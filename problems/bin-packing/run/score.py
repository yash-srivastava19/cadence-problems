"""What a heuristic is worth, decided outside the region the model may edit.

Two sets, both generated, neither of them the benchmark. The OR-Library sets
live one directory up and are never copied into the sandbox, so a candidate
cannot be tuned against them even by accident -- which is the only thing that
makes the number in the final report a held-out number.

Three failures, deliberately kept apart:

  broken code       priority() raises. Let it propagate: cadence books it as
                    CRASHED and retires the candidate after enough of them.

  invalid answer    it returns the wrong number of scores, or something that
                    is not a number. A real answer to the question, just an
                    unusable one. It scores the ceiling with a reason on
                    stderr, so the run learns what it did wrong.

  not deterministic the same heuristic scores the train set differently twice.
                    The manifest declares a tolerance, which switches on a
                    verdict cache shared across runs; a candidate rolling dice
                    would poison it with whichever score it happened to get
                    first. Checked here rather than trusted.
"""

import sys

from packing import excess, load, pack

#: Worse than any heuristic anybody would write, and finite so the run can
#: still rank two bad candidates against each other.
CEILING = 100.0


def refuse(reason: str) -> None:
    """A valid program with an unusable answer. Ceiling, and say why."""
    print(f"invalid: {reason}", file=sys.stderr)
    print(f"excess_train: {CEILING}")
    print(f"excess_valid: {CEILING}")
    raise SystemExit(0)


def checked(priority):
    """priority(), with the contract enforced on every call."""

    def scored(item: int, bins: list[int]) -> list[float]:
        given = priority(item, list(bins))
        try:
            values = [float(v) for v in given]
        except (TypeError, ValueError):
            refuse(f"priority returned {type(given).__name__}, not numbers")
        if len(values) != len(bins):
            refuse(f"priority returned {len(values)} scores for {len(bins)} bins")
        if any(v != v for v in values):
            refuse("priority returned NaN, which cannot be compared")
        return values

    return scored


def main() -> None:
    from heuristic import priority

    scored = checked(priority)
    train, valid = load("data/train.txt"), load("data/valid.txt")

    def bins_used(capacity, items):
        return pack(capacity, items, scored)

    on_train = excess(train, bins_used)
    if excess(train, bins_used) != on_train:
        refuse("scored the same instances differently twice; remove the randomness")

    print(f"excess_train: {on_train:.6f}")
    print(f"excess_valid: {excess(valid, bins_used):.6f}")


if __name__ == "__main__":
    main()
