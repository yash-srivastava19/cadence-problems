# What to improve

`pack(n)` places `n` circles in the unit square and returns them as
`(x, y, r)` triples. Right now it lays them on a square grid at equal size,
which wastes the corners and holds every circle to the tightest cell.

The score is the sum of the radii. Higher is better.

## What you may change

Only the code between the `CADENCE:BEGIN` and `CADENCE:END` markers. The
function must keep the name `pack`, take `n`, and return a list of `n`
`(x, y, r)` triples of floats.

## What you may not change

The number of circles, the constraints, or how the score is computed. Those
live in `score.py`, which you cannot see or edit. Use the standard library
only.

## The constraints your answer must satisfy

- every circle lies inside the unit square: `r <= x <= 1 - r`, same for `y`
- no two circles overlap: the distance between centres is at least the sum
  of their radii
- every radius is positive

A packing that breaks any of these scores 0, with the reason printed. It is
not a crash -- it is a wrong answer, and you can fix it.

## Randomness

If you use randomness, seed it from the `CADENCE_SEED` environment variable:

```python
import os, random
rng = random.Random(int(os.environ.get("CADENCE_SEED", 0)))
```

Do not call `random.seed()` with a constant of your own, and do not leave
randomness unseeded. A program that scores differently every time cannot be
compared with the one before it.

## Worth knowing

Equal radii are not required. The best known packings mix sizes: large
circles in the middle, smaller ones filling the gaps at the edges and
corners. Local refinement of a rough starting layout tends to beat any
closed-form arrangement.
