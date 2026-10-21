"""One game: the bag fixed by the seed, turns, and the end.

The bag is shuffled once, at the start, from the seed. Only an exchange
reshuffles it, and that uses the same random stream, so a seed plus the list
of moves reproduces a game exactly.
"""

import random
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from scrabble import board
from scrabble.ruleset import BLANK, Ruleset


@dataclass(frozen=True)
class Move:
    kind: str  # play | exchange | pass
    tiles: tuple[board.Placement, ...] = ()
    returned: tuple[str, ...] = ()
    score: int = 0
    word: str = ""
    where: str = ""
    leave: tuple[str, ...] = ()

    def label(self) -> str:
        if self.kind == "play":
            return f"{self.word} {self.where}"
        if self.kind == "exchange":
            return f"exchange {''.join(self.returned)}"
        return "pass"


@dataclass
class Game:
    rs: Ruleset
    seed: int
    rng: random.Random = field(init=False)
    bag: list[str] = field(init=False)
    racks: list[list[str]] = field(init=False)
    grid: board.Grid = field(init=False)
    scores: list[int] = field(default_factory=lambda: [0, 0])
    turn: int = 0
    scoreless: int = 0
    over: bool = False
    end: str = ""

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.bag = self.rs.full_set()
        self.rng.shuffle(self.bag)
        self.racks = [[], []]
        self.grid = board.empty(self.rs)
        for p in (0, 1):
            self._draw(p, self.rs.rack)

    @classmethod
    def at(cls, rs: Ruleset, source: "Game", racks, bag, seed: int) -> "Game":
        """A game in the middle: source's board, scores and turn, with these
        racks and this bag. Used to branch into worlds the teacher invents."""
        g = cls.__new__(cls)
        g.rs, g.seed, g.rng = rs, seed, random.Random(seed)
        g.grid = [list(row) for row in source.grid]
        g.racks = [sorted(r) for r in racks]
        g.bag = list(bag)
        g.scores, g.turn = list(source.scores), source.turn
        g.scoreless, g.over, g.end = source.scoreless, False, ""
        return g

    @property
    def to_move(self) -> int:
        return self.turn % 2

    def _draw(self, p: int, k: int) -> list[str]:
        drawn, self.bag = self.bag[:k], self.bag[k:]
        self.racks[p].extend(drawn)
        self.racks[p].sort()
        return drawn

    def rack_value(self, p: int) -> int:
        return sum(self.rs.value(t) for t in self.racks[p])

    def view(self) -> dict:
        """What the player to move may see. Never the bag order or the other rack."""
        p = self.to_move
        seen = Counter(self.racks[p])
        for row in self.grid:
            for cell in row:
                if cell is not None:
                    seen[BLANK if cell[1] else cell[0]] += 1
        unseen = Counter(self.rs.full_set()) - seen
        return {
            "me": p,
            "rack": list(self.racks[p]),
            "scores": list(self.scores),
            "bag": len(self.bag),
            "unseen": dict(sorted(unseen.items())),
            "grid": [list(row) for row in self.grid],
        }

    def legal(self) -> list[Move]:
        rack = self.racks[self.to_move]
        out = []
        for play in board.plays(self.rs, self.grid, rack):
            used = Counter(BLANK if b else t for _, _, t, b in play.tiles)
            leave = tuple(sorted((Counter(rack) - used).elements()))
            out.append(
                Move("play", play.tiles, (), play.score, play.word, play.where, leave)
            )
        if len(self.bag) >= self.rs.exchange_min_bag:
            subsets = set()
            for k in range(1, len(rack) + 1):
                subsets.update(combinations(rack, k))
            for returned in sorted(subsets):
                leave = tuple(sorted((Counter(rack) - Counter(returned)).elements()))
                out.append(Move("exchange", returned=returned, leave=leave))
        out.append(Move("pass", leave=tuple(rack)))
        return out

    def apply(self, move: Move) -> None:
        assert not self.over, "the game is over"
        p = self.to_move
        rack = Counter(self.racks[p])
        if move.kind == "play":
            used = Counter(BLANK if b else t for _, _, t, b in move.tiles)
            assert not used - rack, "tiles not on the rack"
            for r, c, t, b in move.tiles:
                assert self.grid[r][c] is None, "square taken"
                self.grid[r][c] = (t, b)
            self.racks[p] = sorted((rack - used).elements())
            self.scores[p] += move.score
            self._draw(p, len(move.tiles))
        elif move.kind == "exchange":
            assert len(self.bag) >= self.rs.exchange_min_bag
            returned = Counter(move.returned)
            assert not returned - rack, "tiles not on the rack"
            self.racks[p] = sorted((rack - returned).elements())
            self._draw(p, len(move.returned))
            self.bag.extend(move.returned)
            self.rng.shuffle(self.bag)

        self.scoreless = self.scoreless + 1 if move.score == 0 else 0
        if not self.racks[p] and not self.bag:
            self.scores[p] += 2 * self.rack_value(1 - p)
            self.over, self.end = True, f"player {p} went out"
        elif self.scoreless >= self.rs.scoreless_turns:
            for q in (0, 1):
                self.scores[q] -= self.rack_value(q)
            self.over, self.end = True, "six scoreless turns"
        self.turn += 1
