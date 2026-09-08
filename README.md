# cadence-problems

Staging for [cadence](https://github.com/yash-srivastava19/cadence). Every
feature gets used here, on a real problem, before it counts as done.

Not a demo folder. The question it answers is: **if we ship this cadence,
does a real project still work?** Anything that only ever runs in cadence's
own test suite has not been tested against the thing it is for.

## Three jobs

**1. Exercise the feature surface.** [`COVERAGE.md`](COVERAGE.md) maps every
part of cadence to the problem that uses it. Gaps are visible on purpose.

**2. Keep an audit log.** [`demos/`](demos/) holds one record per session:
which cadence commit, what ran, what it answered, what it revealed. That log
is how a product proposition gets built out of evidence rather than memory.

**3. Anticipate mistakes.** [`mistakes/`](mistakes/) holds one broken
project per way a user gets it wrong, each asserting what cadence says about
it. A first hour is mostly errors, so the error text is the product.

**4. Produce numbers.** Each problem's README carries its own results and the
published figures it is measured against.

## Layout

```
problems/<name>/     one problem
  .cadence           the manifest
  <program>.py       the seed, with CADENCE:BEGIN / CADENCE:END markers
  score.py           the verifier — outside the markers, never edited
  IMPROVE.md         what the model is told
  README.md          provenance, published numbers, our numbers
arms/                small-budget manifests, used with `cadence run --config`
mistakes/            deliberately broken projects — is the error any good?
demos/               dated session records — the audit log
baselines/           control arms, for judging the search honestly
COVERAGE.md          feature → problem
```

Each problem is its own cadence project root, because that is what cadence
takes: `cadence run problems/circle-packing` reads `.cadence` from there.
`bin-packing` nests the project one level deeper, in `run/`, so that its
held-out test data can sit outside the directory the sandbox copies.

## The problems

| Problem | Published source | What it covers |
|---|---|---|
| [`circle-packing`](problems/circle-packing) | AlphaEvolve, n=26 sum of radii | stochastic verifier, verdict cache **off** |
| [`bin-packing`](problems/bin-packing) | FunSearch, Nature 625 Table 1 | deterministic verifier, verdict cache **on**, two metrics, custom objective, a held-out test set |

Prefer a problem whose baselines are *code*. `bin-packing` reproduces all
eight published baseline cells before a model call is spent, so a broken
harness is caught for free. `circle-packing` cannot: its 2.16667 grid is our
own invention and nobody has published it.

## The rule every problem follows

**Scoring lives outside the edited region.** If the file the model rewrites
can also decide its own score, the benchmark measures the model's
imagination. `score.py` imports the program, checks the constraints, prints
one metric line.

Corollary: an invalid answer scores 0 with a reason. A crash is for broken
code. Conflating them teaches the run the wrong lesson and eventually
quarantines a candidate that was merely wrong.

## What "better" means

Comparing against a published number first is a trap: those runs used budgets
we will not match, so a worse result says nothing about our search. The
comparison that pays is against controls we run ourselves, at the same budget.

| Arm | Answers |
|---|---|
| Single-shot: ask once, keep it | What does zero search buy? |
| Random: ask N times, keep the best | Does selection help at all? |
| Hill climb: always mutate the best | Is the tournament better than greedy? |
| cadence | The number we actually have |
| Published SOTA | Sanity check, much later |

If cadence cannot beat "ask the model 20 times and keep the best", nothing
downstream matters.

## Friction

Observations go in the session's `demos/` record, then to cadence's tracker.
They are not kept as a document here — a friction list that lives beside the
problems is a list nobody acts on.

## Running one

```sh
export DATABASE_URL=...          # optional; without it nothing is recorded
export GEMINI_API_KEY=...
cadence check problems/circle-packing
cadence run   problems/circle-packing
```

Record the session in `demos/` afterwards, including what went wrong.
