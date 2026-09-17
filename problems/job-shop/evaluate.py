"""Measure the standard rules, and optionally an evolved one, on held-out data.

    python evaluate.py                      the textbook rules
    python evaluate.py winners/<run>.py     those, and the evolved rule

Needs no API key and no database. The held-out instances and this script live
above the cadence project root, so the sandbox never copies them and a
candidate cannot read them.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "run"))

from baselines import RULES  # noqa: E402
from run.shop import load, makespan  # noqa: E402

FAMILIES = {"ft": "Fisher-Thompson", "la": "Lawrence"}


def optima(path: Path) -> dict[str, tuple[int, str]]:
    rows = {}
    for line in path.read_text().splitlines():
        if line.strip():
            name, value, kind = line.split()
            rows[name] = (int(value), kind)
    return rows


def measure(instances, best, rule) -> tuple[float, float, int]:
    """Pooled excess, mean per-instance excess, and instances counted.

    Both, because they disagree and the literature quotes the second while
    the first is the one that does not let a small instance outvote a big one.
    """
    total_span = total_best = 0
    each = []
    for inst in instances:
        span = makespan(inst, rule)
        opt = best[inst[0]][0]
        total_span += span
        total_best += opt
        each.append(100.0 * (span / opt - 1.0))
    pooled = 100.0 * (total_span / total_best - 1.0)
    return pooled, sum(each) / len(each), len(each)


def load_rule(path: str):
    spec = importlib.util.spec_from_file_location("winner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.priority


def main() -> None:
    best = optima(HERE / "heldout" / "optima.txt")
    instances = load(HERE / "heldout" / "orlib.txt")
    proven = sum(1 for n, (_, k) in best.items() if k == "optimal")

    rules = dict(RULES)
    for arg in sys.argv[1:]:
        rules[Path(arg).stem] = load_rule(arg)

    print(f"{len(instances)} held-out instances, {proven} with a proven optimum")
    print("excess over the optimal makespan, lower is better\n")
    # Split by family. `la` is the distribution train and validation are drawn
    # from; everything else is a shape the search never saw. A rule that gains
    # on the first and loses on the second has been tuned, not improved -- the
    # failure bin-packing hit on 2026-09-16.
    la = [i for i in instances if i[0].startswith("la")]
    other = [i for i in instances if not i[0].startswith("la")]

    print(f"{'rule':<14}{'pooled':>9}{'mean':>9}{'  | la (seen shape)':>20}{'  other':>10}")
    print("-" * 62)
    for name, rule in rules.items():
        pooled, mean, _ = measure(instances, best, rule)
        la_p, _, _ = measure(la, best, rule)
        ot_p, _, _ = measure(other, best, rule)
        print(f"{name:<14}{pooled:>8.2f}%{mean:>8.2f}%{la_p:>18.2f}%{ot_p:>9.2f}%")


if __name__ == "__main__":
    main()
