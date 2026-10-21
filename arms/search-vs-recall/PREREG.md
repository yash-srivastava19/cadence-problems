# Search vs recall at equal cost (2026-10-18)

Written before any run. Question: does cadence's search (evolution, children
build on earlier results) beat asking the model the same number of times
independently and keeping the best (best-of-N recall)?

Why now: E1 vs E2 (Scrabble, 2026-10-04) tied, but with one run per arm. The
cache example peaked at trial 1. A reviewer (Aryan) asked whether LLM search
adds anything; this is the experiment that answers it for cadence.

## Design

- Code: cadence at commit 1a5bab7, unchanged during the run. Runs on EC2.
- Problems (deterministic scorers, as shipped in problems/):
  - bin-packing: search metric excess_valid (lower is better); held-out
    metric = mean excess over OR-Library binpack1..4 (evaluate.py), which no
    run can read.
  - circle-packing (n = 26): metric sum_radii (higher is better). No held-out
    set exists; the scorer checks geometry, so the score is the claim.
- Arms, identical except for the method:
  - search: one run, budget N = 4 trials (4 model calls), evolution as shipped.
  - recall: 4 runs of 1 trial each from the same start; no run sees another;
    keep the best by the search metric.
  Same start program, same IMPROVE.md hint, same model, same settings.
- Blocks: the Gemini free tier allows only a few calls a day per model, so
  each block is one model. Within a block, each problem gets one paired
  replicate (search vs recall). Arm order and problem order alternate between
  blocks so a quota cut hits both arms equally. A pair with a missing arm, or
  an arm with fewer than 4 measured trials, is dropped and counted.
- Models (one block each, in this order): gemini-3.6-flash, gemini-3.7-flash,
  gemini-3.8-flash, gemini-3.5-flash, gemini-3-flash-preview,
  gemini-2.5-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite,
  gemini-2.5-flash-lite. Free tier only; no paid calls.

## Measures

Primary, per problem: paired difference search minus recall in the winner's
score, with the sign set so positive means search is better. Bin packing uses
the held-out score; circle packing uses sum_radii. Reported as mean ± 95% CI
(t) over completed pairs, plus the sign count (search wins / ties / losses).

Secondary, recorded for every winner:
- bin packing: search metric minus held-out metric (the Goodhart gap);
- lines changed from the start program (diff size);
- tokens used per arm (search prompts are longer).

## Pass rule

Search counts as better than recall on a problem if the paired CI excludes 0
in its favour. Overall verdict "search helps" needs that on both problems.
"Tie" if the CI includes 0. With ~9 pairs per problem this detects only large
effects; a tie is weak evidence of no effect, not proof.

## Prior (honest)

A tie on both, as in E1/E2 and the cache. If anything, search ahead on
circle packing, where building on a good layout compounds, and no difference
on bin packing.

## Integrity

- Both scorers run the candidate inside the scorer's process (the known hole:
  a candidate can print its own score). Every winner is therefore re-scored
  in a fresh process outside cadence, and scanned for print/exit/atexit.
  A winner whose re-score disagrees with cadence's number is flagged and
  reported, not silently dropped.
- Copy-back from EC2 pulls only arms/search-vs-recall/results/, never this
  file.

## Amended before the rerun (2026-10-18, 12:47 UTC)

The first pair (block 0, gemini-3.6-flash, bin packing) is discarded. With no
`prompt.hints`, cadence rotates built-in hints, and the first is "make it
faster without changing what it returns". Every recall run has only a first
trial, so every recall attempt was told to copy the start program (all four
scored exactly the baseline). Search got four different hints. Unfair to
recall, so not used.

Fix: both arms get one hint on every trial, via `prompt.hints`:
"improve the score; changing what the code returns is allowed". Nothing else
changes. Block 0 restarts with whatever of gemini-3.6-flash's daily quota is
left; a cut pair is dropped and counted, as planned.

Second amendment (13:05 UTC): the rerun reused the run ids of the discarded
runs, so cadence refused to start them and `apply` returned the old winners.
That attempt's results are discarded too. Run ids now carry a suffix (r2) and
the driver refuses a run cadence did not start. gemini-3.6-flash's free quota
is spent for today, so block 0 will come back incomplete and be dropped, as
the design says.

Note (13:40 UTC): to cut cost the runner was moved to a 2-core machine after
block 1's circle-packing pair. Block 1's bin-packing pair had just started; it
restarts from scratch with run-id suffix r3 (a call already spent on it may
leave that model short of quota; if so the pair is dropped, as planned).
Circle-packing pairs in block 1 ran beside the BestBot job under heavy load;
later pairs run alone. The analysis reports this.

## Outcome (2026-10-18, 18 pairs attempted, 5 complete)

Most pairs were dropped, as the design allows, for reasons outside the
comparison: free quota already spent (429 on gemini-3.6-flash, gemini-3.5-flash
and others) and replies slower than cadence's read timeout. Dropped pairs
are kept in results/pairs.jsonl.

Complete pairs (re-scored outside cadence; every re-score matched, no
suspect patterns):

| block | model | problem | search | recall |
|---|---|---|---|---|
| 1 | gemini-3.7-flash | circle-packing | 2.6135 | 2.6296 |
| 4 | gemini-3-flash-preview | circle-packing | 2.4580 | 2.4053 |
| 7 | gemini-3.1-flash-lite | circle-packing | 2.1667 | 2.3170 |
| 6 | gemini-3.5-flash-lite | bin-packing (held-out) | 5.5444 | 5.5444 |
| 7 | gemini-3.1-flash-lite | bin-packing (held-out) | 5.5444 | 5.5444 |

Circle packing: search 1 win, 2 losses, mean difference -0.038 (n = 3, CI
not meaningful). Bin packing: 2 ties, both arms left the start program
unchanged. Verdict under the pass rule: no verdict -- too few pairs. Not
evidence for or against search.

Next, if run: the dropped pairs on a fresh day's quota, with a longer model
read timeout, written here as an amendment before the rerun.
