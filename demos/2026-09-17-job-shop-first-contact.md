# 2026-09-17 — job shop runs, and a malformed candidate ends the run

First two runs on `problems/job-shop`, one per model, both stopped after a
single scored trial. Neither is a result. Both are useful.

    20260917-032417-42409b   gemini-3.6-flash   1 trial   stopped: 429
    20260917-032237-ebce04   gemma3:4b (local)  1 trial   stopped: MarkerError

Seed is MWKR: `excess_train 11.4057`, `excess_valid 13.7445`, and 17.29%
pooled over optimal on the 33 held-out instances.

## What worked

The harness is proven end to end on both models. The region parses to the one
body line, candidates apply cleanly, `score.py` runs in 0.19s, the determinism
check holds, and both runs stopped in a state that can be picked up.

Both models' first candidate scored exactly the seed's numbers. Gemini's was
`[o.work_remaining for o in ops]` -- the seed with the `float()` cast dropped.
gemma3's was the same thing as an explicit loop. Behaviourally identical
rewrites on trial 1 of a brand new problem, which is the duplicate
rediscovery seen at 30% on bin-packing run 1 and 41% on run 2.

## The bug: a candidate can end a run by echoing the markers

gemma3's second candidate returned the marker lines inside its replacement:

    # CADENCE:BEGIN
    # CADENCE:BEGIN
    scores = []
    ...
    # CADENCE:END
    # CADENCE:END

The `region` template says "Do not include the marker lines themselves". It
did anyway. cadence noticed -- `MarkerError: a program needs exactly one
CADENCE:BEGIN and one CADENCE:END; found 2 and 2` -- and then ended the run.

`MarkerError` is a `SetupError`, and `SetupError` is caught in preflight.py
and nowhere in the trial loop. That classification is right for a malformed
*project*: the user should be stopped. It is wrong for a malformed
*candidate*, which should cost a trial.

The verdict taxonomy covers what happens inside the sandbox -- invalid,
crashed, timed_out, out_of_memory, verifier_error. A candidate that is
malformed *before* the sandbox has no state in it, so it escapes as a setup
error. A model that cannot reliably follow "do not repeat the markers" can
therefore never complete a run, however good its other candidates are.

Third time this week the same shape has appeared: one bad event ends a whole
run rather than a trial. The others were an exhausted retry and a finished-run
resume.

## Still open

- No number yet. Gemini's run is `failed` on quota and resumable with the next
  day's twenty; that is the one whose result belongs in the problems table.
- Whether anything beats MWKR's 17.29% held-out is unanswered.
- `baselines/` is still empty.
