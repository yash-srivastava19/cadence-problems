# Lean proofs, miniF2F

One tactic, applied to every theorem in a set. The score is how many close.

Source: Zheng, Han and Polu, *miniF2F: a cross-system benchmark for formal
Olympiad-level mathematics*, ICLR 2022. Statements from
[miniF2F-lean4](https://github.com/yangky11/miniF2F-lean4) `5746b7d6c478`,
proofs stripped to `sorry`.

## Results

| | closed |
|---|---|
| `sorry` | 0/25 |
| `aesop`, `simp_all` alone | 1/25 |
| `norm_num`, `omega` alone | 2/25 |
| `linarith`, `nlinarith` alone | 6/25 |
| **seed** — the tidy baseline's list (`norm_num`, `ring_nf`, `linarith`, `nlinarith`) | **7/25** |
| a 9-way modern combinator, adding `positivity`, `omega`, `decide`, `simp_all`, `aesop` | 9/25 |
| cadence | not yet run |

Held-out numbers come from `evaluate.py` on the full 244+244 splits. Published
context: the paper's `tidy` baseline closes **16.8%** of valid and **18.0%** of
test — but that is a best-first search over a curated tactic list, 128
expansions deep, not a single tactic. It is quoted for scale, not as a
like-for-like target. Its average successful proof is 1.8 tactic steps, which
is why a one-shot combinator is in the same league at all.

## Layout

```
theorems/valid.lean       244 statements. Never copied into the sandbox.
theorems/test.lean        244 statements. Never copied into the sandbox.
evaluate.py               The held-out test. Not part of any run.
run/                      The cadence project — all a candidate can see.
  tactic.lean             The program. The marked region is the tactic.
  train.lean              25 statements, the first mathd_algebra of valid.
  score.py                Splices, compiles once, counts what closed.
  environment.txt         The Lean and Mathlib the scores were measured on.
```

## Setup

Mathlib is **7.5 GB** and must live outside the project. The sandbox copies the
project directory for every trial and hashes every file in it, so Mathlib
inside `run/` would not be slow, it would be fatal.

```sh
curl -sSfL https://elan.lean-lang.org/elan-init.sh | sh -s -- -y
mkdir -p ~/.cache/cadence && cd ~/.cache/cadence
lake new proving math          # fetches Mathlib and its build cache
```

`score.py` finds it at `~/.cache/cadence/proving`, or wherever
`CADENCE_LEAN_PROJECT` points.

## Why environment.txt exists

`verifier.tolerance` is set, which switches on the cross-run verdict cache.
That cache is keyed on `task_hash`, which covers every file beside the
candidate — and Mathlib is not one of them. A Mathlib bump would therefore
reuse verdicts measured against a different library, silently.

`environment.txt` pins the toolchain and the Mathlib revision, sits inside the
workspace where the digest sees it, and `score.py` refuses to score if it does
not match the live project.

## Sandbox settings are load-bearing

`memory_mb: 32768`. This is address space, not resident memory — Lean mmaps
thousands of `.olean` files, so `import Mathlib` needs more than 16GB of it.
Measured: at 8192 Lean reports `failed to read file .../Mathlib/RingTheory/...`
and at 16384 `failed to create thread`. Neither message mentions memory, and
both look like a broken Mathlib install rather than a limit.

`score.py` also restores `HOME` and `ELAN_HOME` for the compile. The sandbox
points `HOME` at the copied workspace, which hides elan's installed toolchains,
and `lake` then downloads Lean again on every trial.

## Five ways the scorer could lie

All five were hit while building this, all five now guarded:

1. **A linter warning is not a failure.** `first | ... | (tac; done)` proves
   the goal and then warns that `done` did nothing. Counting that as a failure
   scored every correct candidate at 0 while a plain tactic scored 6.
2. **Lean exits after 100 errors.** Theorems it never reached emit no
   diagnostic, which reads as proved — a 244-theorem file scored 143/244, or
   58.6%, against a published 16.8%. `evaluate.py` compiles in chunks of 50;
   `score.py` refuses if the cap is ever reported.
3. **A broken header means nothing below it was tried.** Blaming the candidate
   for that is the one failure a search cannot see.
4. **A relative path scored 25/25.** `python score.py` gives a relative
   `__file__`, the compile runs with `cwd` set to the Lean project, and Lean
   looked for the file inside Mathlib. It printed `no such file or directory`,
   no diagnostic matched any theorem, and every theorem counted as closed.
5. **A path the regex did not match would do the same.** The diagnostic
   pattern is no longer anchored on the filename; exactly one file is
   compiled, so line and column are unambiguous.

Only an `error:`, or the warning that a declaration used `sorry`, counts as
unproved. The general guard behind 4 and 5: **if Lean exits non-zero and
nothing is attributable to a theorem, that is not a measurement** — report
`cadence_verifier_error`, never a score.

## Running

```sh
python evaluate.py                    # the current tactic, held-out
cd run && cadence run
```
