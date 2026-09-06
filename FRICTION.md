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
