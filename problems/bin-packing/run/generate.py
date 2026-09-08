"""The training and validation instances, written once and committed.

FunSearch evolved on generated instances the size of binpack1 and selected on
generated instances the size of binpack2, keeping OR-Library for the test.
This reproduces that protocol.

Committed as files rather than generated at score time on purpose: a seeded
RNG makes the data a function of the Python version, and the sandbox hashes
every file beside the candidate to decide whether a cached verdict still
applies. Files are the only version of that which stays true next year.

The third header number is the L2 lower bound, not a best known packing --
these instances have never been solved offline by anybody.
"""

import random
import sys
from pathlib import Path

from packing import lower_bound

CAPACITY = 150


def write(path: Path, count: int, items_per: int, seed: int) -> None:
    rng = random.Random(seed)
    lines = [str(count)]
    for i in range(count):
        items = tuple(rng.randint(20, 100) for _ in range(items_per))
        lines.append(f" gen{items_per}_{i:02d} ")
        lines.append(f" {CAPACITY} {items_per} {lower_bound(CAPACITY, items)}")
        lines.extend(str(item) for item in items)
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    here = Path(__file__).parent / "data"
    here.mkdir(exist_ok=True)
    write(here / "train.txt", 20, 120, seed=20260908)
    write(here / "valid.txt", 20, 250, seed=20260909)
    print("wrote train.txt and valid.txt", file=sys.stderr)
