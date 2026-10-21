"""Score player.py against every frozen player in opponents/.

    python -m scrabble.score          # from problems/games

Self-play: the pool is the earlier champions, so the bar rises every round.
Every opponent gets the same bags, each played twice with the seats swapped.
Players run in their own processes and see only JSON. An answer that is not an
allowed move forfeits that game; a crash fails the whole score.

Prints win_rate over the whole pool, then vs_<opponent> for each one.
"""

import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from kit.play import duplicate
from kit.player import Remote
from scrabble.env import ScrabbleEnv

HERE = Path(__file__).parent
BAGS = 25

_env: ScrabbleEnv | None = None


def _init() -> None:
    global _env
    _env = ScrabbleEnv()


def pair(candidate: Path, opponent: Path, seed: int) -> tuple[list, tuple]:
    """One bag, both seatings: (opponent, points, spread) for each game."""
    assert _env is not None
    me, them = Remote(candidate, "candidate"), Remote(opponent, opponent.stem)
    try:
        games = duplicate(_env, me, them, [seed])
    finally:
        me.close()
        them.close()
    timing = (me.used, me.calls)
    out, timeouts = [], []
    for record, seat in games:
        if record["forfeit"]:
            lost = record["forfeit"]["player"] == seat
            slow = "no answer within" in record["forfeit"]["reason"]
            out.append((opponent.stem, 0.0 if lost else 1.0, float("nan")))
            timeouts.append(lost and slow)
            continue
        mine, theirs = record["returns"][seat], record["returns"][1 - seat]
        points = 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0
        out.append((opponent.stem, points, mine - theirs))
    return out, (*timing, sum(timeouts))


def evaluate(candidate: Path, pool: list[Path], seeds: list[int]) -> dict:
    jobs = [(candidate, opponent, seed) for opponent in pool for seed in seeds]
    # Half the cores by default: under a full machine a look-ahead player times
    # out on load, not on its own thinking. The sandbox passes no env through.
    half = max(1, (os.cpu_count() or 2) // 2)
    workers_wanted = int(os.environ.get("SCRABBLE_WORKERS", half))
    with ProcessPoolExecutor(workers_wanted, initializer=_init) as workers:
        results = list(workers.map(pair, *zip(*jobs, strict=True)))
    games = [g for out, _ in results for g in out]
    used = sum(t[0] for _, t in results)
    calls = sum(t[1] for _, t in results)
    slow = sum(t[2] for _, t in results)
    spreads = [s for _, _, s in games if s == s]
    metrics = {
        "win_rate": sum(p for _, p, _ in games) / len(games),
        "spread": sum(spreads) / max(1, len(spreads)),
        "forfeits": float(sum(1 for _, _, s in games if s != s)),
        "ms_per_move": 1000 * used / max(1, calls),
        # Forfeits split by cause: over the time limit, or a bad answer.
        "timeouts": float(slow),
    }
    for opponent in pool:
        mine = [p for name, p, _ in games if name == opponent.stem]
        metrics[f"vs_{opponent.stem}"] = sum(mine) / len(mine)
    return metrics


def main() -> None:
    first = int(os.environ.get("CADENCE_SEED", "0")) * 1000
    pool = sorted((HERE / "opponents").glob("*.py"))
    metrics = evaluate(HERE / "player.py", pool, list(range(first, first + BAGS)))
    for name, value in metrics.items():
        print(f"{name}: {value:.4f}")


if __name__ == "__main__":
    main()
