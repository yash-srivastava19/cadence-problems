"""Decide which open bin an arriving item goes into.

priority() is handed the item and the remaining capacity of every open bin
the item actually fits in. It returns one score per bin; the item goes to the
highest. It never sees a bin the item would not fit in, so it does not have to
check, and it cannot open a new bin -- that happens when the list is empty.

Only the marked region is yours. The instances, the lower bound, and how
excess is computed live in packing.py and score.py and stay put.
"""


# CADENCE:BEGIN
def priority(item: int, bins: list[int]) -> list[float]:
    """Best fit: prefer the bin left with the least room.

    The standard baseline, and the same starting point FunSearch used. It is
    greedy about the current item and indifferent to what comes next, which is
    where the room to improve is: a bin left with 3 units of slack is nearly
    dead weight, and best fit will happily create one.
    """
    return [-float(left) for left in bins]


# CADENCE:END
