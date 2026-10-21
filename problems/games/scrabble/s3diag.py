"""Why S3 does not beat its own prior: is the first cut a coin flip?

    python -m scrabble.s3diag --positions 200

On positions from klv self-play (bags 710000+, mid-game), records how often
S3 picks something other than klv's top move, the spread of single rollouts,
and the equity gaps among klv's top 8.
"""

import argparse
import json
import random
import statistics
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from scrabble import fastslow, leaves, search
from scrabble.game import Game

OUT = Path(__file__).parent / "rounds" / "s3"


def _init():
    search._init_player("s3-klv-64")


def one(seed: int) -> dict | None:
    g = Game(fastslow._rs, seed)
    stop = random.Random(seed).randrange(4, 14)
    for _ in range(stop):
        if g.over or len(g.bag) < 10:
            return None
        moves = g.legal()
        g.apply(moves[leaves.klv(g, moves)])
    if g.over or not g.bag:
        return None
    moves = g.legal()
    eq = [leaves.equity(g, m) for m in moves]
    top = sorted(range(len(moves)), key=lambda i: (-eq[i], i))[:8]
    pick = search.pick(g, moves, seed)
    p = g.to_move
    lead = g.scores[p] - g.scores[1 - p]
    rolls = {i: [search.rollout(g, p, moves[i], random.Random(f"{seed}:{s}").randrange(2**31)) - lead
                 for s in range(16)] for i in top[:2]}
    a, b = rolls[top[0]], rolls[top[1]]
    return {"seed": seed, "bag": len(g.bag), "gaps": [round(eq[top[0]] - eq[i], 1) for i in top],
            "same": pick == top[0], "pick_rank": top.index(pick) if pick in top else -1,
            "sd": round(statistics.pstdev(a), 1), "sd_diff": round(statistics.pstdev([x - y for x, y in zip(a, b)]), 1),
            "mean_rel": [round(statistics.mean(a), 1), round(statistics.mean(b), 1)],
            "equity": [round(eq[top[0]], 1), round(eq[top[1]], 1)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", type=int, default=200)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(args.workers, initializer=_init) as pool:
        rows = [r for r in pool.map(one, range(711000, 711000 + args.positions)) if r]
    (OUT / "diag.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    n = len(rows)
    lines = [
        f"{n} positions",
        f"S3 picks klv's top move: {sum(r['same'] for r in rows) / n:.0%}",
        f"rank of S3's pick in klv's top 8: {statistics.mean(r['pick_rank'] for r in rows):.2f} on average",
        f"one rollout's sd: {statistics.median(r['sd'] for r in rows):.1f} (median)",
        f"sd of the paired difference, top 1 vs top 2 (same worlds): {statistics.median(r['sd_diff'] for r in rows):.1f}",
        f"equity gap top 1 to top 2: {statistics.median(r['gaps'][1] for r in rows):.1f}, to top 8: "
        f"{statistics.median(r['gaps'][-1] for r in rows):.1f} (median)",
        f"rollout mean minus equity, top 1: {statistics.mean(r['mean_rel'][0] - r['equity'][0] for r in rows):+.1f}",
    ]
    (OUT / "diag.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
