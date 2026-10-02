"""Check cadence on Scrabble with a fake model whose answers we know.

    cd examples/games && python -m scrabble.rehearse

No LLM is called. Each trial gets a scripted reply, and each reply has an
outcome we can predict, so every number cadence reports can be checked.
"""

from pathlib import Path

from cadence.control.backends import Scripted
from cadence.control.entities import Trial
from cadence.control.manifest import load
from cadence.control.registry import build
from cadence.observe.signals import TrialAbandoned, TrialMeasured, cadence

HEAD = "def choose(view, moves):\n"

# Greedy, rewritten. Same choice on every turn, so exactly 0.5.
FASTER = (
    HEAD
    + """\
    return max(range(len(moves)),
               key=lambda i: (moves[i]["score"], moves[i]["kind"] == "play"))
"""
)

# Points plus the value of the tiles kept: the ladder's "leave" bot.
LEAVE = (
    HEAD
    + """\
    from scrabble.bots import leave
    return leave(view, moves)
"""
)

# Answers with an index that is not a move: every game is forfeited.
ILLEGAL = (
    HEAD
    + """\
    return len(moves) + 5
"""
)

# Crashes: the trial must be recorded as a failure, not as a zero.
CRASH = (
    HEAD
    + """\
    raise RuntimeError("the candidate is broken")
"""
)

# Hunts memory for the real bag. It runs in its own process, so it must not
# find one; it raises when it cannot, which fails the trial.
CANARY = (
    HEAD
    + """\
    import gc
    for thing in gc.get_objects():
        if type(thing).__name__ == "Game":
            return 0
    raise LookupError("no game in reach")
"""
)

EXPECT = [
    ("faster greedy", "scored", lambda m: m["win_rate"] == 0.5 and m["spread"] == 0),
    ("leave", "scored", lambda m: m["win_rate"] > 0.55),
    ("illegal move", "scored", lambda m: m["win_rate"] == 0 and m["forfeits"] == 50),
    ("crash", "failed", None),
    ("canary", "failed", None),
    ("prose", "abandoned", None),
]


def reply(code: str) -> str:
    return f"Here is the new section.\n```python\n{code}```"


def main() -> None:
    root = Path(__file__).parent.parent
    source = root / "scrabble" / "rehearse.cadence"
    manifest = load(source)
    answers = [reply(c) for c in (FASTER, LEAVE, ILLEGAL, CRASH, CANARY)]
    answers += ["I would weigh the leave."] * (Trial.max_attempts + 1)
    experiment = build(
        manifest, root, "rehearsal", backend=Scripted(*answers), source=source
    )

    seen: list[tuple[str, dict | None]] = []

    def watch(fact) -> None:
        if isinstance(fact, TrialMeasured):
            scored = fact.verdict.is_scored
            seen.append(
                ("scored", fact.verdict.metrics) if scored else ("failed", None)
            )
        elif isinstance(fact, TrialAbandoned):
            seen.append(("abandoned", None))

    stop = cadence.subscribe(watch)
    report = experiment.run()
    stop()

    ok = len(seen) == len(EXPECT)
    for (name, outcome, check), (got, metrics) in zip(EXPECT, seen, strict=False):
        passed = got == outcome and (check is None or check(metrics))
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}  {name:<14} {got:<10} {metrics or ''}")
    best_is_leave = "scrabble.bots import leave" in report.program
    ok &= best_is_leave
    print(f"{'PASS' if best_is_leave else 'FAIL'}  best program is the leave player")
    print("\ncadence behaved as expected" if ok else "\nsomething is off; see above")


if __name__ == "__main__":
    main()
