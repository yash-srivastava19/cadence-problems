"""Scrabble as a kit Env: the game, with every move turned into plain JSON."""

from pathlib import Path

from scrabble import cgp
from scrabble.game import Game, Move
from scrabble.ruleset import load

HERE = Path(__file__).parent


def as_dict(m: Move) -> dict:
    return {
        "kind": m.kind,
        "label": m.label(),
        "score": m.score,
        "word": m.word,
        "where": m.where,
        "tiles": [list(t) for t in m.tiles],
        "returned": list(m.returned),
        "leave": list(m.leave),
    }


class ScrabbleEnv:
    players = 2

    def __init__(self, config: Path = HERE / "english.json"):
        self.rs = load(config)
        self.name = self.rs.name
        self._offered: dict[int, list[Move]] = {}

    def reset(self, seed: int) -> Game:
        return Game(self.rs, seed)

    def to_move(self, g: Game) -> int:
        return g.to_move

    def observe(self, g: Game, player: int) -> dict:
        assert player == g.to_move, "a player is only shown the board on its turn"
        return {**g.view(), "cgp": cgp.encode(g, viewer=player)}

    def legal(self, g: Game) -> list[dict]:
        moves = g.legal()
        self._offered[id(g)] = moves
        return [as_dict(m) for m in moves]

    def step(self, g: Game, choice: int) -> Game:
        g.apply(self._offered.pop(id(g))[choice])
        return g

    def done(self, g: Game) -> bool:
        return g.over

    def returns(self, g: Game) -> list[float]:
        return [float(s) for s in g.scores]
