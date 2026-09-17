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
    return [float(o.work_remaining) for o in ops]
    # CADENCE:END
