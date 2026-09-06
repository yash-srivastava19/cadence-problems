"""Pack 26 circles into the unit square, as large as they will go.

Only the marked region is yours to change. The count, the constraints, and
how the score is computed live in score.py and stay put -- two runs that
scored themselves differently would not be comparable.

Return a list of (x, y, r). Nothing else is read.
"""


# CADENCE:BEGIN
def pack(n: int) -> list[tuple[float, float, float]]:
    """Equal circles on a square grid.

    The obvious thing, and not a good one: the grid wastes the corners, and
    every circle is held to the size of the tightest cell even where there is
    room to grow.
    """
    side = 1
    while side * side < n:
        side += 1
    r = 1.0 / (2 * side)
    circles = []
    for i in range(n):
        row, col = divmod(i, side)
        circles.append((col * 2 * r + r, row * 2 * r + r, r))
    return circles


# CADENCE:END
