# Friction log

Every snag, written down **before** it gets fixed. A snag that is fixed
silently is a data point thrown away, and this file is the entire output of
the ergonomics question.

Format: date, what happened, what it cost, how bad.

---

## 2026-09-06 -- the CLI does not read `.env`

Ran `cadence runs list` after a fresh setup. It died with "there is nothing
to read: DATABASE_URL is not set."

`DATABASE_URL` was in `.env` the whole time. `docker compose` reads that file
automatically; cadence does not -- there is no `load_dotenv` anywhere in the
package. To get anywhere you have to know `.env` exists, know cadence ignores
it, and run `set -a; source .env; set +a`.

**Severity: blocker for a new user.** Nothing in the error names `.env`.

**Fix shape:** a resolution order, highest wins -- `--database-url` flag, then
`DATABASE_URL`, then `.env` in the project, then `~/.config/cadence/config.toml`,
then nothing (local mode, no recording). The last rung is what makes "install
it and it works" true, and the same field holds a hosted DSN, so local and
shared are one mechanism.

---

## 2026-09-06 -- one manifest per directory, but arms need several

`load()` in `control/manifest.py:181` accepts a file path, but `cadence run`
takes a *root* and uses it as both the manifest location and the project
root. So there is no way to say "same program, different manifest."

The ablation arms (single-shot / random / hill-climb / cadence) are the same
program under different search settings. Today that means duplicating the
directory per arm and keeping four copies of `pack.py` in sync -- which is
how a benchmark quietly stops comparing like with like.

**Severity: blocks the experiment that matters most.**

**Fix shape:** `cadence run <root> --config <file>`, or a manifest that can
name variants. Cheap; the loader already supports it.

---

## 2026-09-06 -- search methods are not pluggable

`control/registry.py` resolves `method` from a dict holding exactly one
entry, `evolution`. There are no entry points. A baseline arm cannot be added
from outside cadence.

**Severity: medium.** Worked around by writing the control arms as plain
scripts in `baselines/`, which is arguably a better control anyway -- an
independent implementation, not cadence grading its own homework.

---

## 2026-09-06 -- a dead database prints a traceback panel, not a sentence

Ran `cadence runs list` while the Postgres container happened to be down.
Output was a Rich traceback panel showing cadence's own source lines, and
only then the useful part:

    StorageError: connection failed: connection to server at "127.0.0.1",
    port 5433 failed: Connection refused

`translating()` worked -- it is a StorageError, not a raw psycopg traceback.
But nothing catches it at the command, so Typer's pretty-exception handler
renders the panel. `run` catches `CadenceError` and calls `die()`
(`commands/run.py:124`); the read commands do not.

**Severity: medium, and embarrassing.** A typo'd DSN shows a user the
internals of a tool they just installed.

**Fix shape:** `pretty_exceptions_enable=False` on the Typer app, and the
same `except CadenceError: die(...)` the run path already has. The message
should also name the likely cause -- "is the database running?" -- since a
refused connection almost always means the container is down.

---

## 2026-09-06 -- a killed run stays "running" forever

`cadence runs list` shows four runs as `running` that were started on 29 and
30 August. Their processes are long gone.

Nothing marks a run dead. `RunFinished` is published by the loop, so a run
whose process is killed -- Ctrl-C, OOM, a laptop closing -- never writes a
terminal status and the row says `running` indefinitely.

**Severity: medium, and it corrupts the experiment.** The one command for
"what is happening" reports things that are not happening. Any later analysis
that filters on `status = 'running'` is wrong.

**Fix shape:** a heartbeat column the loop touches, and `runs list` showing
anything stale as `stalled` rather than `running`. `runs.reason` already
exists to hold why.

Related: this is the same gap as `--resume`. A run that can be resumed is by
definition one that stopped without saying so.

---

## 2026-09-06 -- `cadence check` says "ready" for a project that cannot run

`cadence check examples/lab` prints, in the same block:

    model       scripted, which has no answers in it.
                `cadence run` needs a provider named in .cadence
    ...
    ready. `cadence run` will spend up to 2 trials.

Exit code 0. Then `cadence run examples/lab` fails on the first model call
with `TerminalModelError: the scripted backend ran out of responses`, 0
trials, exit 1.

Check knew. It printed the sentence. It still said ready.

The cause is in `control/preflight.py:141`: the scripted-model `Finding` is
built without `ok=False`, so it lands among the notes rather than the
refusals, and `_refuse_a_project_check_would_refuse` in `commands/run.py`
never sees it.

**Severity: high.** `run.py` documents the intent explicitly -- "the same
checks, from both doors" -- and this is a door that opens onto a wall. The
whole value of a free preflight is that passing it means the expensive thing
will start.

**Fix shape:** `ok=False` on that finding. One keyword.

Separately, this means `examples/lab` is not a CLI project at all.
`demo.py` builds `Scripted(...)` in Python with a hardcoded response and
hands it to `build()`; there is no manifest key that supplies canned answers.
The example's README should say it is run with `python demo.py`, not
`cadence run`.

---

## 2026-09-06 -- `--json` and `--no-json` are not the same flag everywhere

`cadence check examples/lab --no-json` fails with "No such option: --no-json
(Possible options: --json)". `run` and `runs list` both accept the pair.

**Severity: low.** But it is the kind of thing that makes a CLI feel
untrustworthy -- you stop believing a flag works until you have tried it.

**Fix shape:** the same `--json/--no-json` pair on every command, and the
same non-TTY default `wanted_json()` already implements.

---

## What went well, for balance

The friction log would be dishonest if it only recorded failures.

`cadence check` output is the best thing in the product. Eleven lines that
name the region and its line numbers, the method and its parameters, the
resolved objective, whether the baseline actually ran and what it scored,
whether the score repeated, and an estimate of what the run will cost. It
answers "what is about to happen" better than anything else in the CLI.

Which is exactly why the "ready" bug above matters so much.
