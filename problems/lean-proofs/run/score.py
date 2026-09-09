"""How many of the training theorems the tactic closes.

The tactic in tactic.lean is spliced into every theorem in train.lean, the
result is compiled once, and the score is the number of theorems that closed.
One compile rather than one per theorem: importing Mathlib costs about eleven
seconds and proving these costs almost nothing, so the import is the whole
bill and paying it once is the difference between 11s and 275s.

Three ways this file could report a number that is not true, all guarded:

  a linter warning      `first | ... | (tac; done)` proves the goal and then
                        warns that `done` did nothing. Counting that as a
                        failure scores every correct candidate at zero.

  Lean's error cap      Lean exits after 100 errors, and theorems it never
                        reached emit no diagnostic at all -- which reads as
                        proved. Cannot happen with 25 theorems; guarded
                        anyway, because the cap is silent when it fires.

  a broken header       if the preamble does not compile, nothing below it was
                        ever tried, and blaming the candidate for that is the
                        one failure the search cannot see.

The last two are the harness's fault, not the candidate's, so they report
cadence_verifier_error rather than a score. A verifier that quietly returns
zero makes every candidate look equally bad and the run look finished.
"""

import json
import os
import pathlib
import pwd
import re
import shutil
import subprocess
import sys

#: Resolved, not relative. `python score.py` gives a relative __file__, and
#: the compile runs with cwd set to the Lean project -- so a relative path is
#: looked for inside Mathlib, where it does not exist.
HERE = pathlib.Path(__file__).resolve().parent
BEGIN, END = "CADENCE:BEGIN", "CADENCE:END"

#: The user's real home, not $HOME. The sandbox points HOME at the copied
#: workspace, so `~` resolves inside the project and every path built from it
#: lands somewhere that does not exist.
HOME = pathlib.Path(pwd.getpwuid(os.getuid()).pw_dir)

#: Mathlib is 7.5GB. It lives outside the project because the sandbox copies
#: the project directory for every trial and hashes every file in it.
PROJECT = pathlib.Path(
    os.environ.get("CADENCE_LEAN_PROJECT", HOME / ".cache/cadence/proving")
).expanduser()

HEADER = """import Mathlib
set_option maxHeartbeats 400000
set_option linter.unusedTactic false
open BigOperators Real Nat Topology Rat
"""


def broke(why: str) -> None:
    """The harness failed, not the candidate. Say so rather than score it."""
    print(json.dumps({"cadence_verifier_error": why}))
    raise SystemExit(0)


def lake() -> str:
    found = shutil.which("lake") or str(HOME / ".elan/bin/lake")
    if not pathlib.Path(found).exists():
        broke(f"lake is not on PATH and {HOME}/.elan/bin/lake does not exist")
    if not (PROJECT / "lakefile.toml").exists():
        broke(f"no Lean project at {PROJECT}; set CADENCE_LEAN_PROJECT")
    return found


def check_environment() -> None:
    """The Lean and Mathlib the score was measured against.

    Mathlib is outside the workspace, so workspace_digest cannot see it and
    task_hash does not cover the library that decides whether a proof
    compiles. environment.txt is inside the workspace, so it does -- which
    makes the verdict cache safe, but only if something actually compares the
    stamp to the live project. This is that something.
    """
    stamp = (HERE / "environment.txt").read_text().split()
    toolchain, rev = stamp[0], stamp[2]
    live_toolchain = (PROJECT / "lean-toolchain").read_text().strip()
    if live_toolchain != toolchain:
        broke(f"environment.txt pins {toolchain}, {PROJECT} has {live_toolchain}")
    manifest = json.loads((PROJECT / "lake-manifest.json").read_text())
    live = next(
        (p.get("rev") for p in manifest["packages"] if p["name"] == "mathlib"), None
    )
    if live != rev:
        broke(f"environment.txt pins mathlib {rev[:12]}, {PROJECT} has {str(live)[:12]}")


def tactic() -> str:
    lines = (HERE / "tactic.lean").read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if BEGIN in line)
    stop = next(i for i, line in enumerate(lines) if END in line)
    body = [line for line in lines[start + 1 : stop] if line.strip()]
    if not body:
        broke("the marked region is empty")
    return "\n".join("  " + line for line in body)


def theorems(path: pathlib.Path) -> list[tuple[str, str]]:
    """Every `theorem name ... := by sorry` in a statements file."""
    found = []
    for block in path.read_text().split("\ntheorem ")[1:]:
        block = "theorem " + block.rstrip()
        name = block.split()[1]
        if not block.endswith("sorry"):
            broke(f"{name} does not end in sorry")
        found.append((name, block[: -len("sorry")].rstrip()))
    return found


def measure(statements, script, path):
    lines, at = HEADER.splitlines(), {}
    for name, stem in statements:
        at[name] = len(lines) + 3  # the 1-indexed line the theorem starts on
        lines += ["", ""] + (stem + "\n" + script).splitlines()
    path.write_text("\n".join(lines) + "\n")

    said = subprocess.run(
        [lake(), "env", "lean", str(path)],
        capture_output=True,
        text=True,
        cwd=PROJECT,
        # HOME and ELAN_HOME restored: the sandbox points HOME at the copied
        # workspace, and elan then cannot see its installed toolchains, so
        # lake starts downloading Lean again on every trial.
        env={**os.environ, "HOME": str(HOME), "ELAN_HOME": str(HOME / ".elan")},
    )
    out = said.stdout + said.stderr
    if "maximum number of errors" in out:
        broke("lean stopped at its error cap; theorems past it were never tried")

    starts = sorted(at.items(), key=lambda kv: kv[1])
    broken = set()
    # Not anchored on the filename: lean may print a path that does not match
    # the one we passed, and a regex that then matches nothing would report
    # every theorem closed. Exactly one file is compiled, so line and column
    # are unambiguous on their own.
    for line, kind, why in re.findall(r"^\S*:(\d+):(?:\d+): (error|warning): (.*)", out, re.M):
        # Only an error, or the warning that a declaration used `sorry`, means
        # unproved. Everything else is a linter with an opinion about style.
        if kind == "warning" and "sorry" not in why:
            continue
        above = [name for name, first in starts if first <= int(line)]
        if not above:
            broke(f"the header did not compile: {why[:120]}")
        broken.add(above[-1])
    if said.returncode != 0 and not broken:
        # lean failed and yet nothing was attributable to a theorem, so the
        # count is not a measurement. This is how a relative path scored a
        # perfect 25/25: lean never found the file, printed no diagnostics,
        # and every theorem looked closed.
        broke(f"lean exited {said.returncode} with nothing to attribute: {out[:200]}")
    return [name for name, _ in statements if name not in broken]


def main() -> None:
    lake()
    check_environment()
    statements = theorems(HERE / "train.lean")
    closed = measure(statements, tactic(), HERE / "Train.lean")
    for name in closed:
        print(f"-- closed {name}", file=sys.stderr)
    print(f"closed: {len(closed)}")


if __name__ == "__main__":
    main()
