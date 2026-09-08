# 2026-09-08 — online bin packing, and the first held-out number

cadence at `26bd7b4`. Run `20260908-030111-f02ae0`, experiment
`bin-packing-online`, 10 trials, gemini-3.6-flash, recorded to the local
Postgres on 5433.

## What happened

Built `problems/bin-packing` from FunSearch's combinatorial benchmark, ran it,
and measured the winner on OR-Library data it had never seen.

Held-out results, percentage of bins over the L2 lower bound, lower is better:

| | binpack1 | binpack2 | binpack3 | binpack4 |
|---|---|---|---|---|
| First Fit (published) | 6.42 | 6.45 | 5.74 | 5.23 |
| First Fit (ours) | **6.42** | **6.45** | **5.74** | **5.23** |
| Best Fit (published) | 5.81 | 6.06 | 5.37 | 4.94 |
| Best Fit (ours) | **5.81** | **6.06** | **5.37** | **4.94** |
| cadence, 10 trials | 5.61 | 5.22 | 3.80 | 3.22 |
| FunSearch (published) | 5.30 | 4.19 | 3.11 | 2.47 |

cadence beats best fit on all four, closing 40 / 45 / 69 / 70 percent of the
distance from best fit to FunSearch. The gap closes *more* on the larger sets,
which is the same direction FunSearch reported: a heuristic evolved on
120-item instances holds up on 1000-item ones.

None of those four sets was visible to the run. They live above the cadence
project root and the sandbox copies the project directory and nothing above
it, so this is a held-out number by construction rather than by promise.

## The harness was verified before a model call was spent

First fit and best fit are ten lines each, so we ran them and compared against
Table 1. All eight cells matched exactly — but only after one correction:
excess is **pooled** (total bins over total bound), not averaged per instance.
Averaged gives 6.4111 where the paper says 6.42. A third-significant-digit
error, and exactly the kind that leaves a broken harness looking right.

This is the property circle-packing does not have. Its 2.16667 grid baseline
is our own invention; nobody published it, so it cannot check anything. **A
problem whose baselines are code is worth more than one whose baselines are a
number.** That is now the first thing COVERAGE.md says.

## The run, trial by trial

Selection was on validation only, by an explicit `objective:` weighting
`excess_valid`. Train is reported so overfitting would be visible.

| trial | fingerprint | train | valid | scoring |
|---|---|---|---|---|
| baseline | 94a5b7fd | 6.64622 | 5.88529 | 190ms |
| 1 | c5d1162f | 9.10020 | 7.08229 | 383ms |
| 2 | e866688a | 6.64622 | 5.68579 | 303ms |
| 3 | 0d4ab1d2 | 9.10020 | 7.08229 | 304ms |
| 4 | 1c02f460 | 6.64622 | 5.88529 | 176ms |
| 5 | 5862a76b | 6.74847 | 5.53616 | 177ms |
| 6 | 707b7698 | 6.74847 | 5.53616 | 180ms |
| **7** | **3c1ec04a** | **6.64622** | **5.13716** | **177ms** |
| 8 | d428e453 | 6.74847 | 5.53616 | 84ms |
| 9 | 1ee0bf8a | 5.93047 | 5.58603 | 82ms |

Two things worth reading off this table.

**Trial 9 is why selection was on validation.** It has the best training score
of the run, 5.93047 against the baseline's 6.64622, and a *worse* validation
score than the winner. Had the objective summed both metrics — which is what
cadence does by default when a manifest names two — trial 9 would have been in
contention on the strength of twenty instances it had been tuned against.
Overfitting was not hypothetical here; it showed up in a ten-trial run.

**Trials 1 and 3 are the same wrong idea, twice.** Different fingerprints,
identical metrics to six decimals. So are 5, 6 and 8. The search rediscovers
its own dead ends, and nothing in the loop notices.

## The verdict cache, and what it did not do

This problem's whole reason for existing is that it can declare
`verifier.tolerance` and switch on the content-addressed verdict cache — the
one keyed `(candidate_hash, task_hash, seeds_hash)` with no `run_id`, which
circle-packing structurally cannot exercise.

The path is live. Eleven verdict rows written, all with the same
`task_hash` `ed810b83` and `seeds_hash` `b4fc5c9e`, and recomputing both from
the project as it stands today reproduces those exact values — so every one of
them is reusable by a future run without spending the measurement again.

It got **zero hits inside this run**. Trials 5, 6 and 8 scored identically to
six decimals and are three distinct rows, because content addressing keys on
the text and those were three different spellings of one idea. Worth stating
plainly: the cache saves a re-measurement, not a re-derivation. A cross-run
hit is still unobserved and is the next thing to check.

`score.py` measures the training set twice and refuses any candidate whose two
scores differ, so the determinism the tolerance asserts is enforced rather
than trusted. Nothing was refused.

## `--resume` closed against a real interruption

The first invocation died at trial 3 on a gemini `503: This model is currently
experiencing high demand`, having spent 2 calls. `cadence run --resume` said:

    resuming run 20260908-030111-f02ae0 from trial 2 with 2 results already scored

and went straight to trial 3. Neither paid-for call was bought again. That row
in COVERAGE.md was a gap this morning and was closed by an interruption
nobody arranged.

The 503 is also the second sighting of **one exhausted retry ending the whole
run**. `attempts: 4` was set. `TrialAbandoned` exists and the loop already
handles a barren trial; a provider being briefly busy should cost a trial, not
a run.

## Friction

1. **`cadence check` reports an objective the run will not use.** The manifest
   declares `objective: {weighted_sum: {excess_valid: -1.0}}` and the built
   objective is exactly that, confirmed. check prints
   `objective   weighted_sum over excess_train to minimize, excess_valid to
   minimize` — a description of the *metrics*. A user declaring a custom
   objective gets no confirmation it took effect and would reasonably conclude
   it was ignored. On this problem the difference is the difference between
   selecting the winner and selecting the overfitted trial 9.

2. **`spend.calls` counts the invocation, not the run.** The resumed
   invocation reported 8 calls. The run has 10 `model_calls` rows. Anyone
   reading the report of a resumed run undercounts what it cost. Compounds
   with the already-known gap that retried attempts are not counted at all.

3. **`cadence apply` needs `--config` when the run used one**, and says so
   clearly — `was not run against this project's manifest ... Use the root
   that run used, or --config to name the manifest it used`. Working as
   intended; noted because the guard fired on a real mistake rather than a
   test.

## Cost

10 model calls, 6689 tokens in, 2027 out. Model latency 19.7s to 131.3s,
median about 73s. Scoring 82ms to 383ms. Wall clock about 20 minutes across
both invocations, essentially all of it waiting on the model.

## Reproducing

    cd problems/bin-packing && python evaluate.py            # baselines only
    python evaluate.py winners/20260908-030111-f02ae0.py     # the winner

    cd run
    GEMINI_API_KEY=... DATABASE_URL=... \
      cadence run --config ../../../arms/bin-packing-10.cadence
