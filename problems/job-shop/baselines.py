"""The textbook dispatching rules, as code. Ten lines each, no model involved."""

from run.shop import Op


def spt(ops: list[Op], now: int) -> list[float]:
    """Shortest processing time."""
    return [-float(o.duration) for o in ops]


def lpt(ops: list[Op], now: int) -> list[float]:
    """Longest processing time."""
    return [float(o.duration) for o in ops]


def fifo(ops: list[Op], now: int) -> list[float]:
    """First in, first out: whichever has been waiting longest."""
    return [-float(o.ready_at) for o in ops]


def mwkr(ops: list[Op], now: int) -> list[float]:
    """Most work remaining on the job."""
    return [float(o.work_remaining) for o in ops]


def lwkr(ops: list[Op], now: int) -> list[float]:
    """Least work remaining."""
    return [-float(o.work_remaining) for o in ops]


def mopnr(ops: list[Op], now: int) -> list[float]:
    """Most operations remaining."""
    return [float(o.ops_remaining) for o in ops]


RULES = {
    "SPT": spt, "LPT": lpt, "FIFO": fifo,
    "MWKR": mwkr, "LWKR": lwkr, "MOPNR": mopnr,
}
