# cadence-problems

A test bed for [cadence](https://github.com/yash-srivastava19/cadence). Two
questions, run at the same time, kept apart on purpose:

**A. Is cadence pleasant to use?** Sample size: one, me. Output:
[`FRICTION.md`](FRICTION.md). Costs nothing, and it is lost the moment a snag
gets fixed silently. Write it down before fixing it.

**B. Does cadence's search actually do anything?** Sample size: problems x
trials x dollars. Output: numbers in each problem's README.

The two are separate because a bad number is not evidence of bad ergonomics,
and a smooth install is not evidence the search works.

## Layout

```
problems/<name>/     one problem, one cadence project root
  .cadence           the manifest
  <program>.py       the seed, with CADENCE:BEGIN / CADENCE:END markers
  score.py           the verifier -- outside the markers, never edited
  IMPROVE.md         what the model is told
  README.md          provenance, published numbers, our numbers
baselines/           control arms, for answering B honestly
FRICTION.md          the log for A
```

Each problem is its own directory because that is what cadence takes:
`cadence run problems/circle-packing` reads `.cadence` from that directory.

## The rule every problem follows

**Scoring lives outside the edited region.** If the file the model rewrites
can also decide its own score, the benchmark measures the model's
imagination. `score.py` imports the program, checks the constraints, and
prints one metric line.

## What "better" means

Comparing against a published SOTA number first is a trap: those runs used
budgets we will not match, so a worse number tells us nothing about our
search. The comparison that pays is against controls we run ourselves at the
same budget.

| Arm | Answers |
|---|---|
| Single-shot: ask the model once, keep it | What does zero search buy? |
| Random: ask N times independently, keep the best | Does selection help at all? |
| Hill climb: always mutate the current best | Is the tournament better than greedy? |
| cadence | The number we actually have |
| Published SOTA | Sanity check, much later |

If cadence does not beat "ask the model 20 times and keep the best," nothing
downstream matters. That is the cheapest and most informative experiment
here, and it comes first.

## Running one

```sh
export DATABASE_URL=...          # optional; without it nothing is recorded
export GEMINI_API_KEY=...
cadence check problems/circle-packing
cadence run   problems/circle-packing
```

`cadence check` is free and catches most mistakes. Always run it first.
