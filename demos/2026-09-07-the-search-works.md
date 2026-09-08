# 2026-09-07 — it works, and the harness was the problem

**cadence:** `26bd7b4` (main, after #77–#82)
**arm:** `arms/circle-packing-full.cadence` — 6 trials, sandbox 120s, model
timeout 300s

```
  baseline   sum_radii 2.16667
  trial 1      scored   1.71271
  trial 2      scored   0          (invalid packing, scored 0 with a reason)
  trial 3      scored   2.60228
  trial 4      scored   2.60455    <- winner
  trial 5    failed after 4 trials (429: daily quota exhausted)
```

| | sum_radii |
|---|---|
| grid baseline | 2.16667 |
| **cadence, 4 trials** | **2.60455** |
| AlphaEvolve | ~2.635 (still unverified) |

**+20.2% over the baseline, within 1.2% of the published figure, in four
trials.** Verified independently: `cadence apply` wrote the winner into a
copy and `score.py` scored it 2.600 / 2.608 / 2.605 across the three seeds.
The constraint check passed, so the packing is real — no overlaps, nothing
outside the square.

## The finding: a 30s sandbox timeout was suppressing every good candidate

Two earlier runs produced six candidates, all between 1.49 and 1.77, all
*below* a 6x6 grid. The obvious reading was that the search does not work.

It was the harness. The model writes long optimizers -- Adam with a penalty
schedule and dozens of restarts -- and at `sandbox.seconds: 30` they were
being killed part-way and scored on whatever half-converged state they had
reached. Give them 120s and the same approach lands at 2.60.

So the earlier numbers were not measuring the search. They were measuring how
much of the search fits in thirty seconds.

**This is the more general lesson: before concluding a search is weak, check
whether the harness is killing its candidates.** `check` reports the sandbox
limits, and it reported them correctly the whole time -- nobody read them as
a constraint on what could win.

## What else this run proved

- **The seed-scoring fix (#82) behaves in both directions.** The previous run
  reported the baseline as the winner because everything was worse. This one
  reported a child, because one was better.
- **Invalid answers score 0 and do not crash.** Trial 2 returned an
  overlapping packing, scored 0 with a reason, and the run carried on. That
  is the split `score.py` was built for.
- **Narration made this legible while it ran.** Watching 2.60 arrive at trial
  3 is what made the timeout hypothesis obvious.

## Still open

The run ended on a real 429: `limit: 20` for
`generate_content_free_tier_requests`. That confirms the daily cap exactly.
It is a clean stop, not a bug -- but it is still the case that one exhausted
retry ends the whole run rather than the trial.

Untested: `cadence run --resume 20260907-025816-571b77` should carry on
tomorrow without re-buying the four answers already in `model_calls`. Worth
doing as the first thing next session, because it exercises the resume path
against a real interruption rather than a synthetic one.

## Budget

20 of 20 requests used. Quota resets daily.
