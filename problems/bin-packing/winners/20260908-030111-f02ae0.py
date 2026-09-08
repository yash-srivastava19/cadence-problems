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
    """Score open bins based on remaining capacity after placing item.

    Leverages item size bounds (min size 20, max 100, bin capacity 150):
    - Exact fit (rem == 0): highest score.
    - Small closed waste (0 < rem <= 5): preferred, locks in >= 96.7% bin usage.
    - Closed bin waste (5 < rem < 20): penalized proportionally.
    - Open bins (rem >= 20): scored using capacity tiers (rem // 20) and 
      slack margins (rem % 20). Higher margin within a tier gives flexibility 
      to accept a wider range of future items (since items are >= 20).
    """
    return [
        100000.0 if (rem := left - item) == 0 else (
            200.0 - rem * 25.0 if rem <= 5 else (
                -15.0 * rem if rem < 20 else (
                    -0.8 * rem + 2.0 * (rem % 20) + 25.0 * (rem // 20) - 0.05 * left
                )
            )
        )
        for left in bins
    ]
# CADENCE:END