"""S1: does choosing a plan beat sticking to one?

    uv run --with numpy python -m scrabble.plans fixed --bags 1000     # each plan, and shuffle
    uv run --with numpy python -m scrabble.plans planner --bags 200

A plan is a fast rule held for several turns: open the board, close it, turn
tiles over, or play steady. The planner stops at a few points in the game,
plays the rest out under each plan in the same invented worlds, and commits to
the one that won most often. Every player faces steady.
"""

import argparse
import json
import math
import os
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scrabble import fastslow
from scrabble.fastslow import fast
from scrabble.game import Game
from scrabble.simulate import world

HERE = Path(__file__).parent
OUT = HERE / "rounds" / "plans"
FIRST = 640_000
CHECKPOINTS = (70, 45, 20)  # bag sizes at which the planner chooses again
ROLLOUTS = 12

STEADY = {n: v[0] for n, v in json.loads((fastslow.OUT / "weights.json").read_text()).items()}
PLANS = {
    "steady": STEADY,
    "open": STEADY | {"opens_T": 2.0, "opens_D": 1.0, "opens_t": 0.5},
    "close": STEADY | {"opens_T": -7.0, "opens_D": -2.0, "opens_t": -1.2},
    "turnover": STEADY | {"tiles": 1.5, "leave": 0.6},
}


def finish(g: Game, p: int, plan: str) -> tuple[float, float]:
    """Play g to the end, p on `plan`, the opponent on steady."""
    while not g.over:
        moves = g.legal()
        rule = PLANS[plan] if g.to_move == p else STEADY
        g.apply(moves[fast(g, moves, rule)])
    ahead = g.scores[p] - g.scores[1 - p]
    return (1.0 if ahead > 0 else 0.5 if ahead == 0 else 0.0), float(ahead)


def choose(g: Game, seed: int) -> tuple[str, dict]:
    p = g.to_move
    wins = {plan: [] for plan in PLANS}
    for r in range(ROLLOUTS):
        world_seed = random.Random(f"{seed}:{r}").randrange(2**31)
        for plan in PLANS:
            wins[plan].append(finish(world(g, p, random.Random(world_seed)), p, plan))
    score = {
        plan: (sum(w for w, _ in xs) / len(xs), sum(s for _, s in xs) / len(xs))
        for plan, xs in wins.items()
    }
    return max(PLANS, key=lambda plan: score[plan]), score


def play(seed: int, seat: int, who: str) -> dict:
    """One game against steady. `who` is a plan name, 'shuffle' or 'planner'."""
    g = Game(fastslow._rs, seed)
    plan = who if who in PLANS else "steady"
    left = list(CHECKPOINTS)
    rng = random.Random(f"shuffle:{seed}:{seat}")
    choices = []
    while not g.over:
        moves = g.legal()
        if g.to_move == seat and left and len(g.bag) <= left[0]:
            while left and len(g.bag) <= left[0]:
                left.pop(0)
            lead = g.scores[seat] - g.scores[1 - seat]
            if who == "shuffle":
                plan = rng.choice(list(PLANS))
            elif who == "planner":
                plan, score = choose(g, seed * 1000 + g.turn)
                choices.append({"bag": len(g.bag), "lead": lead, "plan": plan,
                                "score": score})
        rule = PLANS[plan] if g.to_move == seat else STEADY
        g.apply(moves[fast(g, moves, rule)])
    mine, theirs = g.scores[seat], g.scores[1 - seat]
    return {
        "seed": seed, "seat": seat, "who": who,
        "points": 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0,
        "spread": mine - theirs, "choices": choices,
    }


def _job(args):
    return play(*args)


def run(who: str, bags: int) -> list[dict]:
    """Each game is saved as it finishes; run again to pick up where it stopped."""
    OUT.mkdir(parents=True, exist_ok=True)
    saved = OUT / f"{who}.jsonl"
    games = [json.loads(x) for x in saved.read_text().splitlines()] if saved.exists() else []
    done_already = {(x["seed"], x["seat"]) for x in games}
    jobs = [(FIRST + k, seat, who) for k in range(bags) for seat in (0, 1)
            if (FIRST + k, seat) not in done_already]
    total = len(jobs) + len(games)
    with ProcessPoolExecutor(os.cpu_count(), initializer=fastslow._init, initargs=({},)) as pool, \
            saved.open("a") as out:
        for done in as_completed([pool.submit(_job, job) for job in jobs]):
            games.append(done.result())
            out.write(json.dumps(games[-1]) + "\n")
            out.flush()
            if len(games) % 20 == 0:
                print(f"    {who}: {len(games)}/{total} games, {summary(games)}", flush=True)
    return [x for x in games if x["seed"] < FIRST + bags]


def summary(games: list[dict]) -> str:
    n = len(games)
    rate = sum(x["points"] for x in games) / n
    spreads = [x["spread"] for x in games]
    m = sum(spreads) / n
    se = math.sqrt(sum((s - m) ** 2 for s in spreads) / max(1, n - 1) / n)
    return (f"win {rate:.3f} ±{1.96 * math.sqrt(rate * (1 - rate) / n):.3f},"
            f" spread {m:+.1f} ±{2 * se:.1f} ({n} games)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["fixed", "planner"])
    parser.add_argument("--bags", type=int, default=200)
    args = parser.parse_args()
    if args.what == "fixed":
        for who in ("open", "close", "turnover", "shuffle"):
            games = run(who, args.bags)
            first = [x for x in games if x["seed"] < FIRST + 200]
            print(f"{who}: {summary(games)} | first 200 bags: {summary(first)}", flush=True)
        return
    games = run("planner", args.bags)
    print(f"planner: {summary(games)}", flush=True)
    picked: dict[tuple[int, str], int] = {}
    for x in games:
        for c in x["choices"]:
            picked[c["bag"] // 25, c["plan"]] = picked.get((c["bag"] // 25, c["plan"]), 0) + 1
    print("plans chosen (bag band, plan): count", dict(sorted(picked.items())), flush=True)


if __name__ == "__main__":
    main()
