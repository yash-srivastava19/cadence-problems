# cadence-problems

Staging for [cadence](https://github.com/yash-srivastava19/cadence): real
problems with published numbers, run end to end before a feature counts as
done.

## Layout

```
problems/<name>/   one problem, one cadence project root
arms/              small-budget manifests for `cadence run --config`
baselines/         control arms — single-shot, random, hill-climb
mistakes/          deliberately broken projects; asserts cadence's error text
demos/             dated session records
COVERAGE.md        cadence feature → the problem that exercises it
```

## Problems

| Problem | Source | Baseline | Ours |
|---|---|---|---|
| [`circle-packing`](problems/circle-packing) | AlphaEvolve, n=26 | grid, 2.16667 | 2.60455 |
| [`bin-packing`](problems/bin-packing) | FunSearch, Nature 625 T1 | best fit, 5.81/6.06/5.37/4.94 | 5.61/5.22/3.80/3.22 |
| [`lean-proofs`](problems/lean-proofs) | miniF2F, ICLR 2022 | tidy tactic list, 7/25 | not yet run |

## Rules

1. **Scoring lives outside the edited region.** A program that can score
   itself measures the model's imagination.
2. **An invalid answer scores at the floor with a reason; only broken code
   crashes.** Conflating them quarantines candidates that were merely wrong.
3. **Prefer baselines that are code.** `bin-packing` reproduces all eight
   published baseline cells before a model call is spent, so a broken harness
   is caught for free. `circle-packing` cannot — its grid baseline is our own
   invention.
4. **Published SOTA is context, not a target.** Those runs used budgets we do
   not match. The comparison that pays is against controls at our own budget:
   if cadence cannot beat "ask the model N times and keep the best", nothing
   downstream matters.

## Running one

```sh
export GEMINI_API_KEY=...
export DATABASE_URL=...        # optional; without it nothing is recorded
cadence check problems/circle-packing
cadence run   problems/circle-packing
```

Write the session up in `demos/`, including what went wrong. Friction goes
there and then to cadence's tracker, not into a document beside the problems.
