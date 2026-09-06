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

None. All nine assert a real message.

Three were fixed the day they were found — `scorer-inside-markers`,
`wrong-metric-name`, and a fourth that was never broken:

**`bad-yaml` was a bad entry, not a bad error.** The message does name the
file, on its first line. The original note was written from `tail -6` output
and was wrong. A wrong entry in this list costs a wasted investigation, so
check the whole message before adding one.
