# Feature coverage

Which problem exercises which part of cadence. This is what makes the repo a
staging environment rather than a folder of examples: a problem earns its
place by covering a path nothing else covers.

Before adding a problem, find the row it fills. If every row is already
covered, the problem is a benchmark, not a staging case — say so in its
README and keep it anyway, but do not pretend it is testing anything.

| Area | Covered by | State |
|---|---|---|
| `prompt.template: region` | circle-packing | covered |
| `prompt.template: rewrite` | — | **gap** |
| `prompt.template: improve` (diff) | — | **gap** |
| `method: evolution` | circle-packing | covered |
| verdict cache on (`verifier.tolerance` set) | bin-packing | covered |
| verdict cache off (stochastic verifier) | circle-packing | covered |
| invalid answer scores 0, does not crash | circle-packing | covered |
| genuine crash → quarantine after `crash_limit` | bin-packing (a bad `priority` raises) | available |
| multi-metric manifest | bin-packing (train + valid) | covered |
| custom `objective` plugin | bin-packing (`weighted_sum` on valid only) | covered |
| `budget.usd` exhaustion | — | **gap** |
| `sandbox` timeout hit | — | **gap** |
| `sandbox` memory cap hit | — | **gap** |
| multi-seed variance (`sandbox.seeds`) | circle-packing | partial |
| `--resume` after a killed run | — | **gap** |
| `--config` manifest override | `arms/` | covered |
| error text on a malformed project | mistakes/ (9 cases) | covered |
| `cadence init` output passes `check` | tested in cadence | covered |
| scoring inside the editable region | mistakes/scorer-inside-markers | covered |
| concurrent runs, distinct ids | ad hoc, 2026-09-06 | covered |
| no `DATABASE_URL` (in-memory run) | — | **gap** |

A published baseline the repo can *run* is worth more than one it quotes.
circle-packing's 2.16667 grid is our own invention, so it checks nothing;
bin-packing's first fit and best fit are ten lines each and reproduce all
eight cells of the FunSearch table, which means the harness is verified before
a model call is spent. Prefer problems with that property.

Most rows are still gaps. That is the honest state and the reason this repo
exists.
