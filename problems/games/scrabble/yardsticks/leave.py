"""The yardstick: points plus a simple leave value. Never in the pool, so
nothing is ever trained against it."""

from scrabble.bots import leave


def choose(view: dict, moves: list[dict]) -> int:
    return leave(view, moves)
