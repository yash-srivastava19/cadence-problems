"""The player's toolbox: the rules, and nothing hidden.

A player is sent its view as a CGP string (view["cgp"]). With these it can
imagine: fill in the hidden tiles at random from the ones it has not seen,
then try moves and see what follows, as often as its time allows.

    from scrabble import tools

    world = tools.sample_world(view["cgp"], rng)   # one possible full state
    moves = tools.legal(world)                     # same moves, same order, same form
    after = tools.play(world, moves[i])            # or tools.play(world, i)
    tools.spread(after, me)                        # my points minus theirs

The moves `legal` lists for a sampled world come in the same order as the
moves the player was sent, so an index found by imagining is the one to return.
"""

import random
from functools import cache
from pathlib import Path

from kit.player import Record

from scrabble import cgp
from scrabble.env import as_dict
from scrabble.game import Game, Move
from scrabble.ruleset import Ruleset, load

BUDGET_SECONDS = 2.0  # aim for this per move; the hard limit is higher


@cache
def ruleset() -> Ruleset:
    return load(Path(__file__).with_name("english.json"))


def position(view: str) -> cgp.Position:
    return cgp.parse(view)


def unseen(view: str) -> list[str]:
    """The other rack and the bag, mixed: every tile you cannot see."""
    return cgp.unseen(ruleset(), cgp.parse(view))


def sample_world(view: str, rng: random.Random) -> Game:
    """One full state that fits what you know: the unseen tiles shuffled into
    the other rack and the bag. Once the bag is empty this is exact."""
    pos = cgp.parse(view)
    tiles = cgp.unseen(ruleset(), pos)
    rng.shuffle(tiles)
    return cgp.game(ruleset(), pos, tiles[: pos.held], tiles[pos.held :],
                    rng.randrange(2**31))


def legal(g: Game) -> list[Record]:
    """Every legal move for whoever is to move in g, in the same form as the
    moves you are sent: move["score"] and move.score both work."""
    moves = g.legal()
    g.offered = moves
    return [Record(as_dict(m)) for m in moves]


def play(g: Game, move) -> Game:
    """The state after `move`. g itself is not changed.

    `move` can be a move from `legal(g)` or from the moves you were sent
    (they are the same), or its index in that list."""
    nxt = Game.at(g.rs, g, g.racks, g.bag, seed=g.seed)
    nxt.rng.setstate(g.rng.getstate())
    nxt.apply(_resolve(g, move))
    return nxt


def _resolve(g: Game, move) -> Move:
    if isinstance(move, Move):
        return move
    moves = getattr(g, "offered", None) or g.legal()
    g.offered = moves
    if isinstance(move, int):
        return moves[move]
    wanted = (move["kind"], [list(t) for t in move["tiles"]], list(move["returned"]))
    for m in moves:
        if (m.kind, [list(t) for t in m.tiles], list(m.returned)) == wanted:
            return m
    raise ValueError(f"{move.get('label', move)} is not a legal move here")


def spread(g: Game, me: int) -> int:
    """My points minus theirs. After the game ends, this is the final result."""
    return g.scores[me] - g.scores[1 - me]


def to_move(g: Game) -> int:
    return g.to_move


def over(g: Game) -> bool:
    return g.over
