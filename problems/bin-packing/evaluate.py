"""The held-out test. Nothing in here is visible to a run.

This file and the OR-Library data sit outside run/, which is the whole cadence
project: the sandbox copies the project directory and nothing above it, so a
candidate is physically unable to read binpack1..4 no matter what it tries.
That is what lets the number this prints be called held out.

    python evaluate.py                  # the heuristic currently in run/
    python evaluate.py path/to/other.py # any other one

Prints the FunSearch table beside our own so a mismatch in the first two rows
is visible immediately: if first fit and best fit do not reproduce, the harness
is wrong and the third row means nothing.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "run"))

from packing import best_fit, excess, first_fit, load, pack  # noqa: E402

SETS = ("binpack1", "binpack2", "binpack3", "binpack4")

#: Table 1 of Novikov et al., "Mathematical discoveries from program search
#: with large language models", Nature 625 (2024). Quoted, not recomputed.
PUBLISHED = {
    "First Fit (published)": (6.42, 6.45, 5.74, 5.23),
    "Best Fit (published)": (5.81, 6.06, 5.37, 4.94),
    "FunSearch (published)": (5.30, 4.19, 3.11, 2.47),
}


def load_priority(path: Path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.priority


def row(name: str, values) -> str:
    return f"{name:<24}" + "".join(f"{v:>10.2f}" for v in values)


def main() -> None:
    where = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "run" / "heuristic.py"
    priority = load_priority(where)
    sets = [load(HERE / "heldout" / f"{name}.txt") for name in SETS]

    print(f"{'':<24}" + "".join(f"{name:>10}" for name in SETS))
    for name, values in PUBLISHED.items():
        print(row(name, values))
    print()
    print(row("First Fit (ours)", [excess(s, first_fit) for s in sets]))
    print(row("Best Fit (ours)", [excess(s, best_fit) for s in sets]))
    print(
        row(
            f"{where.stem} (ours)",
            [
                excess(s, lambda c, i: pack(c, i, priority))
                for s in sets
            ],
        )
    )


if __name__ == "__main__":
    main()
