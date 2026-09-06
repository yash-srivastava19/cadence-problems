# Circle packing, n = 26

Place 26 circles in the unit square so the sum of their radii is as large as
possible. Circles may differ in size. They may touch; they may not overlap or
leave the square.

Chosen as the first problem because it has the four properties a benchmark
needs: the verifier is cheap (milliseconds), it is deterministic, the score
is one number, and other people have published theirs.

## Numbers

| Source | Sum of radii | Notes |
|---|---|---|
| Grid baseline (`pack.py` as shipped) | 2.166667 | 26 equal circles, 6x6 grid |
| AlphaEvolve | ~2.635 | **verify against the paper before citing** |
| ShinkaEvolve | reported comparable | verify |
| cadence | not yet run | |

The published figures above are from memory and are **not** verified. Read
the papers and correct this table before any of it goes in a writeup. A
benchmark whose target is wrong is worse than no benchmark.

Deliberately kept out of `IMPROVE.md`: the model reads that file, and telling
it the number to beat anchors it on the number instead of the problem.

## Why scoring is in its own file

`pack.py` is edited by the model; `score.py` is not. If the two were one
file, a candidate could return a single circle of radius 100, or overlapping
circles, and print whatever it liked. Both are blocked, and there are tests
for both.

## Invalid vs crashed

An overlapping packing scores 0 and prints its reason to stderr. It does not
raise. That distinction matters to cadence: a crash increments
`candidates.crashes` and eventually quarantines the candidate, which is the
right response to broken code and the wrong response to a wrong answer.
