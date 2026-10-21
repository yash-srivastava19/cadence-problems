"""Greedy: the most points this turn. The first opponent in the pool."""


def choose(view: dict, moves: list[dict]) -> int:
    """Return the index of one of `moves`. `view` is all this player may see."""
    best = 0
    for i, move in enumerate(moves):
        key = (move["score"], move["kind"] == "play")
        if key > (moves[best]["score"], moves[best]["kind"] == "play"):
            best = i
    return best
