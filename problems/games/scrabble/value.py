"""N1: a learned value of the position, in place of six hand-picked features.

    T="uv run --with numpy --with torch --index https://download.pytorch.org/whl/cpu python -m"
    $T scrabble.value gen --games 18000      # self-play positions, saved as they finish
    $T scrabble.value train                  # the network and the linear control, same rows
    $T scrabble.value duel --who net         # vs fast_0 and steady on the H3 check games

Both players choose among steady's top ten moves by points ahead after the
move plus V(position after the move). V is learned from what happened next:
the final spread minus the spread just after the move (a Monte Carlo target).
The network reads the board; the linear control reads the six features. Same
rows, same target, same top ten, so a difference is the representation's.
"""

import argparse
import json
import math
import os
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scrabble import fastslow
from scrabble.fastslow import BASE, CHECK_FIRST, FEATURES, fast, features, key
from scrabble.game import Game
from scrabble.ruleset import BLANK

HERE = Path(__file__).parent
OUT = HERE / "rounds" / "value"
GEN_FIRST = 700_000  # bags nothing else uses; the check games stay unseen
TOP, EXPLORE = 10, 0.15
STEADY = {n: v[0] for n, v in json.loads((fastslow.OUT / "weights.json").read_text()).items()}
TILES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ?"
LINEAR = [n for n in FEATURES if n != "score"]  # score is already in the lead


# --- positions ------------------------------------------------------------

def after(g: Game, move) -> dict:
    """The position after `move`, seen by the player who made it."""
    p = g.to_move
    grid = [list(row) for row in g.grid]
    for r, c, t, b in move.tiles:
        grid[r][c] = (t, b)
    cells = "".join(
        "." if cell is None else cell[0].lower() if cell[1] else cell[0]
        for row in grid for cell in row
    )
    seen = Counter(BLANK if ch.islower() else ch for ch in cells if ch != ".")
    seen.update(move.leave)
    unseen = Counter(g.rs.full_set()) - seen
    lead = g.scores[p] - g.scores[1 - p] + move.score
    return {
        "grid": cells, "leave": "".join(move.leave),
        "unseen": "".join(sorted(unseen.elements())),
        "bag": len(g.bag), "lead": lead,
        "x": [features(g, move)[n] for n in LINEAR],
    }


def shortlist(g: Game, moves) -> list[int]:
    keys = [key(g, m, STEADY) for m in moves]
    return sorted(range(len(moves)), key=lambda i: (-keys[i], i))[:TOP]


def gen_game(seed: int) -> dict:
    """Steady against itself, sometimes taking one of its other top five."""
    g = Game(fastslow._rs, seed)
    rng = random.Random(f"explore:{seed}")
    rows = []
    while not g.over:
        moves = g.legal()
        picks = shortlist(g, moves)
        i = picks[rng.randrange(min(5, len(picks)))] if rng.random() < EXPLORE else picks[0]
        rows.append((g.to_move, after(g, moves[i])))
        g.apply(moves[i])
    for p, row in rows:
        row["y"] = (g.scores[p] - g.scores[1 - p]) - row["lead"]
    return {"seed": seed, "rows": [row for _, row in rows]}


def gen(games: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    saved = OUT / "positions.jsonl"
    done = set()
    if saved.exists():
        done = {json.loads(x)["seed"] for x in saved.read_text().splitlines() if x.strip()}
    seeds = [GEN_FIRST + k for k in range(games) if GEN_FIRST + k not in done]
    with ProcessPoolExecutor(os.cpu_count(), initializer=fastslow._init, initargs=({},)) as pool, \
            saved.open("a") as out:
        for n, f in enumerate(as_completed([pool.submit(gen_game, s) for s in seeds]), 1):
            out.write(json.dumps(f.result()) + "\n")
            out.flush()
            if n % 500 == 0:
                print(f"    {n + len(done)}/{games} games", flush=True)


# --- the network and the control -----------------------------------------

def encode(rows, rs):
    """Board planes and a vector, both small enough for a few hundred thousand rows."""
    import numpy as np

    n, size = len(rows), len(rs.premiums)
    premium = np.array([[ch for ch in line] for line in rs.premiums])
    planes = np.zeros((n, 7, size, size), dtype=np.float32)
    vec = np.zeros((n, 27 + 27 + 2 + len(LINEAR)), dtype=np.float32)
    worth = np.zeros(256, dtype=np.float32)  # a blank (lower case) is worth nothing
    for t in TILES[:-1]:
        worth[ord(t)] = rs.value(t) / 10
    for k, row in enumerate(rows):
        board = np.frombuffer(row["grid"].encode(), dtype=np.uint8).reshape(size, size)
        filled = board != ord(".")
        planes[k, 0] = filled
        planes[k, 1] = worth[board]
        empty = ~filled
        near = np.zeros_like(filled)
        near[1:] |= filled[:-1]; near[:-1] |= filled[1:]
        near[:, 1:] |= filled[:, :-1]; near[:, :-1] |= filled[:, 1:]
        for j, code in enumerate("TDtd"):
            planes[k, 2 + j] = empty & (premium == code)
        planes[k, 6] = empty & near
        for t, c in Counter(row["leave"]).items():
            vec[k, TILES.index(t)] = c
        for t, c in Counter(row["unseen"]).items():
            vec[k, 27 + TILES.index(t)] = c / 10
        vec[k, 54] = row["bag"] / 100
        vec[k, 55] = row["lead"] / 100
        vec[k, 56:] = row["x"]
    return planes, vec


def net():
    import torch
    from torch import nn

    class Value(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(7, 32, 3, padding=1), nn.ReLU(),
                nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(),
                nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(),
            )
            self.head = nn.Sequential(nn.Linear(64 + 56 + len(LINEAR), 64), nn.ReLU(), nn.Linear(64, 1))

        def forward(self, planes, vec):
            h = self.conv(planes)
            pooled = torch.cat([h.mean((2, 3)), h.amax((2, 3))], 1)
            return self.head(torch.cat([pooled, vec], 1)).squeeze(1)

    return Value()


def train(epochs: int) -> None:
    import numpy as np
    import torch

    rs = fastslow._rs
    games = [json.loads(x) for x in (OUT / "positions.jsonl").read_text().splitlines() if x.strip()]
    held = [g for g in games if g["seed"] % 10 == 0]  # a tenth of the games, never trained on
    fit_on = [g for g in games if g["seed"] % 10 != 0]
    tr = [r for g in fit_on for r in g["rows"]]
    va = [r for g in held for r in g["rows"]]
    ytr = np.array([r["y"] for r in tr], dtype=np.float32)
    yva = np.array([r["y"] for r in va], dtype=np.float32)
    print(f"{len(tr)} positions to fit on, {len(va)} held out ({len(held)} games)", flush=True)

    # The control: six features (score sits in the lead), plus a constant.
    def lin_x(rows):
        return np.array([r["x"] + [1.0] for r in rows])
    w, *_ = np.linalg.lstsq(lin_x(tr), ytr, rcond=None)
    lin_mse = float(np.mean((lin_x(va) @ w - yva) ** 2))
    base_mse = float(np.mean((ytr.mean() - yva) ** 2))
    (OUT / "linear.json").write_text(json.dumps(dict(zip(LINEAR + ["const"], map(float, w), strict=True)), indent=1))

    ptr, vtr = map(torch.from_numpy, encode(tr, rs))
    pva, vva = map(torch.from_numpy, encode(va, rs))
    ytr_t, yva_t = torch.from_numpy(ytr), torch.from_numpy(yva)
    model = net()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    best = math.inf
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(tr))
        for s in range(0, len(tr), 512):
            idx = order[s:s + 512]
            loss = torch.mean((model(ptr[idx], vtr[idx]) - ytr_t[idx]) ** 2)
            opt.zero_grad(); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            pred = torch.cat([model(pva[s:s + 4096], vva[s:s + 4096]) for s in range(0, len(va), 4096)])
            mse = float(torch.mean((pred - yva_t) ** 2))
        if mse < best:
            best = mse
            torch.save(model.state_dict(), OUT / "net.pt")
        print(f"    epoch {epoch + 1}: held-out mse {mse:.1f}", flush=True)
    line = (f"held-out mse: mean only {base_mse:.1f}, linear {lin_mse:.1f}, net {best:.1f}"
            f" | {len(tr)} positions, {len(va)} held out")
    print(line, flush=True)
    (OUT / "train.txt").write_text(line + "\n")


# --- playing with a value ---------------------------------------------------

_value = None


def _init_player(who: str) -> None:
    global _value
    fastslow._init({})
    if who == "linear":
        w = json.loads((OUT / "linear.json").read_text())
        _value = lambda rows: [sum(w[n] * x for n, x in zip(LINEAR, r["x"], strict=True)) + w["const"] for r in rows]
    else:
        import torch

        torch.set_num_threads(1)
        model = net()
        model.load_state_dict(torch.load(OUT / "net.pt"))
        model.eval()

        def v(rows):
            planes, vec = encode(rows, fastslow._rs)
            with torch.no_grad():
                return model(torch.from_numpy(planes), torch.from_numpy(vec)).tolist()
        _value = v


def choose(g: Game, moves) -> int:
    picks = shortlist(g, moves)
    rows = [after(g, moves[i]) for i in picks]
    totals = [r["lead"] + v for r, v in zip(rows, _value(rows), strict=True)]
    return picks[totals.index(max(totals))]


def duel_game(seed: int, seat: int, against: str) -> dict:
    g = Game(fastslow._rs, seed)
    other = BASE if against == "fast_0" else STEADY
    while not g.over:
        moves = g.legal()
        i = choose(g, moves) if g.to_move == seat else fast(g, moves, other)
        g.apply(moves[i])
    mine, theirs = g.scores[seat], g.scores[1 - seat]
    return {"seed": seed, "seat": seat, "against": against,
            "points": 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0,
            "spread": mine - theirs}


def duel(who: str, against: str, bags: int, first: int = CHECK_FIRST) -> None:
    saved = OUT / (f"duel_{who}_vs_{against}.jsonl" if first == CHECK_FIRST else f"duel_{who}_vs_{against}_{first}.jsonl")
    games = [json.loads(x) for x in saved.read_text().splitlines() if x.strip()] if saved.exists() else []
    done = {(x["seed"], x["seat"]) for x in games}
    jobs = [(first + k, seat, against) for k in range(bags) for seat in (0, 1)
            if (first + k, seat) not in done]
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init_player, initargs=(who,)) as pool, \
            saved.open("a") as out:
        for f in as_completed([pool.submit(duel_game, *job) for job in jobs]):
            games.append(f.result())
            out.write(json.dumps(games[-1]) + "\n")
            out.flush()
            if len(games) % 100 == 0:
                print(f"    {who} vs {against}: {summary(games)}", flush=True)
    line = f"{who} vs {against}{'' if first == CHECK_FIRST else f' @{first}'}: {summary(games)}"
    print(line, flush=True)
    with (OUT / "duels.txt").open("a") as out:
        out.write(line + "\n")


def summary(games) -> str:
    n = len(games)
    rate = sum(x["points"] for x in games) / n
    s = [x["spread"] for x in games]
    m = sum(s) / n
    se = math.sqrt(sum((x - m) ** 2 for x in s) / max(1, n - 1) / n)
    return (f"win {rate:.3f} ±{1.96 * math.sqrt(rate * (1 - rate) / n):.3f},"
            f" spread {m:+.1f} ±{2 * se:.1f} ({n} games)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["gen", "train", "duel"])
    parser.add_argument("--games", type=int, default=18000)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--who", default="net", choices=["net", "linear"])
    parser.add_argument("--against", default="fast_0", choices=["fast_0", "steady"])
    parser.add_argument("--bags", type=int, default=1000)
    parser.add_argument("--first", type=int, default=CHECK_FIRST)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.what == "gen":
        gen(args.games)
    elif args.what == "train":
        fastslow._init({})
        train(args.epochs)
    else:
        duel(args.who, args.against, args.bags, args.first)


if __name__ == "__main__":
    main()
