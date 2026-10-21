"""Y1: score each decision, not each game.

    T="uv run --with numpy --with torch --index https://download.pytorch.org/whl/cpu python -m"
    $T scrabble.oracle label --positions 1000             # slow; saved as they finish
    $T scrabble.oracle score fast_0 steady linear net slow

A fixed set of positions from bags nothing else uses. In each, every candidate
move (steady's top ten, plus fast_0's choice) is played out to the end of the
game in the same invented worlds, steady on both sides, and valued by how
often it won. A player is scored by the value of the move it picks, averaged
over the positions: the luck of the draw is the same for every player, so
small differences show with far fewer trials than duels need.
"""

import argparse
import json
import math
import os
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from statistics import mean

from scrabble import fastslow, value
from scrabble.fastslow import BASE, fast
from scrabble.game import Game
from scrabble.simulate import world
from scrabble.value import STEADY, shortlist

HERE = Path(__file__).parent
OUT = HERE / "rounds" / "oracle"
FIRST = 900_000  # bags nothing else uses
WORLDS = 24
SLOW = {"keep": 6, "samples": 20, "plies": 1, "weights": STEADY}


def walk(seed: int) -> list[int]:
    """The moves of one exploring steady self-play game (as in N1's data)."""
    g = Game(fastslow._rs, seed)
    rng = random.Random(f"explore:{seed}")
    history = []
    while not g.over:
        moves = g.legal()
        picks = shortlist(g, moves)
        i = picks[rng.randrange(min(5, len(picks)))] if rng.random() < value.EXPLORE else picks[0]
        history.append(i)
        g.apply(moves[i])
    return history


def replay(seed: int, history: list[int]) -> Game:
    g = Game(fastslow._rs, seed)
    for i in history:
        g.apply(g.legal()[i])
    return g


def finish(g: Game, p: int) -> tuple[float, float]:
    while not g.over:
        moves = g.legal()
        g.apply(moves[fast(g, moves, STEADY)])
    ahead = g.scores[p] - g.scores[1 - p]
    return (1.0 if ahead > 0 else 0.5 if ahead == 0 else 0.0), float(ahead)


def label(seed: int) -> dict:
    history = walk(seed)
    rng = random.Random(f"turn:{seed}")
    while True:
        turn = rng.randrange(len(history))
        g = replay(seed, history[:turn])
        moves = g.legal()
        cands = shortlist(g, moves)
        if fast(g, moves, BASE) not in cands:
            cands.append(fast(g, moves, BASE))
        if len(cands) > 1:
            break
    p = g.to_move
    win = [[] for _ in cands]
    spread = [[] for _ in cands]
    for w in range(WORLDS if g.bag else 1):  # nothing hidden: one world is the real one
        world_seed = random.Random(f"{seed}:{w}").randrange(2**31)
        for k, i in enumerate(cands):
            x = world(g, p, random.Random(world_seed))
            x.apply(moves[i])
            a, b = finish(x, p)
            win[k].append(a)
            spread[k].append(b)
    return {"seed": seed, "turn": turn, "history": history[:turn], "bag": len(g.bag),
            "cands": cands, "win": win, "spread": spread}


def load(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def label_all(positions: int) -> None:
    saved = OUT / "positions.jsonl"
    rows = load(saved)
    done = {x["seed"] for x in rows}
    seeds = [FIRST + k for k in range(positions) if FIRST + k not in done]
    with ProcessPoolExecutor(os.cpu_count(), initializer=fastslow._init, initargs=({},)) as pool, \
            saved.open("a") as out:
        for f in as_completed([pool.submit(label, s) for s in seeds]):
            rows.append(f.result())
            out.write(json.dumps(rows[-1]) + "\n")
            out.flush()
            if len(rows) % 50 == 0:
                print(f"    {len(rows)}/{positions} positions", flush=True)
    print(noise(rows), flush=True)


def noise(rows: list[dict]) -> str:
    """Split each position's worlds in two: do the halves agree on the best move?"""
    agree, n = 0, 0
    for r in rows:
        if r["bag"] == 0:
            continue
        even = [mean(w[0::2]) + mean(s[0::2]) / 1000 for w, s in zip(r["win"], r["spread"], strict=True)]
        odd = [mean(w[1::2]) + mean(s[1::2]) / 1000 for w, s in zip(r["win"], r["spread"], strict=True)]
        agree += even.index(max(even)) == odd.index(max(odd))
        n += 1
    return f"oracle noise: the two halves of the worlds pick the same best move in {agree}/{n} positions"


# --- scoring players --------------------------------------------------------

def _init_scorer(who: str) -> None:
    if who in ("linear", "net"):
        value._init_player(who)
    elif who.startswith(("v1-", "v2-")):
        from scrabble import value2
        value2._init_player(who)
    elif who.startswith(("s2-", "flat-")):
        from scrabble import search
        search._init_player(who)
    else:
        fastslow._init(SLOW)


def pick(who: str, g: Game, moves, seed: int) -> int:
    if who == "fast_0":
        return fast(g, moves, BASE)
    if who == "steady":
        return fast(g, moves, STEADY)
    if who == "slow":
        return fastslow.slow(g, moves, seed * 1000 + g.turn)
    if who.startswith(("v1-", "v2-")):
        from scrabble import value2
        return value2.choose(g, moves)
    if who.startswith(("s2-", "flat-")):
        from scrabble import search
        return search.pick(g, moves, seed)
    return value.choose(g, moves)


def score_one(who: str, r: dict) -> dict:
    g = replay(r["seed"], r["history"])
    i = pick(who, g, g.legal(), r["seed"])
    if i not in r["cands"]:
        return {"seed": r["seed"], "win": None, "spread": None}
    k = r["cands"].index(i)
    return {"seed": r["seed"], "win": mean(r["win"][k]), "spread": mean(r["spread"][k])}


def score(who: str, rows: list[dict]) -> dict[int, dict]:
    saved = OUT / f"score_{who}.jsonl"
    got = {x["seed"]: x for x in load(saved)}
    todo = [r for r in rows if r["seed"] not in got]
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init_scorer, initargs=(who,)) as pool, \
            saved.open("a") as out:
        for f in as_completed([pool.submit(score_one, who, r) for r in todo]):
            x = f.result()
            got[x["seed"]] = x
            out.write(json.dumps(x) + "\n")
            out.flush()
    return got


def _ms(xs: list[float]) -> str:
    m = sum(xs) / len(xs)
    se = math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1) / len(xs))
    return f"{m:+.4f} ±{2 * se:.4f}" if abs(m) < 2 else f"{m:+.2f} ±{2 * se:.2f}"


def report(players: list[str]) -> None:
    rows = load(OUT / "positions.jsonl")
    best = {r["seed"]: (max(mean(w) for w in r["win"]), max(mean(s) for s in r["spread"])) for r in rows}
    scores = {who: score(who, rows) for who in players}
    lines = [f"{len(rows)} positions, {WORLDS} worlds each"]
    for who in players:
        xs = [x for x in scores[who].values() if x["win"] is not None]
        lines.append(f"{who}: win regret {_ms([best[x['seed']][0] - x['win'] for x in xs])},"
                     f" spread regret {_ms([best[x['seed']][1] - x['spread'] for x in xs])}"
                     f" ({len(xs)} scored, {len(scores[who]) - len(xs)} off the list)")
    for n, a in enumerate(players):
        for b in players[n + 1:]:
            both = [s for s in scores[a] if scores[a][s]["win"] is not None and scores[b][s]["win"] is not None]
            dw = [scores[a][s]["win"] - scores[b][s]["win"] for s in both]
            ds = [scores[a][s]["spread"] - scores[b][s]["spread"] for s in both]
            lines.append(f"{a} - {b}: win {_ms(dw)}, spread {_ms(ds)} ({len(both)} positions)")
    text = "\n".join(lines)
    print(text, flush=True)
    (OUT / "report.txt").write_text(text + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["label", "score"])
    parser.add_argument("players", nargs="*", default=["fast_0", "steady", "linear", "net", "slow"])
    parser.add_argument("--positions", type=int, default=1000)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.what == "label":
        fastslow._init({})
        label_all(args.positions)
    else:
        report(args.players)


if __name__ == "__main__":
    main()
