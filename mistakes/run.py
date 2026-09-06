"""What cadence says when a first-time user gets it wrong.

Each directory is one mistake. Its `expect` file holds the lines that must
appear in `cadence check`'s output, and `known-bad:` lines describing an
error we are not happy with yet -- those are reported, not failed, so the
list stays visible without blocking.

    python mistakes/run.py            # cadence from PATH
    CADENCE=../cadence/.venv/bin/cadence python mistakes/run.py
"""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CADENCE = os.environ.get("CADENCE", "cadence")


def check(case: Path) -> tuple[list[str], list[str]]:
    """The lines we wanted and did not get, and the known-bad notes."""
    lines = (case / "expect").read_text().splitlines()
    notes = [ln.removeprefix("known-bad:").strip() for ln in lines if ln.startswith("known-bad:")]
    want = [ln for ln in lines if ln.strip() and not ln.startswith("known-bad:")]
    done = subprocess.run(
        [CADENCE, "check", str(case)], capture_output=True, text=True
    )
    output = done.stdout + done.stderr
    return [ln for ln in want if ln not in output], notes


def main() -> int:
    cases = sorted(p for p in HERE.iterdir() if (p / "expect").is_file())
    failed, known = [], []
    for case in cases:
        missing, notes = check(case)
        if missing:
            failed.append((case.name, missing))
        if notes:
            known.append((case.name, " ".join(notes)))
        print(f"{'FAIL' if missing else 'ok  '}  {case.name}")
    for name, note in known:
        print(f"\nknown-bad  {name}\n           {note}")
    for name, missing in failed:
        print(f"\nFAIL  {name}: never said {missing!r}")
    print(f"\n{len(cases) - len(failed)}/{len(cases)} say what they should.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
