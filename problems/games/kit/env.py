"""What a game or environment gives the kit.

Everything a player sees, `observe` and `legal`, must be plain JSON: it is
sent to the player across a process boundary.
"""

from typing import Any, Protocol


class Env(Protocol):
    name: str
    players: int  # 1 for an environment with no opponent

    def reset(self, seed: int) -> Any:
        """A new episode. All of its randomness is fixed here, from the seed."""

    def to_move(self, state: Any) -> int: ...

    def observe(self, state: Any, player: int) -> dict:
        """Only what this player may see."""

    def legal(self, state: Any) -> list[dict]:
        """Every allowed action, in a fixed order. Each needs a "label"."""

    def step(self, state: Any, choice: int) -> Any:
        """Apply legal(state)[choice]."""

    def done(self, state: Any) -> bool: ...

    def returns(self, state: Any) -> list[float]:
        """The result, one number per player."""
