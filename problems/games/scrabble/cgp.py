"""Scrabble positions as CGP strings: the FEN of crossword games.

    <rows> <rack to move>/<other rack> <score to move>/<other score> <zeros> <ops>

Rows are separated by "/", digits are runs of empty squares, lowercase is a
blank, and a token longer than one letter is written in brackets ("[CH]").
Racks write a blank as "?". Everything is from the point of view of the
player to move. Our opcodes add what plain CGP leaves out:

    turn N;        moves made so far (who is player 0 follows from it)
    bag TILES;     full state only: the bag, in draw order
    held N;        a player's view only: tiles in the other rack
    bagsize N;     a player's view only: tiles in the bag

A full state can be rebuilt exactly, except the random stream an exchange
reshuffles with; a game is replayed exactly from its seed and moves.
A player's view leaves the other rack empty and the bag out: it holds only
what that player may know.
"""

import random
from collections import Counter
from dataclasses import dataclass

from scrabble.game import Game
from scrabble.ruleset import BLANK, Ruleset


@dataclass
class Position:
    """A parsed CGP string. `racks`, `scores` are (to move, other)."""

    grid: list[list[tuple[str, bool] | None]]
    racks: tuple[list[str], list[str]]
    scores: tuple[int, int]
    zeros: int
    turn: int
    bag: list[str] | None  # None in a player's view
    held: int  # tiles in the other rack
    bag_size: int

    @property
    def to_move(self) -> int:
        return self.turn % 2


def _token(t: str) -> str:
    return t if len(t) == 1 else f"[{t}]"


def _tiles(tiles: list[str]) -> str:
    return "".join(_token(t) for t in tiles)


def _split(text: str) -> list[str]:
    out, i = [], 0
    while i < len(text):
        if text[i] == "[":
            j = text.index("]", i)
            out.append(text[i + 1 : j])
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return out


def encode(g: Game, viewer: int | None = None) -> str:
    """The full state, or with `viewer` set, what that player may see.

    A player's view is only ever made on its own turn, like the game's view.
    """
    p = g.to_move
    if viewer is not None:
        assert viewer == p, "a player sees the board on its own turn"
    rows = []
    for row in g.grid:
        out, empty = "", 0
        for cell in row:
            if cell is None:
                empty += 1
                continue
            if empty:
                out, empty = out + str(empty), 0
            t, blank = cell
            out += _token(t.lower() if blank else t)
        rows.append(out + (str(empty) if empty else ""))
    other = "" if viewer is not None else _tiles(g.racks[1 - p])
    text = (
        f"{'/'.join(rows)} {_tiles(g.racks[p])}/{other} "
        f"{g.scores[p]}/{g.scores[1 - p]} {g.scoreless} turn {g.turn};"
    )
    if viewer is None:
        return text + f" bag {_tiles(g.bag)};"
    return text + f" held {len(g.racks[1 - p])}; bagsize {len(g.bag)};"


def parse(text: str) -> Position:
    board, racks, scores, zeros, *rest = text.split(" ", 4)
    ops = {}
    for op in " ".join(rest).split(";"):
        if op.strip():
            name, _, value = op.strip().partition(" ")
            ops[name] = value
    grid = []
    for row in board.split("/"):
        cells: list[tuple[str, bool] | None] = []
        number = ""
        for t in _split(row):
            if t.isdigit():
                number += t
                continue
            if number:
                cells += [None] * int(number)
                number = ""
            cells.append((t.upper(), t != t.upper()))
        cells += [None] * int(number or 0)
        grid.append(cells)
    mine, other = racks.split("/")
    a, b = scores.split("/")
    bag = _split(ops["bag"]) if "bag" in ops else None
    return Position(
        grid=grid,
        racks=(_split(mine), _split(other)),
        scores=(int(a), int(b)),
        zeros=int(zeros),
        turn=int(ops["turn"]),
        bag=bag,
        held=int(ops["held"]) if "held" in ops else len(_split(other)),
        bag_size=int(ops["bagsize"]) if "bagsize" in ops else len(bag or []),
    )


def unseen(rs: Ruleset, pos: Position) -> list[str]:
    """Tiles the player to move cannot see: the other rack and the bag."""
    seen = Counter(pos.racks[0])
    for row in pos.grid:
        for cell in row:
            if cell is not None:
                seen[BLANK if cell[1] else cell[0]] += 1
    return sorted((Counter(rs.full_set()) - seen).elements())


def game(
    rs: Ruleset, pos: Position, other: list[str], bag: list[str], seed: int = 0
) -> Game:
    """A playable game from a position, with the hidden parts filled in."""
    p = pos.to_move
    racks = [[], []]
    racks[p], racks[1 - p] = list(pos.racks[0]), list(other)
    scores = [0, 0]
    scores[p], scores[1 - p] = pos.scores
    g = Game.__new__(Game)
    g.rs, g.seed = rs, seed
    g.rng = random.Random(seed)
    g.grid = [list(row) for row in pos.grid]
    g.racks = [sorted(r) for r in racks]
    g.bag = list(bag)
    g.scores, g.turn, g.scoreless = scores, pos.turn, pos.zeros
    g.over, g.end = False, ""
    return g


def decode(rs: Ruleset, text: str, seed: int = 0) -> Game:
    """A full-state CGP back into a game. A player's view cannot be decoded:
    its hidden parts are missing (use tools.sample_world for that)."""
    pos = parse(text)
    assert pos.bag is not None, "a player's view has no bag to rebuild from"
    return game(rs, pos, pos.racks[1], pos.bag, seed)
