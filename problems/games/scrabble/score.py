"""Score player.py: duplicate games against the frozen greedy bot.

    python -m scrabble.score          # from examples/games

The candidate plays in its own process (kit.player.Remote). CADENCE_SEED picks
the bags; each bag is played twice with the seats swapped. An answer that is
not an allowed move forfeits that game. A crash fails the whole score.
"""

import os
from pathlib import Path

from kit.play import duplicate
from kit.player import Local, Remote

from scrabble.bots import greedy
from scrabble.env import ScrabbleEnv

BAGS = 25


def main() -> None:
    env = ScrabbleEnv()
    first = int(os.environ.get("CADENCE_SEED", "0")) * 1000
    me = Remote(Path(__file__).with_name("player.py"), "candidate")
    try:
        games = duplicate(env, me, Local(greedy, "greedy"), range(first, first + BAGS))
    finally:
        me.close()

    points, spreads, forfeits = [], [], 0
    for record, seat in games:
        if record["forfeit"]:
            lost = record["forfeit"]["player"] == seat
            forfeits += lost
            points.append(0.0 if lost else 1.0)
            continue
        mine, theirs = record["returns"][seat], record["returns"][1 - seat]
        points.append(1.0 if mine > theirs else 0.5 if mine == theirs else 0.0)
        spreads.append(mine - theirs)

    print(f"win_rate: {sum(points) / len(points):.4f}")
    print(f"spread: {sum(spreads) / max(1, len(spreads)):.1f}")
    print(f"forfeits: {forfeits}")


if __name__ == "__main__":
    main()
