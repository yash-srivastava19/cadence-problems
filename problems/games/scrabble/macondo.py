"""Macondo's bots as opponents: the world's yardstick.

    python -m scrabble.macondo duel --who v1-spread --bags 500

Macondo (github.com/domino14/macondo) is run as a shell, one per worker
process. Each turn the position is sent as a standard CGP from the bot's side
(its own rack only), and the bot's top move is matched back to one of our
legal moves by the tiles it places. HastyBot is Macondo's static player:
points plus a leave table (NWL23's, on our ENABLE word list).
"""

import argparse
import json
import os
import re
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scrabble import cgp, fastslow
from scrabble.fastslow import fast
from scrabble.game import Game
from scrabble.value import STEADY

HERE = Path(__file__).parent
OUT = HERE / "rounds" / "macondo"
BIN = Path(os.environ.get("MACONDO", Path.home() / "mrel" / "macondo"))
FIRST = 670_000  # bags nothing else uses
COLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ROW = re.compile(r"^\s*1:\s+(.*?)\s{2,}")


class Shell:
    def __init__(self):
        self.p = subprocess.Popen([str(BIN)], cwd=BIN.parent, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.send("set lexicon ENABLE english")
        self.send("set ttable-mem-fraction 0.01")  # peg's table; a dozen shells share the RAM

    def send(self, line: str) -> None:
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def top(self, position: str) -> str:
        """The static bot's best move for a CGP position, as Macondo writes it."""
        self.send(f"load cgp {position}")
        self.send("gen 1")
        for line in self.p.stdout:
            m = ROW.match(re.sub(r"\x1b\[[0-9;]*m", "", line))
            if m:
                return m.group(1).strip()
        raise RuntimeError("macondo exited")

    def simmed(self, position: str, plays: int = 15, plies: int = 2, opprack: str = "") -> str:
        """The best move after a 2-ply sim that stops once it is 99% sure.

        BestBot's shape without its rack inference: the opponent's rack is
        drawn at random from the unseen tiles, since the CGP does not hold it.
        """
        self.send(f"load cgp {position}")
        self.send(f"gen {plays}")
        known = f" -opprack {opprack}" if opprack else ""
        self.send(f"sim -plies {plies} -stop 99 -threads 1{known}")
        table = False
        for line in self.p.stdout:
            line = re.sub(r"\x1b\[[0-9;]*m", "", line)
            if line.startswith("Play") and "Win%" in line:
                table = True
            elif table:
                row = line.strip()
                if row.startswith("("):
                    return row[: row.index(")") + 1]
                return " ".join(row.split()[:2])
        raise RuntimeError("macondo exited")

    def pegged(self, position: str, seconds: int = 8) -> str:
        """The pre-endgame solver's move: every draw from a one-tile bag, played out."""
        self.send(f"load cgp {position}")
        self.send(f"peg -threads 1 -endgameplies 4 -maxtime {seconds}")
        table = False
        for line in self.p.stdout:
            line = re.sub(r"\x1b\[[0-9;]*m", "", line)
            if line.startswith("Play") and "%Win" in line:
                table = True
            elif table:
                row = line.strip()
                if row.startswith("("):
                    return row[: row.index(")") + 1]
                return " ".join(row.split()[:2])
        raise RuntimeError("macondo exited")


def position(g: Game) -> str:
    """Standard CGP from the side to move: its rack, no opponent rack, no bag."""
    rows = cgp.encode(g, viewer=g.to_move).split(" ")[0]
    p = g.to_move
    return f"{rows} {''.join(g.racks[p])}/ {g.scores[p]}/{g.scores[1 - p]} {g.scoreless} lex ENABLE;"


def _placed(moves, coord: str, word: str) -> int | None:
    """The play putting exactly these tiles down, if any."""
    if coord[0].isdigit():
        r, c, dr, dc = int(coord[:-1]) - 1, COLS.index(coord[-1]), 0, 1
    else:
        r, c, dr, dc = int(coord[1:]) - 1, COLS.index(coord[0]), 1, 0
    placed, k, through = set(), 0, False
    for ch in word:  # letters already on the board are in brackets: (B)EHOVE
        if ch in "()":
            through = ch == "("
            continue
        if not through and ch != ".":
            placed.add((r + k * dr, c + k * dc, ch.upper(), ch.islower()))
        k += 1
    for i, m in enumerate(moves):
        if m.kind == "play" and {(a, b, t, bl) for a, b, t, bl in m.tiles} == placed:
            return i
    return None


def match(g: Game, moves, text: str) -> int:
    """Our legal move that is Macondo's `text`."""
    if text.lower().startswith("(exch") or text.lower().startswith("exch"):
        tiles = sorted(text.split()[-1].strip("()"))
        for i, m in enumerate(moves):
            if m.kind == "exchange" and sorted(m.returned) == tiles:
                return i
    if "pass" in text.lower():
        return next(i for i, m in enumerate(moves) if m.kind == "pass")
    coord, word = text.split()[:2]
    # A long word can run into the leave column ("(R)E(INDICT)MENTLO" is
    # REINDICTMENT, leave LO): try cutting letters off the end, and accept a
    # cut only if what was cut is the move's leave.
    for cut in range(0, 8):
        head, tail = (word[:-cut], word[-cut:]) if cut else (word, "")
        i = _placed(moves, coord, head)
        if i is not None and (not cut or sorted(moves[i].leave) == sorted(tail.upper())):
            return i
    raise ValueError(f"no legal move matches {text!r}")


# --- duels --------------------------------------------------------------------

_shell, _who, _solver, _vs, _their_solver = None, None, None, "hasty", None
_seen = [0, 0, 0.0]


def _init(who: str, vs: str = "hasty") -> None:
    global _shell, _who, _vs, _their_solver
    _who, _vs = who, vs
    if vs == "sim":
        from scrabble.endgame import Solver
        _their_solver = Solver(memory=0.02)
    if who.startswith(("v1-", "v2-")):
        from scrabble import value2
        value2._init_player(who)
    elif who.split("+")[0] in ("klv", "klve"):
        fastslow._init({})
        from scrabble import leaves
        leaves.table()
        if who.startswith("klve"):  # klv until the bag is empty, then the exact solver
            global _solver
            from scrabble.endgame import Solver
            _solver = Solver(memory=0.02)
    elif who.startswith(("s2-", "flat-", "s3")):
        from scrabble import search
        search._init_player(who)
    else:
        fastslow._init({})
    _shell = Shell()


def ours(g: Game, moves, seed: int) -> int:
    if _who == "steady":
        return fast(g, moves, STEADY)
    if _who.split("+")[0] in ("klv", "klve"):
        from scrabble import leaves
        if _solver is not None and not g.bag and len(moves) > 1:
            text = _solver.best(g)
            if text is not None:
                return match(g, moves, text)
        extras = _who.split("+")[1:]
        if "peg" in extras and len(g.bag) == 1:  # H1
            return match(g, moves, _shell.pegged(position(g)))
        deep = {"plays": 10, "plies": 3} if "sim3" in extras else {}  # H3: depth for breadth
        if "oracle" in extras:  # C1: the ceiling of rack inference, by seeing the real rack
            deep["opprack"] = "".join(g.racks[1 - g.to_move])
        if "peg" in extras and len(g.bag) <= 7 or {"sim", "sim3"} & set(extras) and len(g.bag) > 7:  # H1, H2
            return match(g, moves, _shell.simmed(position(g), **deep))
        if "win" in extras and len(g.bag) < 20:  # H3
            return winning(g, moves)
        return leaves.klv(g, moves)
    if _who.startswith(("v1-", "v2-")):
        from scrabble import value2
        return value2.choose(g, moves)
    from scrabble import search
    return search.pick(g, moves, seed)


def winning(g: Game, moves) -> int:
    """H3: the move with the best win chance, not the most points, once the end is near."""
    from scrabble import leaves
    p = g.to_move
    ahead = g.scores[p] - g.scores[1 - p]

    def chance(m):
        drawn = len(m.tiles) if m.kind == "play" else 0
        return leaves.winp(ahead + m.score + leaves.value(m.leave), max(0, len(g.bag) - drawn))

    keys = [chance(m) for m in moves]
    return keys.index(max(keys))


def their_move(g: Game, moves) -> int:
    if _vs == "sim":
        if not g.bag and len(moves) > 1:
            text = _their_solver.best(g)
            if text is not None:
                return match(g, moves, text)
        return match(g, moves, _shell.simmed(position(g)))
    return match(g, moves, _shell.top(position(g)))


def written(m) -> str:
    """A move as Macondo writes it: tiles already on the board are dots."""
    if m.kind == "exchange":
        return f"exch {''.join(m.returned)}"
    if m.kind == "pass":
        return "pass"
    at = {(r, c): t.lower() if blank else t for r, c, t, blank in m.tiles}
    return f"{m.where} {''.join(at.get(cell, '.') for cell in _span(m))}"


def _span(m):
    coord = m.where
    if coord[0].isdigit():
        r, c = int(coord[:-1]) - 1, COLS.index(coord[-1])
        return [(r, c + k) for k in range(len(m.word))]
    r, c = int(coord[1:]) - 1, COLS.index(coord[0])
    return [(r + k, c) for k in range(len(m.word))]


def _retried(choose, *args) -> int:
    """A Macondo that died (out of memory, a rare crash) is started again once."""
    try:
        return choose(*args)
    except RuntimeError:
        _init(_who, _vs)
        return choose(*args)


def duel_game(seed: int, seat: int, log: bool = False) -> dict:
    g = Game(fastslow._rs, seed)
    secs, turns, same, theirs, history = 0.0, 0, 0, 0.0, []
    while not g.over:
        moves = g.legal()
        t = time.perf_counter()
        if g.to_move == seat:
            seen = position(g)
            i = _retried(ours, g, moves, seed)
            secs, turns = secs + time.perf_counter() - t, turns + 1
            if _who == "klv":  # the gate: does our copy of HastyBot pick HastyBot's move?
                same += match(g, moves, _shell.top(position(g))) == i
        else:
            seen = None
            i = _retried(their_move, g, moves)
            theirs += time.perf_counter() - t
        if log:
            history.append({"ours": seen is not None, "cgp": seen, "bag": len(g.bag),
                            "scores": [g.scores[seat], g.scores[1 - seat]], "move": written(moves[i]),
                            "points": moves[i].score, "secs": round(time.perf_counter() - t, 2)})
        g.apply(moves[i])
    their_secs = theirs
    mine, theirs = g.scores[seat], g.scores[1 - seat]
    out = {"seed": seed, "seat": seat, "points": 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0,
           "spread": mine - theirs, "secs": round(secs / max(1, turns), 3), "same": same, "turns": turns,
           "their_secs": round(their_secs, 1)}
    if log:
        out["history"] = history
    solver = _solver
    if solver is None and _who.startswith("s3e"):
        from scrabble import search
        solver = search._solver
    if solver is not None:  # this game's endgame solves: calls, gave up, seconds
        now = [solver.calls, solver.fails, solver.secs]
        out["solves"] = [now[0] - _seen[0], now[1] - _seen[1], round(now[2] - _seen[2], 1)]
        _seen[:] = now
    return out


def duel(who: str, bags: int, first: int, vs: str = "hasty", log: bool = False) -> None:
    from scrabble import value

    OUT.mkdir(parents=True, exist_ok=True)
    saved = OUT / f"duel_{who}_vs_{vs}_{first}{'_log' if log else ''}.jsonl"
    games = [json.loads(x) for x in saved.read_text().splitlines() if x.strip()] if saved.exists() else []
    done = {(x["seed"], x["seat"]) for x in games}
    jobs = [(first + k, seat) for k in range(bags) for seat in (0, 1) if (first + k, seat) not in done]
    with ProcessPoolExecutor(int(os.environ.get("WORKERS", os.cpu_count())), initializer=_init, initargs=(who, vs)) as pool, saved.open("a") as out:
        for f in as_completed([pool.submit(duel_game, *job, log) for job in jobs]):
            try:
                games.append(f.result())
            except ValueError as e:  # a move we could not match: skip the game, say so
                print(f"    skipped a game: {e}", flush=True)
                continue
            out.write(json.dumps(games[-1]) + "\n")
            out.flush()
            if len(games) % 100 == 0:
                print(f"    {who} vs {vs} @{first}: {value.summary(games)}", flush=True)
    line = f"{who} vs {vs} @{first}: {value.summary(games)}"
    timed = [x for x in games if "secs" in x]
    if timed:
        line += f", {sum(x['secs'] for x in timed) / len(timed):.2f} s a move"
        solved = [x["solves"] for x in timed if "solves" in x]
        if solved:
            calls = sum(x[0] for x in solved)
            line += (f", endgame solves {calls} (gave up {sum(x[1] for x in solved)},"
                     f" {sum(x[2] for x in solved) / max(1, calls):.1f} s each)")
        if who == "klv":
            line += f", same move as HastyBot {sum(x['same'] for x in timed) / sum(x['turns'] for x in timed):.1%}"
    print(line, flush=True)
    with (OUT / "duels.txt").open("a") as out:
        out.write(line + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["duel"])
    parser.add_argument("--who", default="steady")
    parser.add_argument("--bags", type=int, default=500)
    parser.add_argument("--first", type=int, default=FIRST)
    parser.add_argument("--vs", choices=["hasty", "sim"], default="hasty")
    parser.add_argument("--log", action="store_true", help="keep every move we made, for diagnosis")
    args = parser.parse_args()
    duel(args.who, args.bags, args.first, args.vs, args.log)


if __name__ == "__main__":
    main()
