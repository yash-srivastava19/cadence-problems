"""Choose which waiting operation a free machine starts next.

priority() is handed every operation that could start at this moment on this
machine, and returns one score per operation; the highest starts. Ties fall to
the lowest job index, so two runs agree.

Only the marked region is yours. The instances, the schedule and the makespan
live in shop.py and score.py and stay put.
"""

from shop import Op


def priority(ops: list[Op], now: int) -> list[float]:
    """Most work remaining: start whichever job has the most left to do.

    A standard dispatching rule and a strong one for makespan. It looks only
    at the job in front of it and never at the machine it is about to block,
    which is where the room to improve is.
    """
    # CADENCE:BEGIN
    if len(ops) == 1:
        return [0.0]

    tot_work = sum(o.work_remaining for o in ops)
    n = len(ops)

    scores = []
    for o in ops:
        wait = now - o.ready_at
        tail = o.work_remaining - o.duration
        unlock_rate = tail / (o.duration + 3.0)
        other_work = tot_work - o.work_remaining

        score = (
            o.work_remaining
            + 1.2 * tail
            + 3.5 * unlock_rate
            + 0.8 * wait
            + 7.5 * (o.work_remaining / o.job_work)
            + 4.5 * (o.ops_remaining / o.job_ops)
            - 0.5 * o.duration
            - 0.0012 * o.duration * other_work
            - 0.4 * o.duration * (n - 1)
        )
        scores.append(score)

    return scores
    # CADENCE:END