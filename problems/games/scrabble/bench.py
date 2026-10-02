"""The benchmark ladder: duplicate games between the fixed bots.

    python bench.py --games 20

Every seed is played twice with the seats swapped, so both bots get the same
bag. Writes every game to out/records.json and a viewer to out/viewer.html.
"""

import argparse
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from scrabble import bots, viewer
from scrabble.env import as_dict
from scrabble.game import Game, Move
from scrabble.ruleset import Ruleset, load

HERE = Path(__file__).parent
LADDER = [("greedy", "random"), ("leave", "greedy"), ("leave", "random")]
TOP = 5

_rs: Ruleset | None = None


def _init(config: str) -> None:
    global _rs
    _rs = load(config)


def _move(m: Move) -> dict:
    return {
        "kind": m.kind,
        "label": m.label(),
        "score": m.score,
        "tiles": [list(t) for t in m.tiles],
        "returned": list(m.returned),
    }


def play_game(args: tuple[int, str, str]) -> dict:
    seed, name0, name1 = args
    assert _rs is not None
    g = Game(_rs, seed)
    players = [bots.BOTS[name0](seed * 2), bots.BOTS[name1](seed * 2 + 1)]
    frames, gen_ms = [], 0.0
    while not g.over:
        p, view = g.to_move, g.view()
        started = time.perf_counter()
        moves = g.legal()
        ms = (time.perf_counter() - started) * 1000
        gen_ms += ms
        offered = [as_dict(m) for m in moves]
        chosen = moves[players[p](view, offered)]
        value = {
            id(m): bots.equity(view, d) for m, d in zip(moves, offered, strict=True)
        }

        # The viewer's ranking is our own simple equity, not an engine's.
        ranked = sorted(moves, key=lambda m: -value[id(m)])
        top = ranked[:TOP] if chosen in ranked[:TOP] else [*ranked[:TOP], chosen]
        eq = {id(m): round(value[id(m)], 1) for m in top}
        frames.append(
            {
                "turn": g.turn,
                "player": p,
                "rack": view["rack"],
                "bag": view["bag"],
                "unseen": sum(view["unseen"].values()),
                "plays": sum(m.kind == "play" for m in moves),
                "ms": round(ms, 1),
                "move": _move(chosen),
                "top": [
                    {
                        "label": m.label(),
                        "score": m.score,
                        "equity": eq[id(m)],
                        "rank": ranked.index(m) + 1,
                        "chosen": m is chosen,
                    }
                    for m in top
                ],
                "regret_points": max(m.score for m in moves) - chosen.score,
                "regret_equity": round(value[id(ranked[0])] - value[id(chosen)], 1),
            }
        )
        before = list(g.scores)
        g.apply(chosen)
        frames[-1]["scores"] = list(g.scores)
        gained = [after - was for after, was in zip(g.scores, before, strict=True)]
        gained[p] -= chosen.score
        if any(gained):
            frames[-1]["adjust"] = gained
    return {
        "seed": seed,
        "players": [name0, name1],
        "frames": frames,
        "final": list(g.scores),
        "end": g.end,
        "gen_ms": round(gen_ms),
    }


def summarize(games: list[dict], a: str, b: str) -> dict:
    points, spreads = [], []
    for game in games:
        me = game["players"].index(a)
        mine, theirs = game["final"][me], game["final"][1 - me]
        points.append(1.0 if mine > theirs else 0.5 if mine == theirs else 0.0)
        spreads.append(mine - theirs)
    n = len(points)
    rate = sum(points) / n
    return {
        "a": a,
        "b": b,
        "games": n,
        "win_rate": round(rate, 3),
        "ci95": round(1.96 * math.sqrt(rate * (1 - rate) / n), 3),
        "spread": round(sum(spreads) / n, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=10, help="seeds per matchup")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config", default=str(HERE / "english.json"))
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument(
        "--view", type=int, default=3, help="seeds per matchup to put in the viewer"
    )
    args = parser.parse_args()

    jobs = []
    for a, b in LADDER:
        for seed in range(args.seed, args.seed + args.games):
            jobs += [(seed, a, b), (seed, b, a)]

    started = time.perf_counter()
    with ProcessPoolExecutor(
        args.workers, initializer=_init, initargs=(args.config,)
    ) as pool:
        games = list(pool.map(play_game, jobs))
    wall = time.perf_counter() - started

    table = []
    for a, b in LADDER:
        mine = [g for g in games if set(g["players"]) == {a, b}]
        table.append(summarize(mine, a, b))
    moves = sum(len(g["frames"]) for g in games)
    speed = {
        "games": len(games),
        "wall_s": round(wall, 1),
        "games_per_s": round(len(games) / wall, 2),
        "ms_per_movegen": round(sum(g["gen_ms"] for g in games) / moves, 1),
        "workers": args.workers,
    }

    print(f"{'matchup':<18}{'games':>6}{'win rate':>10}{'±95%':>7}{'spread':>8}")
    for row in table:
        name = f"{row['a']} vs {row['b']}"
        print(
            f"{name:<18}{row['games']:>6}{row['win_rate']:>10.3f}"
            f"{row['ci95']:>7.3f}{row['spread']:>8.1f}"
        )
    print(
        f"\n{speed['games']} games in {speed['wall_s']}s on {speed['workers']} "
        f"workers: {speed['games_per_s']} games/s, "
        f"{speed['ms_per_movegen']} ms per move generation"
    )

    out = HERE / "out"
    out.mkdir(exist_ok=True)
    rs = load(args.config)
    data = {
        "ruleset": rs.name,
        "premiums": rs.premiums,
        "values": rs.values,
        "table": table,
        "speed": speed,
        "games": games,
    }
    (out / "records.json").write_text(json.dumps(data))
    shown = [g for g in games if g["seed"] < args.seed + args.view]
    viewer.write(out / "viewer.html", {**data, "games": shown})
    print(f"wrote {out / 'records.json'} and {out / 'viewer.html'}")


if __name__ == "__main__":
    main()
