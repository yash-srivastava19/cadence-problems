"""Is the teacher worth listening to? The sim bot must beat the players it
would teach, or its lessons are noise.

    python -m scrabble.teacher_check --bags 16      # from problems/games
"""

import argparse
import math
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from kit.player import Remote
from scrabble import bots, simulate
from scrabble.env import as_dict
from scrabble.game import Game
from scrabble.ruleset import Ruleset, load

HERE = Path(__file__).parent
FIRST = 700_000  # bags no training run or gate uses

_rs: Ruleset | None = None


def _init() -> None:
    global _rs
    _rs = load(HERE / "english.json")


def game(opponent: str, seed: int, seat: int) -> tuple[str, float, float]:
    assert _rs is not None
    g = Game(_rs, seed)
    remote = None
    if opponent == "greedy":
        other = bots.greedy
    elif opponent == "leave":
        other = bots.leave
    else:
        remote = Remote(HERE / "opponents" / f"{opponent}.py", opponent)
        other = remote.choose
    try:
        while not g.over:
            moves = g.legal()
            if g.to_move == seat:
                i = simulate.choose(g, moves, seed=seed * 1000 + g.turn)
            else:
                i = other(g.view(), [as_dict(m) for m in moves])
            g.apply(moves[i])
    finally:
        if remote:
            remote.close()
    mine, theirs = g.scores[seat], g.scores[1 - seat]
    return (
        opponent,
        1.0 if mine > theirs else 0.5 if mine == theirs else 0.0,
        mine - theirs,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bags", type=int, default=16)
    args = parser.parse_args()
    opponents = ["greedy", "leave", "champion_1"]
    jobs = [
        (o, FIRST + b, seat)
        for o in opponents
        for b in range(args.bags)
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init) as workers:
        results = list(workers.map(game, *zip(*jobs, strict=True)))
    print(f"{'sim bot vs':<12}{'games':>6}{'win rate':>10}{'±95%':>7}{'spread':>8}")
    for o in opponents:
        mine = [(p, s) for name, p, s in results if name == o]
        rate = sum(p for p, _ in mine) / len(mine)
        err = 1.96 * math.sqrt(rate * (1 - rate) / len(mine))
        spread = sum(s for _, s in mine) / len(mine)
        print(f"{o:<12}{len(mine):>6}{rate:>10.3f}{err:>7.3f}{spread:>+8.1f}")


if __name__ == "__main__":
    main()
