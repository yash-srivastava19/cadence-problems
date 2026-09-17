# 2026-09-10 — cadence loses to a one-liner

Run `20260910-022826-4fda88`, experiment `lean-mathd-numbertheory`, 10 trials,
gemini-3.6-flash, recorded to the local Postgres on 5433. cadence at `26bd7b4`.

The first cadence run on a Lean problem, and the first time this repo has had
a reference point good enough to lose to.

## The result

All three measured by the same `score.py`, on the same 60 theorems.

| | closed | lines |
|---|---|---|
| seed — the miniF2F paper's `tidy` tactic list | 20/60 | 4 |
| **cadence, 10 trials, 10 model calls** | **37/60** | 38 |
| a 9-way `first \| ...` combinator, written by hand in under a minute | **39/60** | 9 |

cadence improved the seed by 85% and still lost. The evolved tactic is four
times longer, carries a nine-tactic preprocessing chain and 23 alternatives,
and closes two fewer theorems than nine tactics in a flat list.

## Trial by trial

| trial | closed | | trial | closed |
|---|---|---|---|---|
| baseline | 20 | | 5 | **37** |
| 1 | 20 | | 6 | 37 |
| 2 | 11 | | 7 | 37 |
| 3 | 20 | | 8 | 20 |
| 4 | 19 | | 9 | 37 |

Scoring 12.6–24.0s per trial; model calls 20.3–86.4s. 9970 tokens in, 3361 out.

Two things to read off this. **The search found its answer at trial 5 and then
stopped**, returning 37 three more times without improving — the same plateau
the cache experiment showed. Half the budget bought nothing. And **trial 8 went
back to 20**, the seed's score, so the population was still sampling parents
that had been superseded four trials earlier.

## Why this is the most useful run so far

`README.md` has said since the repo was created that the comparison that pays
is against controls we run ourselves, and `baselines/` has been empty the whole
time. This is what that gap was hiding.

Nothing about the run looks wrong. The seed was the published baseline, the
verifier was guarded five ways, the metric moved 20 → 37, and every number is
reproducible. Reported on its own it reads as a clear success. It is only a
success until somebody spends a minute writing the obvious alternative.

The 9-way combinator is not a clever control. It is `first` over nine standard
Mathlib tactics, and every one of them is named in `IMPROVE.md`, so the model
had the ingredients and assembled something worse. The interesting failure is
not that it did badly — it is that **it built complexity that cost it two
theorems**, and no part of the loop can notice that a simpler candidate would
have scored higher, because a simpler candidate was never proposed.

## What this does not say

- One run, one tier, one model, ten trials. It does not say the search cannot
  beat a one-liner; it says it did not here.
- The real control arms are still unwritten. `random_search.py` — ask the model
  ten times independently and keep the best — is the number that would tell us
  whether the evolution loop contributes anything over sampling. Without it,
  "cadence got 37" and "ten samples got 37" are indistinguishable.
- `mathd-numbertheory` may be the friendliest tier for a one-liner, because
  `omega` and `decide` are decision procedures that close whole classes
  outright. A tier where no single tactic dominates might tell a different
  story.

## A benchmark caveat found the same day

[miniF2F-Lean Revisited](https://arxiv.org/pdf/2511.03108) corrects **over 300
of the 488** Lean statements. Documented defects include formal statements that
contain the answer the prover is supposed to find — trivially provable, and
exactly what `omega` and `decide` would close.

So an unknown share of both the 37 and the 39 may be theorems that prove
nothing. The paper ships corrected variants (`miniF2F-v2s`, `v2c`); v2c removes
the given solution and replaces it with `sorry`. Re-measuring against v2c would
say how much of our number is real. Same shape as the pooled-versus-averaged
correction on bin packing: a benchmark detail that makes a wrong number look
right.

## Friction

Nothing new in cadence. `check`, the run, the recording and the narration all
behaved. The five scorer guards written yesterday all held: no
`cadence_verifier_error` fired during the run.
