"""The held-out test. Nothing in here is visible to a run.

    python evaluate.py                       # the tactic currently in run/
    python evaluate.py path/to/other.lean

theorems/ sits outside run/, which is the cadence project root, and the
sandbox copies the project directory and nothing above it -- so a candidate
cannot read these 488 statements no matter what it does.

Compiled in chunks. Lean exits after 100 errors, and a split of 244 theorems
produces far more than that; every theorem past the cap emits no diagnostic,
which a naive scorer reads as proved. Chunks of 50 can never reach it. Each
chunk pays the Mathlib import again, which is the eleven seconds a chunk costs.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "run"))

import score  # noqa: E402

CHUNK = 50

#: Table 3 of Zheng, Han and Polu, "miniF2F: a cross-system benchmark for
#: formal Olympiad-level mathematics", ICLR 2022. The `tidy` baseline is a
#: best-first search over a curated tactic list, not a single tactic, so it is
#: quoted for scale and is not a like-for-like comparison.
PUBLISHED = {"valid": 16.8, "test": 18.0}


def run(split: pathlib.Path, script: str) -> tuple[int, int]:
    statements = score.theorems(split)
    closed = 0
    for at in range(0, len(statements), CHUNK):
        batch = statements[at : at + CHUNK]
        closed += len(score.measure(batch, script, HERE / "Evaluate.lean"))
        print(f"  {split.stem} {at + len(batch):>3}/{len(statements)}", file=sys.stderr)
    return closed, len(statements)


def main() -> None:
    where = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "run/tactic.lean"
    script = score.tactic() if where == HERE / "run/tactic.lean" else region(where)
    print(f"{where.name}\n")
    for name in ("valid", "test"):
        closed, total = run(HERE / "theorems" / f"{name}.lean", script)
        published = PUBLISHED[name]
        print(
            f"  miniF2F-{name:<6} {closed:>3}/{total}  {100 * closed / total:5.1f}%"
            f"   (tidy baseline, published: {published}%)"
        )


def region(path: pathlib.Path) -> str:
    lines = path.read_text().splitlines()
    start = next(i for i, x in enumerate(lines) if score.BEGIN in x)
    stop = next(i for i, x in enumerate(lines) if score.END in x)
    return "\n".join("  " + x for x in lines[start + 1 : stop] if x.strip())


if __name__ == "__main__":
    main()
