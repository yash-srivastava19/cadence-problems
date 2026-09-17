"""Decide which open bin an arriving item goes into.

priority() is handed the item and the remaining capacity of every open bin
the item actually fits in. It returns one score per bin; the item goes to the
highest. It never sees a bin the item would not fit in, so it does not have to
check, and it cannot open a new bin -- that happens when the list is empty.

Only the marked region is yours. The instances, the lower bound, and how
excess is computed live in packing.py and score.py and stay put.
"""


# CADENCE:BEGIN
_SCORE_TABLE = [
    [
        100000.0 if (rem := left - item) == 0 else (
            200.0 - rem * 18.0 if rem < 20 else (
                -0.8 * rem + 2.0 * (rem % 20) + 25.0 * (rem // 20) - 0.05 * left
            )
        )
        for left in range(201)
    ]
    for item in range(201)
]


def priority(item: int, bins: list[int]) -> list[float]:
    """Score open bins based on remaining capacity after placing item.

    Leverages item size bounds (min size 20, max 100, bin capacity 150):
    - Exact fit (rem == 0): highest score.
    - Closed bin waste (0 < rem < 20): scored smoothly across all waste values.
      Small waste (rem <= 10) is preferred over keeping bins open, locking in
      >= 93.3% bin efficiency without artificial cliffs.
    - Open bins (rem >= 20): scored using capacity tiers (rem // 20) and 
      slack margins (rem % 20). Higher margin within a tier gives flexibility 
      to accept a wider range of future items (since items are >= 20).
    """
    row = _SCORE_TABLE[item]
    return [row[left] for left in bins]
# CADENCE:END