# 2026-09-06 — first contact

**cadence:** `5c30f55` (main, dirty: no)
**database:** local, `localhost:5433`, migration `c4e81b90d7a2`
**goal:** stand up the staging repo; find out whether concurrent runs contend.

## What ran

| Command | Result |
|---|---|
| `cadence runs list` | worked once env was loaded; 6 runs, 4 stale |
| `cadence run examples/lab` x2 concurrent | both failed, 0 trials, `TerminalModelError` |
| `cadence check examples/lab` | **exit 0, "ready"** — for a project that cannot run |
| `python problems/circle-packing/score.py` | 2.166667, baseline grid |

Circle packing has not been run through cadence yet — needs `GEMINI_API_KEY`.

## What it answered

**Concurrent runs with distinct ids do not contend.** Two runs started in the
same second got distinct generated ids, separate `events` sequences (0–3
each), and no lock collision. Not tested: two processes on the *same* run id,
where `Journal._next_seq` does select-max-then-insert under a per-process
`LocalLocks` and would race. Arms use distinct ids, so this does not block us.

Consequence: the cloud story is a bigger machine and a shell loop. No job
submission API is needed to run the benchmark suite in parallel.

## What it revealed

Seven observations, raised separately — see the tracker. Ranked:

1. **high** — `cadence check` prints "scripted, which has no answers in it"
   and then "ready", exit 0. `preflight.py:141` omits `ok=False`, so the
   finding never reaches `_refuse_a_project_check_would_refuse`.
2. **blocker for new users** — nothing loads `.env`; no `load_dotenv` in the
   package. `docker compose` reads it, the CLI does not.
3. **blocks the ablation arms** — `cadence run` takes a root, not a manifest,
   so one program cannot have four search configs without four directories.
4. **medium** — killed runs stay `running` forever; four rows from August
   still claim to be live. No heartbeat.
5. **medium** — a dead database prints a Rich traceback panel of cadence
   internals before the useful sentence.
6. **medium** — search methods are not pluggable; `registry.py` holds one
   hardcoded entry. Baseline arms must live outside cadence.
7. **low** — `check` accepts `--json` but not `--no-json`; `run` accepts both.

## What went well

`cadence check`'s output is the best thing in the product: the region and its
line numbers, the method and parameters, the resolved objective, whether the
baseline ran and what it scored, whether the score repeated, projected cost.
Eleven lines that answer "what is about to happen".

Which is exactly why #1 above matters.
