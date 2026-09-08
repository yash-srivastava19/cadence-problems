"""Reading bin packing instances, packing them online, and the lower bound.

Shared by score.py (which measures a candidate on train and validation) and
by ../evaluate.py (which measures the winner on the held-out OR-Library sets).
Neither owns it, so both must agree on what an excess bin is.
"""

import math
from pathlib import Path

#: An instance: its name, the bin capacity, and the items in arrival order.
#: Order matters -- this is online packing, so the sequence is the problem.
Instance = tuple[str, int, tuple[int, ...]]


def load(path: str | Path) -> list[Instance]:
    """OR-Library's bin packing format, which our generated sets also use.

    A count, then per instance: a name, a line of `capacity items best_known`,
    then one item size per line. best_known is read and discarded -- it is the
    best *offline* packing anybody has found, and comparing an online heuristic
    against it would flatter every result.
    """
    numbers = Path(path).read_text().split()
    instances = []
    at = 1
    for _ in range(int(numbers[0])):
        name = numbers[at]
        capacity, count = int(numbers[at + 1]), int(numbers[at + 2])
        at += 4  # name, capacity, count, best_known
        items = tuple(int(n) for n in numbers[at : at + count])
        at += count
        instances.append((name, capacity, items))
    return instances


def lower_bound(capacity: int, items: tuple[int, ...]) -> int:
    """Martello and Toth's L2 bound on the offline optimum.

    The denominator FunSearch reports against. It is a bound and not the
    optimum, so 0% excess is not generally reachable even offline -- which is
    why a heuristic scoring 4% is not "4% worse than perfect".
    """
    best = math.ceil(sum(items) / capacity)
    half = capacity / 2
    for k in range(capacity // 2 + 1):
        big = [w for w in items if w > capacity - k]
        middle = [w for w in items if capacity - k >= w > half]
        small = [w for w in items if half >= w >= k]
        free = len(middle) * capacity - sum(middle)
        extra = max(0, math.ceil((sum(small) - free) / capacity))
        best = max(best, len(big) + len(middle) + extra)
    return best


def pack(capacity: int, items: tuple[int, ...], priority) -> int:
    """Bins used when each item goes to the open bin scoring highest.

    The item is placed the moment it arrives and never moved, which is what
    makes this online. A new bin is opened only when no open bin fits.
    """
    remaining: list[int] = []
    for item in items:
        fits = [i for i, left in enumerate(remaining) if left >= item]
        if not fits:
            remaining.append(capacity - item)
            continue
        scores = priority(item, [remaining[i] for i in fits])
        chosen = fits[max(range(len(fits)), key=lambda j: scores[j])]
        remaining[chosen] -= item
    return len(remaining)


def first_fit(capacity: int, items: tuple[int, ...]) -> int:
    """The earliest open bin the item fits in."""
    return pack(capacity, items, lambda item, bins: [-i for i in range(len(bins))])


def best_fit(capacity: int, items: tuple[int, ...]) -> int:
    """The open bin left with the least room. Also the seed heuristic."""
    return pack(capacity, items, lambda item, bins: [-left for left in bins])


def excess(instances: list[Instance], bins_used) -> float:
    """Percentage of bins used beyond the lower bound, pooled over instances.

    Pooled -- total bins over total bound -- and not averaged per instance.
    The two differ in the third significant digit, and pooling is what
    reproduces every cell of the FunSearch table, so it is what the published
    numbers mean and the only aggregation this file is allowed to use.
    """
    used = sum(bins_used(capacity, items) for _, capacity, items in instances)
    bound = sum(lower_bound(capacity, items) for _, capacity, items in instances)
    return 100 * (used / bound - 1)
