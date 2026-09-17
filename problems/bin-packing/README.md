# Online bin packing

Items arrive one at a time, each is placed on arrival and never moved, and the
goal is to use as few bins as possible. FunSearch's combinatorial benchmark.

Source: Romera-Paredes et al., *Mathematical discoveries from program search with
large language models*, Nature 625, 468–475 (2024), Table 1 and Appendix E.4.

## Results

Percentage of bins over the Martello–Toth L2 lower bound, pooled over
instances. Lower is better. Run `20260908-030111-f02ae0`, 10 trials,
gemini-3.6-flash, 2026-09-08.

| | binpack1 | binpack2 | binpack3 | binpack4 |
|---|---|---|---|---|
| First fit (published / ours) | 6.42 / **6.42** | 6.45 / **6.45** | 5.74 / **5.74** | 5.23 / **5.23** |
| Best fit, the seed (published / ours) | 5.81 / **5.81** | 6.06 / **6.06** | 5.37 / **5.37** | 4.94 / **4.94** |
| cadence, 10 trials | 5.61 | 5.22 | 3.80 | 3.22 |
| FunSearch | 5.30 | 4.19 | 3.11 | 2.47 |

Per-instance record against best fit: 8W-6T-6L, 13W-6T-1L, 20W-0L, 20W-0L.
The heuristic was evolved on 120-item instances and wins every 500- and
1000-item instance, which is the generalisation direction FunSearch reported.

Winner in `winners/`. Session notes in `demos/2026-09-08-bin-packing.md`.

## Layout

```
heldout/binpack1..4.txt   OR-Library. Never copied into the sandbox.
evaluate.py               The held-out test. Not part of any run.
winners/                  Applied winners, one per run.
run/                      The cadence project — all a candidate can see.
  heuristic.py            priority() is the marked region.
  score.py                Train and validation excess.
  packing.py              Parsing, the L2 bound, the online loop.
  generate.py             How data/train.txt and data/valid.txt were made.
```

`evaluate.py` and the OR-Library files sit above `run/`, the project root. The
sandbox copies the project directory and nothing above it, so a candidate
cannot read the test data.

## Protocol

- `excess_train` — 20 generated instances of 120 items. Reported.
- `excess_valid` — 20 generated instances of 250 items. **Selected on**, via an
  explicit `objective:` weighting only this metric.
- binpack1–4 — measured once, on the winner, by `evaluate.py`.

Selection on validation is not decoration. Trial 9 had the best training score
of the run (5.930 against the seed's 6.646) and a worse validation score than
the winner; under cadence's default objective, which sums every declared
metric, it would have won.

## Instances

OR-Library `binpack1`–`binpack4`: 20 instances each of 120, 250, 500 and 1000
items, sizes uniform on [20, 100], capacity 150. Generated train/valid sets
use the same distribution and format.

The denominator is the L2 bound, not the optimum, so 0% is unreachable even
offline.

## Note on the metric

Excess is **pooled** — total bins over total bound — not averaged per
instance. Averaged, first fit on binpack1 is 6.4111; pooled it is 6.4220, and
the paper says 6.42. Averaging reproduces nothing and looks almost right.

## Running

```sh
python evaluate.py                                    # baselines
python evaluate.py winners/20260908-030111-f02ae0.py  # the winner

cd run && cadence run --config ../../../arms/bin-packing-10.cadence
```
