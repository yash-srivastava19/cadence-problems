"""E0: how many points does steady give away once the bag is empty?

    python -m scrabble.endgame --positions 300

With the bag empty nothing is hidden, so the endgame can be solved like a
chess endgame. Macondo's solver gives the final spread under best play, from
the side to move. Steady's move is valued by solving the position after it,
from the other side. The gap is what an exact endgame would win back, per
game, before anyone builds one.
"""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from scrabble import cgp, fastslow
from scrabble.fastslow import fast
from scrabble.game import Game
from scrabble.macondo import BIN
from scrabble.value import STEADY

HERE = Path(__file__).parent
OUT = HERE / "rounds" / "endgame"
FIRST = 680_000  # bags nothing else uses
PLIES = 6
FINAL = re.compile(r"Final spread after seq: ([+-]?\d+)")
BEST = re.compile(r"Best move: (.*)$")


class Solver:
    def __init__(self, memory: float | None = None):
        self.p = subprocess.Popen([str(BIN)], cwd=BIN.parent, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.send("set lexicon ENABLE english")
        if memory is not None:  # share of RAM for the table; many solvers run at once in a duel
            self.send(f"set ttable-mem-fraction {memory}")
        self.calls, self.fails, self.secs = 0, 0, 0.0

    def send(self, line: str) -> None:
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def load(self, g: Game) -> None:
        p = g.to_move
        rows = cgp.encode(g).split(" ")[0]
        self.send(f"load cgp {rows} {''.join(g.racks[p])}/{''.join(g.racks[1 - p])} "
                  f"{g.scores[p]}/{g.scores[1 - p]} {g.scoreless} lex ENABLE;")

    def best(self, g: Game, seconds: int = 10) -> str | None:
        """The solver's move as Macondo writes it, or None if it gave up."""
        self.load(g)
        self.send(f"endgame -plies {PLIES} -maxtime {seconds} -threads 1")
        start = time.perf_counter()
        self.calls += 1
        for line in self.p.stdout:
            line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            m = BEST.search(line)
            if m:
                self.secs += time.perf_counter() - start
                return m.group(1).strip()
            if line.startswith("Error:"):  # the shell's own errors; logs may say error= too
                self.secs += time.perf_counter() - start
                self.fails += 1
                return None
        raise RuntimeError("macondo exited")

    def final(self, g: Game) -> int:
        """Final spread for the side to move, under best play from here."""
        self.load(g)
        self.send(f"endgame -plies {PLIES}")
        for line in self.p.stdout:
            m = FINAL.search(re.sub(r"\x1b\[[0-9;]*m", "", line))
            if m:
                return int(m.group(1))
        raise RuntimeError("macondo exited")


def first_empty(seed: int) -> Game | None:
    """Steady against itself, up to the first turn with an empty bag."""
    g = Game(fastslow._rs, seed)
    while not g.over and g.bag:
        moves = g.legal()
        g.apply(moves[fast(g, moves, STEADY)])
    return None if g.over else g


def gap(solver: Solver, seed: int) -> dict | None:
    g = first_empty(seed)
    if g is None:
        return None
    p = g.to_move
    best = solver.final(g)
    moves = g.legal()
    g.apply(moves[fast(g, moves, STEADY)])
    if g.over:
        steady = g.scores[p] - g.scores[1 - p]
    else:
        steady = -solver.final(g)
    return {"seed": seed, "best": best, "steady": steady, "lost": best - steady,
            "flips": (best > 0) != (steady > 0)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--positions", type=int, default=300)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fastslow._init({})
    saved = OUT / "gaps.jsonl"
    rows = [json.loads(x) for x in saved.read_text().splitlines() if x.strip()] if saved.exists() else []
    done = {x["seed"] for x in rows}
    solver = Solver()
    with saved.open("a") as out:
        for k in range(args.positions):
            if FIRST + k in done:
                continue
            r = gap(solver, FIRST + k)
            if r is None:
                continue
            rows.append(r)
            out.write(json.dumps(r) + "\n")
            out.flush()
            if len(rows) % 25 == 0:
                print(f"    {len(rows)} endgames, mean points lost {sum(x['lost'] for x in rows) / len(rows):.2f}",
                      flush=True)
    n = len(rows)
    lost = [x["lost"] for x in rows]
    m = sum(lost) / n
    se = (sum((x - m) ** 2 for x in lost) / max(1, n - 1) / n) ** 0.5
    line = (f"{n} endgames: steady loses {m:.2f} ±{2 * se:.2f} points a game to best play; "
            f"the result flips in {sum(x['flips'] for x in rows)} of them")
    print(line, flush=True)
    (OUT / "summary.txt").write_text(line + "\n")


if __name__ == "__main__":
    main()
