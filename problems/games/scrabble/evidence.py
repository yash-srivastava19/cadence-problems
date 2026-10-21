"""What the tiles you keep are worth, measured from self-play.

    uv run --with numpy python -m scrabble.evidence --games 5000   # from problems/games
    ... --policy rounds/evidence/values.json --horizon 2 --out evidence_2

Round 1: greedy plays greedy. Later rounds: the last round's values choose the
moves, so the data comes from better play (TD-Gammon and Quackle learn this
way). A player that keeps good tiles on purpose would bias the fit, so a
fraction of moves (--explore) is picked at random from the top five.

Greedy plays greedy: it chooses on points alone, so the tiles it keeps vary
for reasons unrelated to how good they are, which is close to a randomized
experiment. For every turn with 7+ tiles in the bag we record the tiles kept
and that player's points on their next turn. A least-squares fit of those
points on the tiles kept gives each tile's worth, against drawing a fresh one.
"""

import argparse
import json
import os
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from scrabble import simulate
from scrabble.game import Game
from scrabble.ruleset import BLANK, Ruleset, load

HERE = Path(__file__).parent
FIRST = 800_000  # bags no run, gate, check or lesson uses

_rs: Ruleset | None = None
_policy: dict | None = None
_horizon, _explore = 1, 0.0


def _init(policy: dict | None = None, horizon: int = 1, explore: float = 0.0) -> None:
    global _rs, _policy, _horizon, _explore
    _rs = load(HERE / "english.json")
    _policy, _horizon, _explore = policy, horizon, explore


def leave_value(leave, values: dict) -> float:
    """What the fitted values say a leave is worth, against drawing fresh."""
    counts = Counter(leave)
    dup = sum(c - 1 for t, c in counts.items() if c > 1 and t != BLANK)
    value = sum(values[t][0] * c for t, c in counts.items())
    value += values["each duplicate"][0] * dup
    if "Q" in counts and "U" not in counts:
        value += values["Q without U"][0]
    return value


def choose(g: Game, rng: random.Random):
    moves = g.legal()
    if _policy is None:
        return simulate.greedy(moves)
    weight = 1.0 if len(g.bag) >= 7 else 0.5 if g.bag else 0.0
    ranked = sorted(moves, key=lambda m: -(m.score + weight * leave_value(m.leave, _policy)))
    if rng.random() < _explore:
        return rng.choice(ranked[:5])
    return ranked[0]


def game(seed: int) -> list[dict]:
    """One game: (leave, own points over the next turns) for every early turn."""
    assert _rs is not None
    g = Game(_rs, seed)
    rng = random.Random(seed)
    turns: list[dict] = []
    while not g.over:
        move = choose(g, rng)
        turns.append({"p": g.to_move, "bag": len(g.bag), "leave": list(move.leave),
                      "score": move.score, "kind": move.kind,
                      "tiles": len(move.tiles)})
        g.apply(move)
    samples = []
    for i, t in enumerate(turns):
        later = range(i + 2, i + 2 * _horizon + 1, 2)  # the same player's turns
        if t["bag"] < 7 or later[-1] >= len(turns):
            continue
        samples.append({"leave": t["leave"], "next": sum(turns[j]["score"] for j in later),
                        "bingo_next": turns[later[0]]["tiles"] == 7,
                        "kind": t["kind"], "seed": seed})
    return samples


def features(leave: list[str], tokens: list[str]) -> list[float]:
    counts = Counter(leave)
    dup = sum(c - 1 for t, c in counts.items() if c > 1 and t != BLANK)
    q_no_u = float("Q" in counts and "U" not in counts)
    return [1.0, *(float(counts[t]) for t in tokens), float(dup), q_no_u]


def fit(samples: list[dict], tokens: list[str]):
    import numpy as np

    x = np.array([features(s["leave"], tokens) for s in samples])
    y = np.array([s["next"] for s in samples], dtype=float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    sigma2 = resid @ resid / (len(y) - x.shape[1])
    se = np.sqrt(np.diag(np.linalg.pinv(x.T @ x)) * sigma2)
    names = ["(nothing kept)", *tokens, "each duplicate", "Q without U"]
    return dict(zip(names, zip(beta.tolist(), se.tolist(), strict=True), strict=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=5000)
    parser.add_argument("--policy", help="values.json from an earlier round")
    parser.add_argument("--horizon", type=int, default=1, help="own turns counted")
    parser.add_argument("--explore", type=float, default=0.2)
    parser.add_argument("--first", type=int, default=FIRST)
    parser.add_argument("--out", default="evidence")
    args = parser.parse_args()
    out = HERE / "rounds" / args.out
    out.mkdir(parents=True, exist_ok=True)
    policy = json.loads(Path(args.policy).read_text()) if args.policy else None
    seeds = range(args.first, args.first + args.games)
    setup = (policy, args.horizon, args.explore)
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init, initargs=setup) as workers:
        samples = [s for chunk in workers.map(game, seeds, chunksize=20) for s in chunk]
    (out / "samples.jsonl").write_text("\n".join(json.dumps(s) for s in samples))

    rs = load(HERE / "english.json")
    tokens = [*rs.tokens, BLANK]
    found = fit(samples, tokens)
    (out / "values.json").write_text(json.dumps(found, indent=1))
    who = "greedy" if policy is None else f"{args.policy} (explore {args.explore})"
    print(f"{len(samples)} turns from {args.games} games by {who}, horizon {args.horizon}")
    for name, (value, err) in sorted(found.items(), key=lambda kv: -kv[1][0]):
        print(f"{name:<16}{value:+7.2f}  ±{2 * err:.2f}")


if __name__ == "__main__":
    main()
