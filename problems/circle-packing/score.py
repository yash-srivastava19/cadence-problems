"""What a packing is worth, decided outside the region the model may edit.

This file is the reason the benchmark means anything. If scoring lived in
pack.py the model could return one circle of radius 100 and print a
spectacular number, and nothing would catch it.

Two failures, deliberately kept apart:

  broken code   pack() raises, or returns something that is not circles.
                Let it propagate: cadence books it as CRASHED and retires
                the candidate after enough of them.

  invalid answer   the circles overlap or leave the square. That is a real
                answer to the question, just a bad one. It scores 0 with a
                reason on stderr, so the run learns "you overlapped" rather
                than "you crashed".
"""

import sys

N = 26

#: Slack for float arithmetic only. Large enough that a legitimate packing
#: touching its neighbour passes, small enough that a real overlap does not.
EPS = 1e-9


def refuse(reason: str) -> None:
    """A valid program with an invalid answer. Zero, and say why."""
    print(f"invalid: {reason}", file=sys.stderr)
    print("sum_radii: 0.0")
    raise SystemExit(0)


def check(circles: list[tuple[float, float, float]]) -> None:
    if len(circles) != N:
        refuse(f"expected {N} circles, got {len(circles)}")
    for i, (x, y, r) in enumerate(circles):
        if not (r > 0):
            refuse(f"circle {i} has radius {r}, which is not positive")
        if x - r < -EPS or x + r > 1 + EPS or y - r < -EPS or y + r > 1 + EPS:
            refuse(f"circle {i} at ({x:.4f}, {y:.4f}) r={r:.4f} leaves the square")
    for i in range(N):
        xi, yi, ri = circles[i]
        for j in range(i + 1, N):
            xj, yj, rj = circles[j]
            gap = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5 - (ri + rj)
            if gap < -EPS:
                refuse(f"circles {i} and {j} overlap by {-gap:.6f}")


def main() -> None:
    from pack import pack

    circles = [tuple(float(v) for v in c) for c in pack(N)]
    check(circles)
    print(f"sum_radii: {sum(r for _, _, r in circles):.6f}")


if __name__ == "__main__":
    main()
