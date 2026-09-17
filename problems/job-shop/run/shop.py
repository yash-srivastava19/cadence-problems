"""Reading job shop instances, and running a dispatching rule on one.

Shared by score.py (train and validation) and by ../evaluate.py (the held-out
OR-Library sets). Neither owns it, so both must agree on what a makespan is.
"""

from pathlib import Path
from typing import NamedTuple

#: A job is its operations in order; an operation is (machine, duration).
Instance = tuple[str, int, int, tuple[tuple[tuple[int, int], ...], ...]]


class Op(NamedTuple):
    """One operation a rule may choose to start now."""

    job: int
    machine: int
    duration: int
    ready_at: int
    work_remaining: int
    ops_remaining: int
    job_work: int
    job_ops: int


def load(path: str | Path) -> list[Instance]:
    """One instance per block: a name line, `jobs machines`, then a row per job."""
    blocks = Path(path).read_text().strip().split("\n\n")
    out: list[Instance] = []
    for block in blocks:
        lines = [l for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue
        name = lines[0].strip()
        n_jobs, n_mach = (int(x) for x in lines[1].split())
        jobs = []
        for row in lines[2 : 2 + n_jobs]:
            nums = [int(x) for x in row.split()]
            jobs.append(tuple((nums[i], nums[i + 1]) for i in range(0, 2 * n_mach, 2)))
        out.append((name, n_jobs, n_mach, tuple(jobs)))
    return out


def makespan(instance: Instance, priority) -> int:
    """Run a non-delay schedule, letting `priority` break every contest.

    At each step the earliest moment any waiting operation could start is
    found, and the rule chooses among the operations that could start then on
    that machine. Ties in the rule's own scores fall to the lowest job index,
    so two runs of the same rule agree.
    """
    _, n_jobs, _, jobs = instance
    next_op = [0] * n_jobs
    job_free = [0] * n_jobs
    machine_free: dict[int, int] = {}
    total = [sum(d for _, d in job) for job in jobs]
    done = 0
    end = 0

    while done < n_jobs:
        ready = []
        for j in range(n_jobs):
            k = next_op[j]
            if k >= len(jobs[j]):
                continue
            m, d = jobs[j][k]
            start = max(job_free[j], machine_free.get(m, 0))
            ready.append((start, j, k, m, d))
        if not ready:
            break
        soonest = min(r[0] for r in ready)
        machine = min(r[3] for r in ready if r[0] == soonest)
        contest = [r for r in ready if r[0] == soonest and r[3] == machine]

        ops = [
            Op(
                job=j,
                machine=m,
                duration=d,
                ready_at=start,
                work_remaining=sum(dd for _, dd in jobs[j][k:]),
                ops_remaining=len(jobs[j]) - k,
                job_work=total[j],
                job_ops=len(jobs[j]),
            )
            for (start, j, k, m, d) in contest
        ]
        scores = priority(ops, soonest)
        if len(scores) != len(ops):
            raise ValueError(f"rule returned {len(scores)} scores for {len(ops)} ops")
        best = max(range(len(ops)), key=lambda i: (scores[i], -ops[i].job))
        start, j, k, m, d = contest[best]

        finish = start + d
        job_free[j] = finish
        machine_free[m] = finish
        next_op[j] = k + 1
        if next_op[j] >= len(jobs[j]):
            done += 1
        end = max(end, finish)

    return end
