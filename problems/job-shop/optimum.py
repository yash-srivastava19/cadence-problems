"""Compute the optimal makespan for each instance with CP-SAT, once.

Run this, not the scorer. The results are written beside the instances so that
score.py and evaluate.py stay standard library only -- a candidate must never
be able to import a solver, and the sandbox should not need one installed.

    pip install ortools
    python optimum.py heldout/orlib.txt heldout/optima.txt

Every line records whether the solve was proven optimal or stopped at a bound,
because "3% above optimal" and "3% above the best bound we could get in 60s"
are different claims and only one of them is about the rule.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run.shop import load  # noqa: E402

from ortools.sat.python import cp_model  # noqa: E402


def solve(instance, seconds: float = 60.0) -> tuple[int, str]:
    _, n_jobs, n_mach, jobs = instance
    horizon = sum(d for job in jobs for _, d in job)
    model = cp_model.CpModel()
    starts, ends, per_machine = {}, {}, {m: [] for m in range(n_mach)}

    for j, job in enumerate(jobs):
        for k, (m, d) in enumerate(job):
            s = model.new_int_var(0, horizon, f"s{j}_{k}")
            e = model.new_int_var(0, horizon, f"e{j}_{k}")
            per_machine[m].append(model.new_interval_var(s, d, e, f"i{j}_{k}"))
            starts[j, k], ends[j, k] = s, e
            if k:
                model.add(s >= ends[j, k - 1])

    for m in per_machine.values():
        model.add_no_overlap(m)

    span = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(span, [ends[j, len(job) - 1] for j, job in enumerate(jobs)])
    model.minimize(span)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_workers = 8
    status = solver.solve(model)
    if status == cp_model.OPTIMAL:
        return int(solver.value(span)), "optimal"
    if status == cp_model.FEASIBLE:
        return int(solver.best_objective_bound), "bound"
    raise RuntimeError("no solution")


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    lines = []
    for inst in load(src):
        value, kind = solve(inst, seconds)
        print(f"{inst[0]:<8} {value:>6}  {kind}", flush=True)
        lines.append(f"{inst[0]} {value} {kind}")
    Path(dst).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
