# 2026-09-16 — a better validation score and a worse result

Run `20260916-095047-a3b334`, experiment `bin-packing-online`, 17 trials,
gemini-3.6-flash, `arms/bin-packing-from-winner.cadence`. Stopped at trial 18
on a real 429, `limit: 20` for `generate_content_free_tier_requests`.

Not a resume. Run `20260908-030111-f02ae0` finished cleanly, and a finished run
is deliberately not resumable, so this is a new lineage seeded with that run's
winner via `cadence apply`. Only the best program carries over, not the
population.

## The result, and why it is a bad one

Selection metric, on generated 120-item validation instances:

    5.137157   seed (run 1's winner)
    4.837905   trial 2        -5.8%

Held out, percentage of bins over the L2 bound, lower is better:

    |                | binpack1 | binpack2 | binpack3 | binpack4 |
    | items          |      120 |      250 |      500 |     1000 |
    | best fit       |     5.81 |     6.06 |     5.37 |     4.94 |
    | run 1 winner   |     5.61 |     5.22 | **3.80** | **3.22** |
    | run 2 winner   | **5.20** | **5.17** |     4.22 |     3.73 |
    | FunSearch      |     5.30 |     4.19 |     3.11 |     2.47 |

Validation improved 5.8%. binpack1 improved enough to beat FunSearch's
published 5.30 — the first published cell this repo has beaten. And binpack3
and binpack4 got **11% and 16% worse**.

## Why, mechanically

Run 1's winner penalises any bin left in the dead zone. Run 2's winner smooths
that into a single ramp, and says so in its own docstring: waste is "scored
smoothly across all waste values ... without artificial cliffs".

Score for a bin against the units it would be left with:

    rem      run 1     run 2
      5      +75.0    +110.0
      6      -90.0     +92.0    <- run 2 still finds this attractive
      8     -120.0     +56.0
     10     -150.0     +20.0
     11     -165.0      +2.0
     12     -180.0     -16.0

Run 1 refuses any bin from 6 units onward. Run 2 accepts up to 11. On 120-item
instances that is a good trade and the validation set says so. On 1000-item
instances those stranded units compound, which is exactly where it lost.

The generalisation gradient that made run 1 interesting -- better on instances
larger than anything it trained on -- has been destroyed by optimising the
metric harder.

## What this is an instance of

The same failure as trial 9 of run 1, one level up. There, a candidate with the
best training score and a worse validation score would have won under the
default summed objective, and an explicit `objective` block prevented it. Here
the explicit objective worked exactly as written and still produced a worse
heuristic, because **validation is 120-item instances and the held-out sets are
not**. Selecting honestly on the wrong distribution is not a selection bug.

`COVERAGE.md` has no row for "the selection metric disagrees with the
held-out metric". It should.

## Also covered today

- **crash to quarantine.** Trial 8 raised `IndexError: list index out of range`
  from `V[rem] - 0.85 * V[left]`, was recorded as `crashed`, and the run carried
  on. That row was `available`, not `covered`. It is covered now.
- **429 against a real cap**, again confirming `limit: 20`. The run is left
  `failed`, so unlike run 1 it is resumable tomorrow.

## Friction

**`--resume` on a finished run leaks a database error.** `restore.resume_from`
correctly refuses a FINISHED run, but nothing surfaces the refusal: the run
proceeds as fresh, tries to insert a duplicate `runs` row, and the user gets
`duplicate key value violates unique constraint "runs_pkey"`. The tell is that
it printed `recording run <id>` rather than `resuming`. Two-line fix in
`_refuse_to_overwrite`.

**Duplicate candidates got worse.** Trials 2, 5, 13 and 17 all score exactly
5.725971 / 4.837905. Trials 3, 7 and 9 all score 6.74847 / 4.98753. Seven of
seventeen trials, about 41%, bought an answer the run already had -- up from
30% in run 1. `spend` reported 18 calls, 0 replayed.

## Still open

- `baselines/` is still empty. Seventeen trials that produce a worse held-out
  result make the absence of a control arm more glaring, not less.
- The right fix here is probably a held-out-size-mixed validation set, or
  multiple metrics with the objective naming the large-instance one. Both are
  experiments, not patches.
