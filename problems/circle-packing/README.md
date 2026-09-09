# Circle packing, n = 26

Place 26 circles in the unit square, maximising the sum of their radii.
Circles may differ in size and may touch, but not overlap or leave the square.

## Results

| Source | Sum of radii |
|---|---|
| Grid baseline (`pack.py` as shipped) | 2.166667 |
| Previous best known | 2.634 |
| AlphaEvolve | 2.63586276 |
| ShinkaEvolve | 2.635983283 |
| cadence, run `20260907-025816-571b77`, 4 trials | **2.604552** |

Published figures verified 2026-09-08 against the AlphaEvolve whitepaper
(arXiv 2506.13131); ShinkaEvolve's is still second-hand. None of these numbers
appear in `IMPROVE.md` — telling the model the target anchors it on the number
instead of the problem.

Note the weakness of this problem: the grid baseline is our own invention, so
nothing here checks the harness. See `bin-packing` for the contrast.

## Design

`pack.py` is edited; `score.py` is not. Scoring in its own file is what stops
a candidate returning one circle of radius 100 and printing a large number.

An overlapping packing scores 0 with a reason on stderr and does **not** raise.
A crash increments `candidates.crashes` and eventually quarantines the
candidate — the right response to broken code, the wrong one to a wrong answer.

`verifier.tolerance` is deliberately absent. Packing solutions are stochastic,
so declaring determinism would switch on the verdict cache and freeze whichever
score a candidate happened to get first.

## Sandbox limits are load-bearing

`sandbox.seconds: 120`, not 30. The two candidates that beat the baseline took
41.9s and 59.4s to score; a 30s limit killed both, and the run read as "the
search is weak". A limit any winner can hit is a hidden term in the objective.

Likewise `model.gemini.timeout: 300` — `providers.yml` gives gemini a 120s row,
below cadence's own default, and two of four calls took 194s and 248s.

## Running

```sh
cadence run . --config ../../arms/circle-packing-8.cadence
```
