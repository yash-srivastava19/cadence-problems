"""Play leave bots built from measured values against the pool, 400 fresh games each.

    PYTHONPATH=. python scrabble/rounds/measured/check.py evidence_a1 evidence_a2   # from problems/games

Each name is a folder in rounds/ with a values.json from scrabble.evidence.
"""
import json
import sys
from pathlib import Path

from scrabble.score import HERE, evaluate

SEEDS = list(range(600_000, 600_200))
OPPONENTS = [HERE / "yardsticks" / "leave.py", HERE / "opponents" / "champion_1.py"]
PLAYER = '''"""Leave bot with values measured in rounds/{name}/values.json."""
from collections import Counter

V = {values}


def leave_value(leave):
    counts = Counter(leave)
    value = sum(V[t] * c for t, c in counts.items())
    value += V["each duplicate"] * sum(c - 1 for t, c in counts.items() if c > 1 and t != "?")
    if "Q" in counts and "U" not in counts:
        value += V["Q without U"]
    return value


def choose(view, moves):
    weight = 1.0 if view["bag"] >= 7 else 0.5 if view["bag"] > 0 else 0.0
    keys = [m["score"] + weight * leave_value(m["leave"]) for m in moves]
    return keys.index(max(keys))
'''

for name in sys.argv[1:]:
    values = {k: round(v[0], 2) for k, v in json.loads((HERE / "rounds" / name / "values.json").read_text()).items()}
    me = Path(__file__).parent / f"{name}.py"
    me.write_text(PLAYER.format(name=name, values=values))
    for opp in OPPONENTS:
        m = evaluate(me, [opp], SEEDS)
        print(f"{name:<14} vs {opp.stem:<11} win {m['win_rate']:.3f}  spread {m['spread']:+6.1f}"
              f"  forfeits {m['forfeits']:.0f}  ms {m['ms_per_move']:.0f}", flush=True)
