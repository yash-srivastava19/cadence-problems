"""The teacher: Maven-style simulation.

To judge the moves on a turn, invent many hidden worlds that fit what the
player can see, play each candidate move into the same worlds, let both sides
play on for a couple of turns, and average how it came out.

What keeps it honest:
- It never reads the real bag or the opponent's rack, only how many tiles the
  opponent holds. Every world is drawn from the tiles the player has not seen.
- Every candidate move is tried in the same worlds, so they face the same luck
  and the difference between them is the move.
- Seeded from (seed, sample), so the same question gets the same answer.
"""

import math
import random
from collections import Counter

from scrabble import bots
from scrabble.env import as_dict
from scrabble.game import Game, Move
from scrabble.ruleset import BLANK

SAMPLES, PLIES, KEEP = 20, 1, 6


def unseen(g: Game, p: int) -> list[str]:
    """Tiles player p cannot see: the opponent's rack and the bag, mixed."""
    seen = Counter(g.racks[p])
    for row in g.grid:
        for cell in row:
            if cell is not None:
                seen[BLANK if cell[1] else cell[0]] += 1
    return sorted((Counter(g.rs.full_set()) - seen).elements())


def world(g: Game, p: int, rng: random.Random) -> Game:
    tiles = unseen(g, p)
    rng.shuffle(tiles)
    held = len(g.racks[1 - p])  # how many tiles the opponent holds is public
    racks = [list(g.racks[p]), list(g.racks[p])]
    racks[1 - p] = tiles[:held]
    return Game.at(g.rs, g, racks, tiles[held:], rng.randrange(2**31))


def greedy(moves: list[Move]) -> Move:
    best = moves[0]
    for m in moves[1:]:
        if (m.score, m.kind == "play") > (best.score, best.kind == "play"):
            best = m
    return best


def value(g: Game, p: int) -> float:
    """Points ahead, plus what each side's tiles are worth if the game goes on."""
    ahead = g.scores[p] - g.scores[1 - p]
    if g.over:
        return float(ahead)
    weight = 1.0 if len(g.bag) >= 7 else 0.5 if g.bag else 0.0
    mine = bots.leave_value(tuple(g.racks[p]))
    theirs = bots.leave_value(tuple(g.racks[1 - p]))
    return ahead + weight * (mine - theirs)


def rollout(w: Game, move: Move, p: int, plies: int) -> float:
    w.apply(move)
    for _ in range(plies):
        if w.over:
            break
        w.apply(greedy(w.legal()))
    return value(w, p)


def shortlist(g: Game, moves: list[Move], also: tuple[int, ...] = ()) -> list[int]:
    """The moves worth simulating: best by equity, best by points, the best
    exchange, and anything asked for (the player's own choice)."""
    view = g.view()
    eq = [bots.equity(view, as_dict(m)) for m in moves]
    order = sorted(range(len(moves)), key=lambda i: (-eq[i], i))
    picks = order[:KEEP]
    picks.append(max(range(len(moves)), key=lambda i: (moves[i].score, -i)))
    exchanges = [i for i in order if moves[i].kind == "exchange"]
    picks += exchanges[:1] + list(also)
    return list(dict.fromkeys(picks))


def simulate(
    g: Game,
    moves: list[Move],
    picks: list[int],
    seed: int,
    samples: int = SAMPLES,
    plies: int = PLIES,
) -> dict[int, list[float]]:
    """For each picked move: its outcome in each of the same invented worlds."""
    p = g.to_move
    picks = list(dict.fromkeys(picks))
    outcomes: dict[int, list[float]] = {i: [] for i in picks}
    for s in range(samples):
        world_seed = random.Random(f"{seed}:{s}").randrange(2**31)
        for i in picks:
            w = world(g, p, random.Random(world_seed))
            outcomes[i].append(rollout(w, moves[i], p, plies))
    return outcomes


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def gap(a: list[float], b: list[float]) -> tuple[float, float]:
    """How much better a is than b, and the error of that, over shared worlds."""
    d = [x - y for x, y in zip(a, b, strict=True)]
    m = mean(d)
    var = sum((x - m) ** 2 for x in d) / max(1, len(d) - 1)
    return m, math.sqrt(var / len(d))


def choose(g: Game, moves: list[Move], seed: int) -> int:
    """The sim bot: the move that did best in the invented worlds."""
    if len(moves) == 1:
        return 0
    # With the bag empty nothing is hidden: one world is the exact one.
    samples = SAMPLES if g.bag else 1
    outcomes = simulate(g, moves, shortlist(g, moves), seed, samples)
    return max(outcomes, key=lambda i: (mean(outcomes[i]), -i))
