"""Fast and slow: does thinking ahead teach the quick rule anything?

    uv run --with numpy python -m scrabble.fastslow duel --bags 100      # H1a, records lessons
    uv run --with numpy python -m scrabble.fastslow distill              # H1b: fit from them
    uv run --with numpy python -m scrabble.fastslow duel --bags 100 --fast rounds/fastslow/weights.json

Fast is the equity rule: points now plus what the tiles kept are worth (the
A2 values measured from self-play). Slow plays each short-listed move into
many invented worlds that fit what the player can see, lets the opponent
reply, and scores what is left with the fast rule's own value.

H1a: slow beats fast. If not, there is nothing to distil.
H1b: fit the fast rule's weights to what slow found, add a few board
features the fast rule cannot see today, and the distilled fast rule beats
the old one at the same speed.
"""

import argparse
import json
import math
import os
import random
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from scrabble.game import Game, Move
from scrabble.ruleset import BLANK, Ruleset, load
from scrabble.simulate import gap, mean, world

HERE = Path(__file__).parent
OUT = HERE / "rounds" / "fastslow"
A2 = json.loads((HERE / "rounds" / "evidence_a2" / "values.json").read_text())
DUEL_FIRST, CHECK_FIRST = 610_000, 620_000  # bags nothing else uses

# The fast rule as it stands: points + leave. Board features start at zero,
# which is exactly what the fast rule assumes today.
FEATURES = ("score", "leave", "opens_T", "opens_D", "opens_t", "tiles")
BASE = {"score": 1.0, "leave": 1.0, "opens_T": 0.0, "opens_D": 0.0,
        "opens_t": 0.0, "tiles": 0.0}

_rs: Ruleset | None = None
_cfg: dict = {}


def _init(cfg: dict) -> None:
    global _rs, _cfg
    _rs = load(HERE / "english.json")
    _cfg = cfg


def leave_value(leave) -> float:
    counts = Counter(leave)
    value = sum(A2[t][0] * c for t, c in counts.items())
    value += A2["each duplicate"][0] * sum(
        c - 1 for t, c in counts.items() if c > 1 and t != BLANK
    )
    if "Q" in counts and "U" not in counts:
        value += A2["Q without U"][0]
    return value


def opened(g: Game, move: Move) -> Counter:
    """Empty premium squares that sit next to a tile only after this move:
    the lanes it hands the opponent (and itself)."""
    found: Counter = Counter()
    if move.kind != "play":
        return found
    placed = {(r, c) for r, c, _, _ in move.tiles}
    n = len(g.grid)
    seen = set()
    for r, c in placed:
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if not (0 <= rr < n and 0 <= cc < n) or (rr, cc) in placed:
                continue
            if g.grid[rr][cc] is not None or (rr, cc) in seen:
                continue
            seen.add((rr, cc))
            if any(
                0 <= rr + a < n and 0 <= cc + b < n and g.grid[rr + a][cc + b] is not None
                for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ):
                continue  # already next to a tile before the move
            premium = g.rs.premiums[rr][cc]
            if premium in "TDt":
                found[premium] += 1
    return found


def features(g: Game, move: Move) -> dict[str, float]:
    lanes = opened(g, move)
    return {
        "score": float(move.score),
        "leave": leave_value(move.leave),
        "opens_T": float(lanes["T"]),
        "opens_D": float(lanes["D"]),
        "opens_t": float(lanes["t"]),
        "tiles": float(len(move.tiles)),
    }


def key(g: Game, move: Move, weights: dict[str, float]) -> float:
    """The fast rule. Leave and board matter less as the bag empties."""
    late = 1.0 if len(g.bag) >= 7 else 0.5 if g.bag else 0.0
    x = features(g, move)
    return sum(
        weights[name] * x[name] * (1.0 if name == "score" else late)
        for name in FEATURES
    )


def fast(g: Game, moves: list[Move], weights: dict[str, float]) -> int:
    keys = [key(g, m, weights) for m in moves]
    return keys.index(max(keys))


def value(g: Game, p: int) -> float:
    ahead = g.scores[p] - g.scores[1 - p]
    if g.over:
        return float(ahead)
    late = 1.0 if len(g.bag) >= 7 else 0.5 if g.bag else 0.0
    return ahead + late * (leave_value(g.racks[p]) - leave_value(g.racks[1 - p]))


def slow(g: Game, moves: list[Move], seed: int, record: list | None = None) -> int:
    """Simulate the fast rule's shortlist; keep what did best on average."""
    keep, samples, plies = _cfg["keep"], _cfg["samples"], _cfg["plies"]
    if len(moves) == 1:
        return 0
    rule = _cfg.get("weights", BASE)
    keys = [key(g, m, rule) for m in moves]
    picks = sorted(range(len(moves)), key=lambda i: (-keys[i], i))[:keep]
    if not g.bag:
        samples = 1  # nothing hidden: one world is the real one
    p = g.to_move
    outcomes: dict[int, list[float]] = {i: [] for i in picks}
    for s in range(samples):
        world_seed = random.Random(f"{seed}:{s}").randrange(2**31)
        for i in picks:
            w = world(g, p, random.Random(world_seed))
            w.apply(moves[i])
            for _ in range(plies):
                if w.over:
                    break
                replies = w.legal()
                w.apply(replies[fast(w, replies, rule)])
            outcomes[i].append(value(w, p))
    best = max(picks, key=lambda i: (mean(outcomes[i]), -i))
    if record is not None and len(g.bag) >= 7 and len(picks) > 1:
        record.append(
            {
                "x": [features(g, moves[i]) for i in picks],
                "y": [mean(outcomes[i]) for i in picks],
                "bag": len(g.bag),
                "agrees": best == picks[0],
                "gap": gap(outcomes[best], outcomes[picks[0]])[0],
            }
        )
    return best


def play(seed: int, seat: int, a: str, b: str, weights: dict) -> dict:
    """One game, player a in `seat`. Players: 'slow', 'fast', 'fast2'."""
    assert _rs is not None
    g = Game(_rs, seed)
    spent = {a: 0.0, b: 0.0}
    calls = {a: 0, b: 0}
    lessons: list = []
    while not g.over:
        moves = g.legal()
        who = a if g.to_move == seat else b
        start = time.perf_counter()
        if who == "slow":
            i = slow(g, moves, seed * 1000 + g.turn, record=lessons)
        else:
            i = fast(g, moves, weights if who == "fast2" else BASE)
        spent[who] += time.perf_counter() - start
        calls[who] += 1
        g.apply(moves[i])
    mine, theirs = g.scores[seat], g.scores[1 - seat]
    return {
        "points": 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0,
        "spread": mine - theirs,
        "ms": 1000 * spent[a] / max(1, calls[a]),
        "lessons": lessons,
    }


def _duel_job(args):
    return play(*args)


def duel(
    a: str, b: str, bags: int, weights: dict, cfg: dict, first: int,
    lessons_to: Path | None = None, progress: bool = False,
) -> dict:
    from concurrent.futures import as_completed

    jobs = [(first + k, seat, a, b, weights) for k in range(bags) for seat in (0, 1)]
    games = []
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init, initargs=(cfg,)) as pool:
        for done in as_completed([pool.submit(_duel_job, job) for job in jobs]):
            games.append(done.result())
            if progress and len(games) % 20 == 0:
                rate = sum(r["points"] for r in games) / len(games)
                spread = sum(r["spread"] for r in games) / len(games)
                print(f"    {len(games)}/{len(jobs)} games: {a} {rate:.3f}, {spread:+.1f}", flush=True)
    lessons = [x for r in games for x in r["lessons"]]
    if lessons:
        path = lessons_to or OUT / f"lessons_{a}_vs_{b}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(x) for x in lessons))
    rate = sum(r["points"] for r in games) / len(games)
    return {
        "a": a, "b": b, "games": len(games), "win_rate": rate,
        "margin": 1.96 * math.sqrt(rate * (1 - rate) / len(games)),
        "spread": sum(r["spread"] for r in games) / len(games),
        "spread_se": _se([r["spread"] for r in games]),
        "ms_per_move": sum(r["ms"] for r in games) / len(games),
    }


def _se(xs: list[float]) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def fit(lessons: list) -> dict:
    """Weights that make the fast rule rank moves the way slow found them.

    Within each position, outcome differences between moves regressed on
    feature differences: the position's own luck and score cancel out, and
    what is left is what each feature is worth to the move.
    """
    import numpy as np

    rows, target = [], []
    for lesson in lessons:
        x = np.array([[f[n] for n in FEATURES] for f in lesson["x"]])
        y = np.array(lesson["y"])
        rows.append(x - x.mean(axis=0))
        target.append(y - y.mean())
    X, Y = np.vstack(rows), np.concatenate(target)
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ beta
    sigma2 = resid @ resid / (len(Y) - X.shape[1])
    se = np.sqrt(np.diag(np.linalg.pinv(X.T @ X)) * sigma2)
    return {n: (float(b), float(s)) for n, b, s in zip(FEATURES, beta, se, strict=True)}


def iterate(rounds: int, bags: int, cfg: dict) -> None:
    """Expert iteration: slow thinking with fast_k teaches fast_k+1.

    Round 1 starts from the weights the first distillation found. Every new
    rule is checked against the original fast rule on the same 2000 games,
    none of them used for fitting, so rounds are measured on one yardstick.
    """
    folder = OUT / "iterate"
    folder.mkdir(parents=True, exist_ok=True)
    rule = {n: v[0] for n, v in json.loads((OUT / "weights.json").read_text()).items()}
    log = folder / "rounds.txt"
    for k in range(1, rounds + 1):
        print(f"round {k}: slow(fast_{k}) plays fast_{k}, {2 * bags} games", flush=True)
        duel("slow", "fast2", bags, rule, cfg | {"weights": rule}, 630_000 + 1000 * k,
             lessons_to=folder / f"lessons_{k}.jsonl", progress=True)
        lessons = [json.loads(x) for x in (folder / f"lessons_{k}.jsonl").read_text().splitlines()]
        found = fit(lessons)
        new = {n: v[0] for n, v in found.items()}
        (folder / f"weights_{k + 1}.json").write_text(json.dumps(found, indent=1))
        check = duel("fast2", "fast", 1000, new, cfg, CHECK_FIRST)
        line = (
            f"fast_{k + 1}: " + ", ".join(f"{n} {v:+.2f}" for n, v in new.items())
            + f" | vs fast_0, 2000 games: {check['win_rate']:.3f} ±{check['margin']:.3f},"
            f" spread {check['spread']:+.1f} ±{2 * check['spread_se']:.1f}"
            f" | {len(lessons)} lessons"
        )
        print(line, flush=True)
        with log.open("a") as out:
            out.write(line + "\n")
        rule = new


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["duel", "distill", "iterate"])
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--bags", type=int, default=100)
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--a", default="slow")
    parser.add_argument("--b", default="fast")
    parser.add_argument("--fast", help="weights.json for the distilled fast rule")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--plies", type=int, default=1)
    parser.add_argument("--keep", type=int, default=6)
    args = parser.parse_args()
    cfg = {"samples": args.samples, "plies": args.plies, "keep": args.keep}
    OUT.mkdir(parents=True, exist_ok=True)

    if args.what == "iterate":
        iterate(args.rounds, args.bags, cfg)
        return

    if args.what == "duel":
        weights = BASE
        if args.fast:
            weights = {n: v[0] for n, v in json.loads(Path(args.fast).read_text()).items()}
        # The distilled rule is checked on games it did not learn from.
        first = CHECK_FIRST if args.fast else DUEL_FIRST
        r = duel(args.a, args.b, args.bags, weights, cfg, first)
        print(
            f"{r['a']} vs {r['b']} ({cfg}): {r['games']} games, win {r['win_rate']:.3f}"
            f" ±{r['margin']:.3f}, spread {r['spread']:+.1f} ±{2 * r['spread_se']:.1f},"
            f" {r['ms_per_move']:.0f} ms/move for {r['a']}",
            flush=True,
        )
        return

    lessons = [
        json.loads(line)
        for path in sorted(OUT.glob("lessons_*.jsonl"))
        for line in path.read_text().splitlines()
    ]
    agree = sum(x["agrees"] for x in lessons) / len(lessons)
    found = fit(lessons)
    (OUT / "weights.json").write_text(json.dumps(found, indent=1))
    print(f"{len(lessons)} slow decisions (bag 7+), from the recorded duels")
    print(f"slow chose the fast rule's first choice in {agree:.1%} of them")
    for name, (b, s) in found.items():
        print(f"  {name:<8} {b:+7.3f} ±{2 * s:.3f}   (fast rule today: {BASE[name]:+.1f})")


if __name__ == "__main__":
    main()
