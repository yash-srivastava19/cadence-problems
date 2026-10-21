"""A front end for the players, in the spirit of Stockfish.

    T="uv run --with numpy --with torch --index https://download.pytorch.org/whl/cpu python -m"
    $T scrabble.engine analyse "<CGP>" --player s2-v1-spread-64 --top 5
    $T scrabble.engine play --player steady            # a game in the terminal
    $T scrabble.engine serve --port 8765               # the same in a browser
    $T scrabble.engine uci                             # a line protocol for other programs

A position comes in as CGP, ours (cgp.py) or Macondo's (no turn, no held:
the other rack is assumed full while the bag lasts). The engine rebuilds a
game from what the player to move can see, the hidden tiles drawn at random
from the unseen ones, so no player can peek.

Moves are written 8H WORD (across) or H8 WORD (down), a blank in lowercase,
"." for a letter already on the board; exchange ABC (? for a blank); pass.
"""

import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

from scrabble import cgp, fastslow
from scrabble.fastslow import BASE, key
from scrabble.game import Game, Move
from scrabble.ruleset import BLANK
from scrabble.value import STEADY, after, shortlist

HERE = Path(__file__).parent
COORD = re.compile(r"^(\d{1,2}[A-Za-z]|[A-Za-z]\d{1,2})$")


# --- players ----------------------------------------------------------------

class Equity:
    """fast_0 and steady: points plus leave, one rule over every legal move."""

    def __init__(self, name: str):
        rules()
        self.weights = BASE if name == "fast_0" else STEADY
        self.unit = "equity"

    def rank(self, g: Game, moves, seed: int, seconds: float | None):
        keys = [key(g, m, self.weights) for m in moves]
        order = sorted(range(len(moves)), key=lambda i: (-keys[i], i))
        return order[0], [(i, keys[i]) for i in order]


class Net:
    """A value2 network judging steady's top ten afterstates."""

    def __init__(self, name: str):
        from scrabble import value2
        value2._init_player(name)
        self.unit = "win chance" if name.endswith("-win") else "final spread"

    def rank(self, g: Game, moves, seed: int, seconds: float | None):
        from scrabble import search
        picks = shortlist(g, moves)
        values = search._value([after(g, moves[i]) for i in picks])
        order = sorted(range(len(picks)), key=lambda k: (-values[k], k))
        return picks[order[0]], [(picks[k], values[k]) for k in order]


class Search(Net):
    """S2: the network proposes, simulations decide. Its own averages stay
    inside search.choose, so the list is the network's prior; bestmove is S2's."""

    def __init__(self, name: str):
        from scrabble import search
        search._init_player(name)
        kind, _, head, budget = name.split("-")
        self.budget, self.halving = int(budget), kind == "s2"
        self.unit = ("win chance" if head == "win" else "final spread") + " (net prior)"

    def rank(self, g: Game, moves, seed: int, seconds: float | None):
        from scrabble import search
        _, ranked = super().rank(g, moves, seed, None)
        budget = self.budget if seconds is None else self.fit(g, moves[ranked[0][0]], seconds)
        best = search.choose(g, moves, seed * 1000 + g.turn, budget, self.halving)
        self.last_budget = budget
        return best, [x for x in ranked if x[0] == best] + [x for x in ranked if x[0] != best]

    def fit(self, g: Game, move, seconds: float) -> int:
        """Simulations that fit in `seconds`, from the cost of one."""
        from scrabble import search
        start = time.perf_counter()
        search.rollout(g, g.to_move, move, 0)
        each = max(1e-3, time.perf_counter() - start)
        return max(search.K, int(0.9 * seconds / each))


class Klv:
    """HastyBot's rule: points plus NWL23's learned leaves."""

    def __init__(self, name: str):
        from scrabble import leaves
        rules()
        leaves.table()
        self.unit = "equity (learned leaves)"

    def rank(self, g: Game, moves, seed: int, seconds: float | None):
        from scrabble import leaves
        keys = [leaves.equity(g, m) for m in moves]
        order = sorted(range(len(moves)), key=lambda i: (-keys[i], i))
        return order[0], [(i, keys[i]) for i in order]


class S3(Klv):
    """S3: learned leaves propose, simulations decide; 's3e-' also solves the
    endgame exactly (needs Macondo, see macondo.BIN). The list is the klv prior."""

    def __init__(self, name: str):
        from scrabble import search
        super().__init__(name)
        search._init_player(name)
        self.unit = "equity (klv prior)"

    def rank(self, g: Game, moves, seed: int, seconds: float | None):
        from scrabble import search
        _, ranked = super().rank(g, moves, seed, None)
        best = search.pick(g, moves, seed)
        return best, [x for x in ranked if x[0] == best] + [x for x in ranked if x[0] != best]


# Name, or prefix ending in "-", to the class that plays it. A new player is one line.
PLAYERS = {
    "fast_0": Equity,
    "steady": Equity,
    "v1-": Net,
    "v2-": Net,
    "s2-": Search,
    "flat-": Search,
    "klv": Klv,
    "s3-": S3,
    "s3e-": S3,
}
_loaded: dict = {}


def player(name: str):
    if name not in _loaded:
        for k, cls in PLAYERS.items():
            if name == k or (k.endswith("-") and name.startswith(k)):
                try:
                    _loaded[name] = cls(name)
                except ImportError as e:
                    raise ValueError(f"{name} needs {e.name}: run with "
                                     "uv run --with numpy --with torch --index "
                                     "https://download.pytorch.org/whl/cpu") from None
                break
        else:
            raise ValueError(f"unknown player {name!r}; known: {', '.join(PLAYERS)}")
    return _loaded[name]


def rules():
    if fastslow._rs is None:
        fastslow._init({})
    return fastslow._rs


# --- positions and moves ----------------------------------------------------

def position(rs, text: str) -> cgp.Position:
    """Parse a CGP, ours or Macondo's, and check it fits the tile set."""
    text = " ".join(text.split())
    fields = text.split(" ", 4)
    if len(fields) < 4:
        raise ValueError("a CGP needs rows, racks, scores and zeros: '<rows> RACK/ 0/0 0'")
    ops = fields[4] if len(fields) == 5 else ""
    names = {op.strip().partition(" ")[0] for op in ops.split(";") if op.strip()}
    if ops and not ops.endswith(";"):
        text += ";"
    if "turn" not in names:
        text += " turn 0;"
    try:
        pos = cgp.parse(text)
    except (ValueError, KeyError, IndexError) as e:
        raise ValueError(f"not a CGP I can read ({e})") from None
    if len(pos.grid) != rs.size or any(len(row) != rs.size for row in pos.grid):
        raise ValueError(f"the board must be {rs.size} rows of {rs.size} squares")
    seen = Counter(pos.racks[0])
    for row in pos.grid:
        for cell in row:
            if cell is not None:
                if cell[0] not in rs.tokens:
                    raise ValueError(f"{cell[0]!r} is not a tile")
                seen[BLANK if cell[1] else cell[0]] += 1
    extra = seen - Counter(rs.full_set())
    if extra:
        raise ValueError(f"more tiles than the set has: {''.join(sorted(extra.elements()))}")
    if len(pos.racks[0]) > rs.rack:
        raise ValueError(f"a rack holds at most {rs.rack} tiles")
    hidden = len(cgp.unseen(rs, pos))
    if not names & {"held", "bagsize", "bag"}:
        pos.held = min(rs.rack, hidden)
        pos.bag_size = hidden - pos.held
    if pos.held + pos.bag_size != hidden:
        raise ValueError(f"held {pos.held} + bag {pos.bag_size} should be the {hidden} unseen tiles")
    return pos


def rebuild(rs, pos: cgp.Position, seed: int) -> Game:
    """A game that fits what the player to move sees; the rest drawn at random."""
    tiles = cgp.unseen(rs, pos)
    random.Random(seed).shuffle(tiles)
    return cgp.game(rs, pos, tiles[: pos.held], tiles[pos.held :], seed)


def notation(m: Move) -> str:
    if m.kind == "play":
        return f"{m.where} {m.word}"
    if m.kind == "exchange":
        return f"exchange {''.join(m.returned)}"
    return "pass"


def _offsets(where: str, tiles) -> list[int]:
    if where[0].isdigit():
        c0 = ord(where[-1]) - ord("A")
        return [c - c0 for _, c, _, _ in tiles]
    r0 = int(where[1:]) - 1
    return [r - r0 for r, _, _, _ in tiles]


def parse_move(text: str, moves: list[Move], rs=None) -> Move:
    """The legal move the text names, or a ValueError saying what is wrong."""
    words = text.split()
    if not words:
        raise ValueError("type a move: 8H WORD, exchange ABC, or pass")
    head = words[0].lower()
    if head == "pass":
        return next(m for m in moves if m.kind == "pass")
    if head in ("exchange", "exch", "ex") or words[0].startswith("-"):
        tiles = "".join(words[1:]) if not words[0].startswith("-") else words[0][1:]
        want = sorted(tiles.upper())
        if not want:
            raise ValueError("say which tiles: exchange ABC (? for a blank)")
        for m in moves:
            if m.kind == "exchange" and sorted(m.returned) == want:
                return m
        if not any(m.kind == "exchange" for m in moves):
            raise ValueError("no exchanges: the bag has too few tiles")
        raise ValueError(f"those tiles are not all on your rack: {tiles}")
    if len(words) != 2:
        raise ValueError(f"{text!r}: write a play as 8H WORD (across) or H8 WORD (down)")
    a, b = words
    if COORD.match(a):
        where, word = a, b
    elif COORD.match(b):
        where, word = b, a
    else:
        raise ValueError(f"{text!r}: no square like 8H or H8 in it")
    where = where.upper()
    same = [m for m in moves if m.kind == "play" and m.where == where and len(m.word) == len(word)
            and all(w == "." or w.upper() == c.upper() for w, c in zip(word, m.word, strict=True))]
    for m in same:
        if all(word[k] == (t.lower() if bl else t)
               for k, (_, _, t, bl) in zip(_offsets(where, m.tiles), m.tiles, strict=True)):
            return m
    if same:
        raise ValueError(f"{where} {word}: mark the blank in lowercase, e.g. {notation(same[0])}")
    if rs is not None and "." not in word and tuple(word.upper()) not in rs.words:
        raise ValueError(f"{word.upper()} is not in the word list")
    raise ValueError(f"{where} {word} is not a legal play here (try `hint`)")


# --- analysis ---------------------------------------------------------------

def analyse(name: str, g: Game, top: int = 5, seconds: float | None = None, seed: int = 0) -> dict:
    pl = player(name)
    start = time.perf_counter()
    moves = g.legal()
    best, ranked = pl.rank(g, moves, seed, seconds)
    took = time.perf_counter() - start
    out = {
        "player": name,
        "unit": pl.unit,
        "legal": len(moves),
        "bag": len(g.bag),
        "moves": [{"move": notation(moves[i]), "score": moves[i].score,
                   "leave": "".join(moves[i].leave), "value": round(v, 3)}
                  for i, v in ranked[:top]],
        "bestmove": notation(moves[best]),
        "time": round(took, 3),
        "best": moves[best],
    }
    if isinstance(pl, Search):
        out["budget"] = pl.last_budget
    return out


def from_view(name: str, g: Game, top: int = 5, seconds: float | None = None, seed: int = 0) -> dict:
    """Analyse g as the player to move sees it: re-encoded, hidden tiles redrawn."""
    rs = g.rs
    w = rebuild(rs, position(rs, cgp.encode(g, viewer=g.to_move)), seed * 1000 + g.turn)
    return analyse(name, w, top, seconds, seed)


def public(a: dict) -> dict:
    return {k: v for k, v in a.items() if k != "best"}


def report(a: dict) -> str:
    lines = [f"{a['player']} · {a['legal']} legal moves · bag {a['bag']} · value = {a['unit']}"
             + (f" · budget {a['budget']}" if "budget" in a else "")]
    width = max(len(m["move"]) for m in a["moves"])
    for n, m in enumerate(a["moves"], 1):
        lines.append(f"{n:>3}. {m['move']:<{width}}  {m['score']:>4}  leave {m['leave'] or '-':<7}"
                     f"  value {m['value']:+.3f}")
    lines.append(f"time {a['time']:.2f}s")
    lines.append(f"bestmove {a['bestmove']}")
    return "\n".join(lines)


GLYPH = {"T": "=", "D": "-", "t": '"', "d": "'", "*": "*", ".": "."}


def draw(g: Game, you: int | None = None, last: Move | None = None) -> str:
    rs = g.rs
    new = {(r, c) for r, c, _, _ in last.tiles} if last else set()
    cols = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[: rs.size]
    lines = ["    " + " ".join(cols)]
    for r, row in enumerate(g.grid):
        cells = []
        for c, cell in enumerate(row):
            if cell is None:
                cells.append(GLYPH[rs.premiums[r][c]])
            else:
                t = cell[0].lower() if cell[1] else cell[0]
                cells.append(f"\033[1m{t}\033[0m" if (r, c) in new and sys.stdout.isatty() else t)
        lines.append(f"{r + 1:>3} " + " ".join(cells))
    names = ["you" if p == you else "bot" for p in (0, 1)] if you is not None else ["P0", "P1"]
    lines.append(f"    {names[0]} {g.scores[0]} · {names[1]} {g.scores[1]} · bag {len(g.bag)}")
    lines.append('    = 3W  - 2W  " 3L  \' 2L  lowercase = blank')
    return "\n".join(lines)


# --- play in the terminal ---------------------------------------------------

def play(name: str, seed: int, you_first: bool, inp=sys.stdin) -> None:
    player(name)  # first: a player's init loads the word list itself
    rs = rules()
    g = Game(rs, seed)
    you, last = (0 if you_first else 1), None
    print(f"you vs {name}, seed {seed}. Moves: 8H WORD, H8 WORD, exchange ABC, pass, hint, quit.")
    while not g.over:
        if g.to_move != you:
            a = from_view(name, g, seed=seed)
            last = a["best"]
            g.apply(last)
            print(f"\nbot: {a['bestmove']} +{last.score}  (time {a['time']:.2f}s)")
            continue
        print("\n" + draw(g, you, last))
        print(f"    your rack: {' '.join(g.racks[you])}")
        while True:
            print("your move> ", end="", flush=True)
            line = inp.readline()
            if not line or line.strip().lower() in ("quit", "exit", "q"):
                print("\nbye")
                return
            line = line.strip()
            if line.lower() == "hint":
                print(report(from_view(name, g, seed=seed)))
                continue
            try:
                last = parse_move(line, g.legal(), rs)
            except ValueError as e:
                print(f"  {e}")
                continue
            g.apply(last)
            print(f"you: {notation(last)} +{last.score}")
            break
    print("\n" + draw(g, you, last))
    mine, theirs = g.scores[you], g.scores[1 - you]
    verdict = "you win" if mine > theirs else "the bot wins" if theirs > mine else "a tie"
    print(f"game over ({g.end}): {mine}-{theirs}, {verdict}. Bot's rack: {''.join(g.racks[1 - you]) or '-'}")


# --- a line protocol --------------------------------------------------------

def uci(name: str, inp=sys.stdin, out=sys.stdout) -> None:
    """uci, isready, player NAME, position cgp <CGP> | startpos [seed N],
    go [time S] [top N], d, quit. Answers end with bestmove."""
    def say(text):
        out.write(text + "\n")
        out.flush()

    g = None
    for line in inp:
        cmd, _, rest = line.strip().partition(" ")
        try:
            if cmd == "uci":
                say("id name cadence-scrabble")
                say(f"option player {name}")
                say("uciok")
            elif cmd == "isready":
                player(name)
                rules()
                say("readyok")
            elif cmd in ("player", "setoption"):
                value = rest.split()[-1]
                player(value)
                name = value
            elif cmd == "position":
                kind, _, arg = rest.partition(" ")
                rs = rules()
                if kind == "cgp":
                    g = rebuild(rs, position(rs, arg), 0)
                elif kind == "startpos":
                    seed = int(arg.split()[-1]) if arg.strip() else 0
                    start = Game(rs, seed)
                    g = rebuild(rs, position(rs, cgp.encode(start, viewer=0)), seed)
                else:
                    raise ValueError("position cgp <CGP> or position startpos [seed N]")
            elif cmd == "go":
                if g is None:
                    raise ValueError("no position yet")
                args = rest.split()
                opt = dict(zip(args[::2], args[1::2], strict=False))
                a = analyse(name, g, int(opt.get("top", 5)),
                            float(opt["time"]) if "time" in opt else None)
                for n, m in enumerate(a["moves"], 1):
                    say(f"info multipv {n} move {m['move']} score {m['score']} value {m['value']}")
                say(f"info time {a['time']}")
                say(f"bestmove {a['bestmove']}")
            elif cmd == "d":
                if g is not None:
                    say(draw(g))
                    say(f"rack {''.join(g.racks[g.to_move])}")
            elif cmd == "quit":
                return
            elif cmd:
                say(f"info string unknown command {cmd}")
        except ValueError as e:
            say(f"info string error {e}")


# --- main -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scrabble.engine")
    sub = parser.add_subparsers(dest="what", required=True)
    a = sub.add_parser("analyse", help="the best moves in a CGP position")
    a.add_argument("cgp")
    a.add_argument("--player", default="s2-v1-spread-64")
    a.add_argument("--top", type=int, default=5)
    a.add_argument("--time", type=float, help="seconds to think (S2 maps it to simulations)")
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--json", action="store_true")
    p = sub.add_parser("play", help="a game against the bot in the terminal")
    p.add_argument("--player", default="steady")
    p.add_argument("--seed", type=int, default=random.randrange(10**6))
    p.add_argument("--you-first", action="store_true")
    s = sub.add_parser("serve", help="a game against the bot in the browser")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--player", default="steady")
    u = sub.add_parser("uci", help="a line protocol on stdin and stdout")
    u.add_argument("--player", default="steady")
    args = parser.parse_args()

    try:
        if args.what == "analyse":
            player(args.player)
            rs = rules()
            g = rebuild(rs, position(rs, args.cgp), args.seed)
            result = analyse(args.player, g, args.top, args.time, args.seed)
            print(json.dumps(public(result)) if args.json else report(result))
        elif args.what == "play":
            play(args.player, args.seed, args.you_first)
        elif args.what == "serve":
            from scrabble import serve
            serve.run(args.port, args.player)
        else:
            uci(args.player)
    except ValueError as e:
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
