"""S2: the network inside the slow player.

The slow player (Maven-style) plays every candidate into invented worlds and
judges the result with a fixed rule. Here the network does both jobs it is
good at, as in AlphaGo and Gumbel AlphaZero:
- it proposes: only its top K moves are simulated;
- it judges: each simulation stops after a couple of plies and the network
  values the position, instead of playing to the end;
- the budget goes where it matters: sequential halving gives every candidate
  a few worlds, drops the worse half, and spends the rest on the survivors.
Every candidate faces the same worlds, so their differences are the move's.

Players (for oracle.py and duels): 's2-<arm>-<budget>' with halving, and
'flat-<arm>-<budget>' spreading the same budget evenly (the ablation), where
<arm> is a value2 player such as v2-win.

S3 ('s3-<leaf>-<budget>[-<plies>][-k<K>][-n<n0>]', 's3e-...' adds the exact
endgame; n0 shrinks each candidate's rollout mean toward its static value): the
Maven/BestBot shape with HastyBot's learned leaves. Shortlist, prior and
rollouts use the klv rule; the leaf is either the network ('net', v1-spread)
or points plus leaves ('klv'), or that turned into a win chance by tiles
left ('wp', BestBot's win table, fitted by `leaves winp`). Once the bag is empty, 's3e' asks Macondo's
solver for the best move instead of simulating.
"""

import math
import random

import numpy as np

from scrabble import fastslow, leaves, value2
from scrabble.fastslow import fast
from scrabble.game import Game
from scrabble.simulate import world
from scrabble.value import STEADY, after, shortlist

K, PLIES = 8, 2  # candidates; plies simulated before the network judges


def _value(rows) -> list[float]:
    """The network's value of afterstates, each from the mover's side: the
    win chance (win head) or the final spread (spread head)."""
    import torch

    rs = fastslow._rs
    ex = [value2.extras(r["grid"], rs) for r in rows]
    ids = torch.from_numpy(np.frombuffer(b"".join(e[0] for e in ex), dtype=np.uint8).copy())
    hooks = torch.from_numpy(np.frombuffer(b"".join(e[1] for e in ex), dtype=np.uint8).copy())
    p, b = value2.planes(ids, hooks, rs, value2._inputs)
    with torch.no_grad():
        spread, logit = value2._model(p, b, torch.from_numpy(np.stack([value2._vec(r) for r in rows])))
    if value2._head == "win":
        return torch.sigmoid(logit).tolist()
    return [r["lead"] + v for r, v in zip(rows, spread.tolist(), strict=True)]


def _flip(v: float) -> float:
    return 1 - v if value2._head == "win" else -v


def _policy(g: Game, moves) -> int:
    return leaves.klv(g, moves) if _cfg.get("klv") else fast(g, moves, STEADY)


def rollout(g: Game, p: int, move, world_seed: int) -> float:
    """Play `move` in one invented world, let the policy play PLIES more, and
    return the leaf's value, for p, of the last position."""
    w = world(g, p, random.Random(world_seed))
    row, mover = after(w, move), p
    w.apply(move)
    for _ in range(_cfg.get("plies", PLIES)):
        if w.over:
            break
        replies = w.legal()
        m = replies[_policy(w, replies)]
        row, mover = after(w, m), w.to_move
        w.apply(m)
    if _cfg.get("leaf") in ("klv", "wp"):
        ahead = w.scores[p] - w.scores[1 - p]
        if w.over:
            return float(ahead) if _cfg["leaf"] == "klv" else 1.0 if ahead > 0 else 0.5 if ahead == 0 else 0.0
        if w.bag:
            ahead += leaves.value(w.racks[p]) - leaves.value(w.racks[1 - p])
        if _cfg["leaf"] == "klv":
            return float(ahead)
        # The leaf is an afterstate of p's move when PLIES is even, else of the opponent's.
        return leaves.winp(ahead, len(w.bag)) if mover == p else 1 - leaves.winp(-ahead, len(w.bag))
    if w.over:
        ahead = w.scores[p] - w.scores[1 - p]
        if value2._head == "win":
            return 1.0 if ahead > 0 else 0.5 if ahead == 0 else 0.0
        return float(ahead)
    v = _value([row])[0]
    return v if mover == p else _flip(v)


def choose(g: Game, moves, seed: int, budget: int, halving: bool) -> int:
    if len(moves) == 1:
        return 0
    if _cfg.get("klv"):
        eq = [leaves.equity(g, m) for m in moves]
        picks = sorted(range(len(moves)), key=lambda i: (-eq[i], i))[:10]
    else:
        picks = shortlist(g, moves)
    if _cfg.get("leaf") in ("klv", "wp"):
        prior = [eq[i] for i in picks]
    else:
        prior = _value([after(g, moves[i]) for i in picks])
    cands = [picks[k] for k in sorted(range(len(picks)), key=lambda k: -prior[k])][:_cfg.get("k", K)]
    if len(cands) == 1:
        return cands[0]
    p = g.to_move
    worlds = 1 if not g.bag else None
    seen: dict[int, list[float]] = {i: [] for i in cands}
    rank = {i: r for r, i in enumerate(cands)}  # the prior breaks ties
    static = dict(zip(picks, prior))
    n0 = _cfg.get("n0", 0)

    def run(alive, n):
        for i in alive:
            have = len(seen[i])
            for s in range(have, have + n):
                if worlds == 1 and s >= 1:
                    break
                ws = random.Random(f"{seed}:{s}").randrange(2**31)
                seen[i].append(rollout(g, p, moves[i], ws))

    def best(alive):
        if not n0:
            return sorted(alive, key=lambda i: (-sum(seen[i]) / max(1, len(seen[i])), rank[i]))
        # A few rollouts are noisy: count the static value as n0 rollouts' worth.
        # Rollouts carry the lead and later plies, so the prior is moved onto
        # their scale by the average offset; only its ordering is trusted.
        off = sum(sum(seen[i]) / len(seen[i]) - static[i] for i in alive) / len(alive)
        return sorted(alive, key=lambda i: (-(n0 * (static[i] + off) + sum(seen[i])) / (n0 + len(seen[i])),
                                            rank[i]))

    if not halving:
        run(cands, max(1, budget // len(cands)))
        return best(cands)[0]
    alive = list(cands)
    rounds = math.ceil(math.log2(len(alive)))
    for _ in range(rounds):
        run(alive, max(1, budget // (rounds * len(alive))))
        alive = best(alive)[:max(1, len(alive) // 2)]
    return alive[0]


_cfg = {}


_solver = None


def _init_player(who: str) -> None:
    global _solver
    if who.startswith("s3"):
        kind, leaf, budget, *rest = who.split("-")
        if leaf == "net":
            value2._init_player("v1-spread")
        else:
            fastslow._init({})
        leaves.table()
        _cfg.update(halving=True, budget=int(budget), klv=True, leaf=leaf, plies=PLIES)
        for opt in rest:  # -<plies>, -k<candidates>, -n<prior weight in rollouts>
            if opt[0] == "k":
                _cfg["k"] = int(opt[1:])
            elif opt[0] == "n":
                _cfg["n0"] = float(opt[1:])
            else:
                _cfg["plies"] = int(opt)
        if kind == "s3e":
            from scrabble.endgame import Solver
            _solver = Solver(memory=0.02)
        return
    kind, inputs, head, budget = who.split("-")
    value2._init_player(f"{inputs}-{head}")
    _cfg.update(halving=kind == "s2", budget=int(budget))


def pick(g: Game, moves, seed: int) -> int:
    if _solver is not None and not g.bag and len(moves) > 1:
        from scrabble.macondo import match
        text = _solver.best(g)
        if text is not None:
            return match(g, moves, text)
    return choose(g, moves, seed * 1000 + g.turn, _cfg["budget"], _cfg["halving"])


def duel_game(seed: int, seat: int) -> dict:
    """One game against steady."""
    g = Game(fastslow._rs, seed)
    while not g.over:
        moves = g.legal()
        i = pick(g, moves, seed) if g.to_move == seat else fast(g, moves, STEADY)
        g.apply(moves[i])
    mine, theirs = g.scores[seat], g.scores[1 - seat]
    return {"seed": seed, "seat": seat, "points": 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0,
            "spread": mine - theirs}


def duel(who: str, first: int, bags: int) -> None:
    import json
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from scrabble import value

    saved = value2.OUT / f"duel_{who}_vs_steady_{first}.jsonl"
    games = [json.loads(x) for x in saved.read_text().splitlines() if x.strip()] if saved.exists() else []
    done = {(x["seed"], x["seat"]) for x in games}
    jobs = [(first + k, seat) for k in range(bags) for seat in (0, 1) if (first + k, seat) not in done]
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init_player, initargs=(who,)) as pool, \
            saved.open("a") as out:
        for f in as_completed([pool.submit(duel_game, *job) for job in jobs]):
            games.append(f.result())
            out.write(json.dumps(games[-1]) + "\n")
            out.flush()
            if len(games) % 100 == 0:
                print(f"    {who} vs steady @{first}: {value.summary(games)}", flush=True)
    line = f"{who} vs steady @{first}: {value.summary(games)}"
    print(line, flush=True)
    with (value2.OUT / "duels.txt").open("a") as out:
        out.write(line + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--who", default="s2-v1-spread-64")
    parser.add_argument("--first", type=int, default=660_000)
    parser.add_argument("--bags", type=int, default=500)
    args = parser.parse_args()
    duel(args.who, args.first, args.bags)
