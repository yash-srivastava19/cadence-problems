"""The fixed players of the benchmark ladder.

Every bot has the same shape as the player cadence will evolve:
choose(view, moves) -> the index of one of moves. The moves arrive in a fixed order, and
ties go to the earliest, so a bot never depends on hash order.
"""

import random
from collections import Counter
from collections.abc import Callable

Bot = Callable[[dict, list[dict]], int]

# A hand-written leave for English: what a tile left on the rack is worth.
# Deliberately simple. It is the rung between "greedy" and a real engine.
TILE = {
    "?": 25,
    "S": 8,
    "Z": 3,
    "X": 3,
    "E": 2,
    "R": 1.5,
    "A": 1,
    "N": 1,
    "T": 1,
    "L": 0.5,
    "H": 0.5,
    "I": -0.5,
    "O": -1,
    "U": -3,
    "V": -5,
    "W": -3,
    "Q": -8,
    "J": -2,
    "K": -1,
    "G": -2,
    "F": -1.5,
    "B": -2,
}
VOWELS = set("AEIOU")


def leave_value(leave: tuple[str, ...]) -> float:
    if not leave:
        return 0.0
    value = sum(TILE.get(t, 0) for t in leave)
    value -= sum(3 * (n - 1) for n in Counter(leave).values() if n > 1)
    vowels = sum(t in VOWELS for t in leave)
    value -= 2 * abs(vowels - round(0.4 * len(leave)))
    if "Q" in leave and "U" not in leave:
        value -= 5
    return value


def equity(view: dict, move: dict) -> float:
    """Points now, plus what the tiles kept are worth. Leave matters less late."""
    weight = 1.0 if view["bag"] >= 7 else 0.5 if view["bag"] > 0 else 0.0
    return move["score"] + weight * leave_value(tuple(move["leave"]))


def _best(moves: list[dict], key) -> int:
    best, best_key = 0, key(moves[0])
    for i, m in enumerate(moves[1:], 1):
        k = key(m)
        if k > best_key:
            best, best_key = i, k
    return best


def greedy(view: dict, moves: list[dict]) -> int:
    return _best(moves, lambda m: (m["score"], m["kind"] == "play"))


def leave(view: dict, moves: list[dict]) -> int:
    return _best(moves, lambda m: equity(view, m))


def make_random(seed: int) -> Bot:
    rng = random.Random(seed)

    def choose(view: dict, moves: list[dict]) -> int:
        plays = [i for i, m in enumerate(moves) if m["kind"] == "play"]
        return rng.choice(plays or range(len(moves)))

    return choose


BOTS = {
    "random": make_random,
    "greedy": lambda seed: greedy,
    "leave": lambda seed: leave,
}
