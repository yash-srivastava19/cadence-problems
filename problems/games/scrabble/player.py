"""The player cadence evolves. It starts as the greedy bot: most points now.

It runs in its own process and is sent plain JSON each turn, so it sees only
what a player may see. Everything outside the markers stays put.
"""


# CADENCE:BEGIN
def choose(view: dict, moves: list[dict]) -> int:
    """Return the index of one of `moves`. `view` is all this player may see."""
    best = 0
    for i, move in enumerate(moves):
        key = (move["score"], move["kind"] == "play")
        if key > (moves[best]["score"], moves[best]["kind"] == "play"):
            best = i
    return best


# CADENCE:END
