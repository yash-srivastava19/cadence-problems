"""Measure a dispatching rule against the optimal makespan.

Excess is pooled -- total makespan over total optimum -- not averaged per
instance. Averaging weights a six-machine toy the same as a thirty-job shop
and quietly reports a different number; the same correction mattered on bin
packing.
"""

import json
from pathlib import Path

from rule import priority
from shop import load, makespan

HERE = Path(__file__).parent


def optima(path: Path) -> dict[str, int]:
    rows = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        name, value, _kind = line.split()
        rows[name] = int(value)
    return rows


def excess(data: Path, best: dict[str, int]) -> float:
    """Percentage of makespan beyond the optimum, pooled over instances."""
    total_span = total_best = 0
    for inst in load(data):
        total_span += makespan(inst, priority)
        total_best += best[inst[0]]
    return 100.0 * (total_span / total_best - 1.0)


def main() -> None:
    best = optima(HERE / "data" / "optima.txt")
    train = excess(HERE / "data" / "train.txt", best)
    # Scored twice: the manifest declares a tolerance, and a rule that is not
    # deterministic must be refused rather than cached.
    if abs(train - excess(HERE / "data" / "train.txt", best)) > 1e-9:
        print(json.dumps({"cadence_verifier_error": "rule is not deterministic"}))
        raise SystemExit(1)
    valid = excess(HERE / "data" / "valid.txt", best)
    print(f"excess_train: {train:.6f}")
    print(f"excess_valid: {valid:.6f}")


if __name__ == "__main__":
    main()
