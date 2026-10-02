"""Playing episodes, and comparing two players on the same luck."""

from collections.abc import Callable, Iterable

from kit.env import Env
from kit.player import Forfeit


def play(env: Env, players: list, seed: int, on_turn: Callable | None = None) -> dict:
    """One episode. A record of the seed and every choice replays it exactly."""
    state = env.reset(seed)
    actions: list[int] = []
    forfeit = None
    while not env.done(state):
        p = env.to_move(state)
        observation, legal = env.observe(state, p), env.legal(state)
        try:
            choice = players[p].choose(observation, legal)
        except Forfeit as why:
            forfeit = {"player": p, "turn": len(actions), "reason": str(why)}
            break
        if on_turn:
            on_turn(state, p, observation, legal, choice)
        actions.append(choice)
        state = env.step(state, choice)
    return {
        "env": env.name,
        "seed": seed,
        "players": [pl.name for pl in players],
        "actions": actions,
        "returns": None if forfeit else env.returns(state),
        "forfeit": forfeit,
    }


def duplicate(env: Env, a, b, seeds: Iterable[int]) -> list[tuple[dict, int]]:
    """Every seed with the seats both ways round, so a and b get the same luck.

    Returns (record, a's seat) pairs. With one player there is no opponent:
    a and b each play every seed alone, and are compared seed by seed.
    """
    out = []
    for seed in seeds:
        if env.players == 1:
            out += [(play(env, [a], seed), 0), (play(env, [b], seed), -1)]
        else:
            out += [(play(env, [a, b], seed), 0), (play(env, [b, a], seed), 1)]
    return out
