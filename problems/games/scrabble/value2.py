"""N2: what the network reads (letters, hooks) and what it predicts (win, spread).

    T="uv run --with numpy --with torch --index https://download.pytorch.org/whl/cpu python -m"
    $T scrabble.value2 prep                       # board extras for N1's positions, cached
    $T scrabble.value2 train --inputs v1          # N1's planes, two heads
    $T scrabble.value2 train --inputs v2          # plus letters and hook squares
    $T scrabble.value2 duel --who v2-win --against steady --first 620000

Same 450k positions as N1, same held-out games. Two networks with the same
trunk: v1 reads N1's board planes, v2 adds which letter is on each square and,
for each empty square, which letters hook there across and down. Each network
has two heads, trained together: the spread to come (N1's target) and the
chance of winning (win, tie = 0.5). So four players, a 2x2: inputs x head.
The only true symmetry of the board is the transpose, which also swaps across
and down; training uses it.
"""

import argparse
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scrabble import board, fastslow, value
from scrabble.fastslow import BASE, fast
from scrabble.game import Game
from scrabble.ruleset import BLANK
from scrabble.value import STEADY, after, shortlist

HERE = Path(__file__).parent
OUT = HERE / "rounds" / "value2"
SRC = HERE / "rounds" / "value" / "positions.jsonl"


def letters(rs) -> list[str]:
    """The ruleset's letters, so another language gets its own alphabet."""
    return sorted(set(rs.full_set()) - {BLANK})


# --- board extras -----------------------------------------------------------

def extras(grid: str, rs) -> tuple[bytes, bytes]:
    """Letter ids (0 empty, 1..L a tile, L+1..2L a blank played as that letter),
    and for each square the number of letters that hook there: down words
    (for across plays) then across words (for down plays). 0 where no
    neighbour or filled."""
    n, alpha = rs.size, letters(rs)
    ids = bytearray(n * n)
    cells = [[None] * n for _ in range(n)]
    for k, ch in enumerate(grid):
        if ch != ".":
            up = ch.upper()
            cells[k // n][k % n] = (up, ch != up)
            ids[k] = alpha.index(up) + 1 + (len(alpha) if ch != up else 0)
    hooks = bytearray(2 * n * n)
    flipped = [list(col) for col in zip(*cells, strict=True)]
    for plane, g in ((0, cells), (1, flipped)):
        for r in range(n):
            for c, allowed in enumerate(board._cross_sets(rs, g, r)):
                if allowed:
                    rr, cc = (r, c) if plane == 0 else (c, r)
                    hooks[plane * n * n + rr * n + cc] = len(allowed)
    return bytes(ids), bytes(hooks)


def _prep_game(line: str) -> dict:
    game = json.loads(line)
    rs = fastslow._rs
    out = []
    for row in game["rows"]:
        ids, hooks = extras(row["grid"], rs)
        out.append((ids.hex(), hooks.hex()))
    return {"seed": game["seed"], "extras": out}


def prep() -> None:
    import numpy as np

    lines = [x for x in SRC.read_text().splitlines() if x.strip()]
    games = {}
    with ProcessPoolExecutor(os.cpu_count(), initializer=fastslow._init, initargs=({},)) as pool:
        for n, f in enumerate(as_completed([pool.submit(_prep_game, x) for x in lines]), 1):
            r = f.result()
            games[r["seed"]] = r["extras"]
            if n % 2000 == 0:
                print(f"    {n}/{len(lines)} games", flush=True)
    rows = [(json.loads(x)["seed"], k) for x in lines for k in range(len(json.loads(x)["rows"]))]
    ids = np.frombuffer(b"".join(bytes.fromhex(games[s][k][0]) for s, k in rows), dtype=np.uint8)
    hooks = np.frombuffer(b"".join(bytes.fromhex(games[s][k][1]) for s, k in rows), dtype=np.uint8)
    np.savez(OUT / "extras.npz", ids=ids.reshape(len(rows), -1), hooks=hooks.reshape(len(rows), 2, -1),
             seeds=np.array([s for s, _ in rows]))
    print(f"{len(rows)} positions prepared", flush=True)


# --- tensors ----------------------------------------------------------------

def _vec(row):
    """Leave, unseen, bag, lead, and N1's five features: what both networks get."""
    import numpy as np
    from collections import Counter

    v = np.zeros(27 + 27 + 2 + len(value.LINEAR), dtype=np.float32)
    for t, c in Counter(row["leave"]).items():
        v[value.TILES.index(t)] = c
    for t, c in Counter(row["unseen"]).items():
        v[27 + value.TILES.index(t)] = c / 10
    v[54] = row["bag"] / 100
    v[55] = row["lead"] / 100
    v[56:] = row["x"]
    return v


def planes(ids, hooks, rs, inputs: str):
    """Board planes from letter ids and hooks, built per batch (torch tensors).
    v1: N1's seven planes. v2: those, hooks across/down (any, how many), and ids
    for the letter embedding."""
    import torch

    n = rs.size
    alpha = letters(rs)
    worth = torch.zeros(2 * len(alpha) + 1)
    for k, t in enumerate(alpha):
        worth[k + 1] = rs.value(t) / 10  # a blank (k + 1 + len) is worth nothing
    premium = torch.tensor([[ord(ch) for ch in line] for line in rs.premiums])
    b = ids.view(-1, n, n).long()
    filled = (b > 0).float()
    empty = 1 - filled
    near = torch.zeros_like(filled)
    near[:, 1:] += filled[:, :-1]; near[:, :-1] += filled[:, 1:]
    near[:, :, 1:] += filled[:, :, :-1]; near[:, :, :-1] += filled[:, :, 1:]
    out = [filled, worth[b]] + [empty * (premium == ord(code)).float() for code in "TDtd"] \
        + [empty * (near > 0).float()]
    if inputs == "v2":
        h = hooks.view(-1, 2, n, n).float()
        out += [(h[:, 0] > 0).float(), h[:, 0] / len(alpha), (h[:, 1] > 0).float(), h[:, 1] / len(alpha)]
    return torch.stack(out, 1), b


def transpose(p, b, inputs: str):
    """The board's one symmetry. Across and down swap, so the hook planes swap."""
    p = p.transpose(2, 3)
    if inputs == "v2":
        p = p[:, [0, 1, 2, 3, 4, 5, 6, 9, 10, 7, 8]]
    return p, b.transpose(1, 2)


def net(inputs: str, rs):
    import torch
    from torch import nn

    alpha = letters(rs)
    width = 7 + (4 + 8 if inputs == "v2" else 0)
    nvec = 27 + 27 + 2 + len(value.LINEAR)

    class Value(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Embedding(2 * len(alpha) + 1, 8) if inputs == "v2" else None
            self.conv = nn.Sequential(
                nn.Conv2d(width, 48, 3, padding=1), nn.ReLU(),
                nn.Conv2d(48, 48, 3, padding=1), nn.ReLU(),
                nn.Conv2d(48, 48, 3, padding=1), nn.ReLU(),
                nn.Conv2d(48, 48, 3, padding=1), nn.ReLU(),
            )
            self.head = nn.Sequential(nn.Linear(96 + nvec, 96), nn.ReLU(), nn.Linear(96, 2))

        def forward(self, p, b, vec):
            if self.embed is not None:
                p = torch.cat([p, self.embed(b).permute(0, 3, 1, 2)], 1)
            h = self.conv(p)
            out = self.head(torch.cat([h.mean((2, 3)), h.amax((2, 3)), vec], 1))
            return out[:, 0] * 50, out[:, 1]  # spread to come, win logit

    return Value()


# --- training ---------------------------------------------------------------

def train(inputs: str, epochs: int) -> None:
    import numpy as np
    import torch

    torch.manual_seed(0)
    rs = fastslow._rs
    cache = np.load(OUT / "extras.npz")
    rows = [r for x in SRC.read_text().splitlines() if x.strip() for r in json.loads(x)["rows"]]
    seeds = cache["seeds"]
    held = seeds % 10 == 0  # N1's split: a tenth of the games
    ids = torch.from_numpy(cache["ids"])
    hooks = torch.from_numpy(cache["hooks"])
    vec = torch.from_numpy(np.stack([_vec(r) for r in rows]))
    y = torch.tensor([r["y"] for r in rows], dtype=torch.float32)
    final = y + torch.tensor([r["lead"] for r in rows], dtype=torch.float32)
    win = (final > 0).float() + 0.5 * (final == 0).float()
    tr = torch.from_numpy(np.flatnonzero(~held))
    va = torch.from_numpy(np.flatnonzero(held))
    print(f"{inputs}: {len(tr)} positions to fit on, {len(va)} held out", flush=True)

    model = net(inputs, rs)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    bce = torch.nn.BCEWithLogitsLoss()
    best = math.inf
    for epoch in range(epochs):
        model.train()
        order = tr[torch.randperm(len(tr))]
        for s in range(0, len(order), 512):
            idx = order[s:s + 512]
            p, b = planes(ids[idx], hooks[idx], rs, inputs)
            if torch.rand(()) < 0.5:
                p, b = transpose(p, b, inputs)
            spread, logit = model(p, b, vec[idx])
            loss = torch.mean((spread - y[idx]) ** 2) / 4000 + bce(logit, win[idx])
            opt.zero_grad(); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            mse, ll = 0.0, 0.0
            for s in range(0, len(va), 4096):
                idx = va[s:s + 4096]
                p, b = planes(ids[idx], hooks[idx], rs, inputs)
                spread, logit = model(p, b, vec[idx])
                mse += float(torch.sum((spread - y[idx]) ** 2))
                ll += float(torch.nn.functional.binary_cross_entropy_with_logits(logit, win[idx], reduction="sum"))
            mse, ll = mse / len(va), ll / len(va)
        score = mse / 4000 + ll
        if score < best:
            best = score
            torch.save(model.state_dict(), OUT / f"net_{inputs}.pt")
        line = f"    {inputs} epoch {epoch + 1}: held-out spread mse {mse:.1f}, win log-loss {ll:.4f}"
        print(line, flush=True)
        with (OUT / "train.txt").open("a") as out:
            out.write(line + "\n")
    base = float(torch.mean((win[va] - win[tr].mean()) ** 2))
    p0 = float(win[tr].mean())
    ll0 = -float(torch.mean(win[va] * math.log(p0) + (1 - win[va]) * math.log(1 - p0)))
    with (OUT / "train.txt").open("a") as out:
        out.write(f"{inputs}: win log-loss of the base rate alone {ll0:.4f} (brier {base:.4f})\n")


# --- playing ----------------------------------------------------------------

_model, _inputs, _head = None, None, None


def _init_player(who: str) -> None:
    """who: '<inputs>-<head>', e.g. 'v2-win'."""
    global _model, _inputs, _head
    import torch

    fastslow._init({})
    torch.set_num_threads(1)
    _inputs, _head = who.split("-")
    _model = net(_inputs, fastslow._rs)
    _model.load_state_dict(torch.load(OUT / f"net_{_inputs}.pt"))
    _model.eval()


def choose(g: Game, moves) -> int:
    import numpy as np
    import torch

    rs = g.rs
    picks = shortlist(g, moves)
    rows = [after(g, moves[i]) for i in picks]
    ex = [extras(r["grid"], rs) for r in rows]
    ids = torch.from_numpy(np.frombuffer(b"".join(e[0] for e in ex), dtype=np.uint8).copy())
    hooks = torch.from_numpy(np.frombuffer(b"".join(e[1] for e in ex), dtype=np.uint8).copy())
    p, b = planes(ids, hooks, rs, _inputs)
    with torch.no_grad():
        spread, logit = _model(p, b, torch.from_numpy(np.stack([_vec(r) for r in rows])))
    if _head == "win":
        totals = logit.tolist()
    else:
        totals = [r["lead"] + v for r, v in zip(rows, spread.tolist(), strict=True)]
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


def duel(who: str, against: str, first: int, bags: int) -> None:
    saved = OUT / f"duel_{who}_vs_{against}_{first}.jsonl"
    games = [json.loads(x) for x in saved.read_text().splitlines() if x.strip()] if saved.exists() else []
    done = {(x["seed"], x["seat"]) for x in games}
    jobs = [(first + k, seat, against) for k in range(bags) for seat in (0, 1) if (first + k, seat) not in done]
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init_player, initargs=(who,)) as pool, \
            saved.open("a") as out:
        for f in as_completed([pool.submit(duel_game, *job) for job in jobs]):
            games.append(f.result())
            out.write(json.dumps(games[-1]) + "\n")
            out.flush()
            if len(games) % 200 == 0:
                print(f"    {who} vs {against} @{first}: {value.summary(games)}", flush=True)
    line = f"{who} vs {against} @{first}: {value.summary(games)}"
    print(line, flush=True)
    with (OUT / "duels.txt").open("a") as out:
        out.write(line + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["prep", "train", "duel"])
    parser.add_argument("--inputs", default="v2", choices=["v1", "v2"])
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--who", default="v2-win")
    parser.add_argument("--against", default="steady", choices=["fast_0", "steady"])
    parser.add_argument("--first", type=int, default=fastslow.CHECK_FIRST)
    parser.add_argument("--bags", type=int, default=1000)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.what == "prep":
        fastslow._init({})
        prep()
    elif args.what == "train":
        fastslow._init({})
        train(args.inputs, args.epochs)
    else:
        duel(args.who, args.against, args.first, args.bags)


if __name__ == "__main__":
    main()
