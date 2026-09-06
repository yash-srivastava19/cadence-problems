# Mistakes

Nine ways to get cadence wrong, and what it says about each. A user's first
hour is mostly errors, so the error text *is* the product. This turns that
into something CI can fail on.

```sh
CADENCE=../cadence/cadence/.venv/bin/cadence python3 mistakes/run.py
```

Each directory is one mistake plus an `expect` file: the lines that must
appear in `cadence check`'s output. `known-bad:` lines describe an error we
are not happy with — reported, not failed, so the list stays visible without
blocking.

## Good today

| Mistake | What cadence says |
|---|---|
| no `.cadence` | "that file is where a cadence project starts" |
| no `CADENCE:BEGIN` marker | names the file, says the reply would replace all of it, gives the fix |
| program prints no metric | names the metric and shows both accepted formats |
| manifest names a missing program | names the file and the directory |
| program crashes | the traceback, plus why a broken scorer stops a run |
| scorer is nondeterministic | both scores, and what the noise does to the search |

## Known bad

**`scorer-inside-markers`** — not detected at all. The line that prints the
score sits inside the editable region, so the model can rewrite what it is
judged by, and check calls the project fine. This is the one rule every
problem in `problems/` follows, and cadence cannot check it.

**`bad-yaml`** — a raw PyYAML error: `in "<unicode string>", line 4`. It
never names `.cadence`, so the user cannot tell which file is malformed.
`load()` already has the path in hand.

**`wrong-metric-name`** — the program printed `score`, the manifest asked for
`value`, and the error only says `value` was never reported. Naming both
would end the guessing.

## Adding one

A directory, a broken project, an `expect` file. No registration.
