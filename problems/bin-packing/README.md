# Online bin packing

Items arrive one at a time, each is placed the moment it arrives and never
moved, and the goal is to use as few bins as possible. FunSearch used this as
its combinatorial optimization benchmark; the numbers below are its Table 1,
which we reproduce here before evolving anything.

## Why this problem is here

The row it fills in `COVERAGE.md` is **verdict cache on**. Circle packing has
`verifier.tolerance` deliberately absent, because a packing solver is
stochastic and a cached score for a candidate that scores differently twice is
not a cache, it is a wrong answer that never expires. That leaves the
content-addressed `verdicts` table -- keyed on `(candidate_hash, task_hash,
seeds_hash)` with no `run_id`, and therefore shared across every run -- as the
largest completely untested part of cadence.

A bin count is an integer. This problem is deterministic, declares a tolerance,
and switches that path on. It also fills **multi-metric manifest** and **custom
objective plugin**, and gives the first genuine **crash** path: a priority
function returning the wrong shape raises, where a bad packing merely scores
badly.

## The one thing circle packing could not do

The baselines here are *code*, not numbers we took on faith. First fit and best
fit are ten lines each. We run them, and if they do not reproduce the published
table the harness is wrong and we know it before spending a single model call.

    $ python evaluate.py

                              binpack1  binpack2  binpack3  binpack4
    First Fit (published)         6.42      6.45      5.74      5.23
    Best Fit (published)          5.81      6.06      5.37      4.94
    FunSearch (published)         5.30      4.19      3.11      2.47

    First Fit (ours)              6.42      6.45      5.74      5.23
    Best Fit (ours)               5.81      6.06      5.37      4.94

All eight cells, exact. Getting there took one correction: excess must be
*pooled* -- total bins over total lower bound -- not averaged per instance.
The two differ in the third significant digit, which is exactly enough to make
a wrong harness look right.

Circle packing's baseline was a 6x6 grid we invented ourselves. Nobody has
published it, so it could not check anything.

## Layout

    heldout/binpack1..4.txt   OR-Library. Never copied into the sandbox.
    evaluate.py               The held-out test. Not part of any run.
    run/                      The cadence project. This whole directory, and
                              only this directory, is what a candidate sees.
      .cadence
      heuristic.py            The program. priority() is the marked region.
      score.py                Train and validation excess. Runs the scoring.
      packing.py              Parsing, the L2 bound, and the online loop.
      generate.py             How data/train.txt and data/valid.txt were made.
      data/                   Generated instances only.

`evaluate.py` and the OR-Library files sit *above* `run/`, which is the cadence
project root. The sandbox copies the project directory and nothing above it, so
a candidate is physically unable to read the test sets. That is what makes the
final number a held-out number rather than a promise.

## Protocol

FunSearch evolved on generated instances the size of binpack1, selected the
winner on generated instances the size of binpack2, and tested on binpack1
through binpack4. This reproduces that:

- `excess_train` -- 20 generated instances of 120 items. Reported.
- `excess_valid` -- 20 generated instances of 250 items. **Selected on**, via
  an explicit `objective:` weighting only this metric.
- binpack1..4 -- measured once, on the winner, by `evaluate.py`.

Reporting train as well as validation is how overfitting becomes visible: a
candidate that has learned these twenty instances rather than the problem shows
train falling while validation does not follow.

Baselines on the generated sets, for reference:

    train  First Fit 7.16%   Best Fit 6.65%
    valid  First Fit 6.38%   Best Fit 5.89%

The seed program is best fit, the same starting point FunSearch used.

## Instances

OR-Library `binpack1`-`binpack4`: 20 instances each of 120, 250, 500 and 1000
items, sizes drawn uniformly from [20, 100], bin capacity 150. The third number
in each instance header is the best known *offline* packing; `packing.py` reads
and discards it, because comparing an online heuristic against an offline
optimum would flatter every result.

Our generated sets use the same format and the same distribution. Their third
header number is the L2 lower bound, not a best known packing -- nobody has
solved them offline.

The denominator throughout is the Martello-Toth L2 bound. It is a bound and not
the optimum, so 0% is not reachable even offline: a heuristic at 4% is not "4%
worse than perfect".

## Running it

    cd run
    GEMINI_API_KEY=... DATABASE_URL=... cadence run --config ../../../arms/bin-packing-10.cadence

Ten trials rather than the twenty in `.cadence`, because the free Gemini tier
allows twenty requests a day and retries cost roughly another 40% that cadence
does not count. Then:

    cadence apply <run-id>     # writes the winner over heuristic.py
    cd .. && python evaluate.py

## Source

Novikov et al., *Mathematical discoveries from program search with large
language models*, Nature 625, 468-475 (2024). Table 1 and Appendix E.4.
