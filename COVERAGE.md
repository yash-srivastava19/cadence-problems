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
| verdict cache on (`verifier.tolerance` set) | — | **gap** |
| verdict cache off (stochastic verifier) | circle-packing | covered |
| invalid answer scores 0, does not crash | circle-packing | covered |
| genuine crash → quarantine after `crash_limit` | — | **gap** |
| multi-metric manifest | — | **gap** |
| custom `objective` plugin | — | **gap** |
| `budget.usd` exhaustion | — | **gap** |
| `sandbox` timeout hit | — | **gap** |
| `sandbox` memory cap hit | — | **gap** |
| multi-seed variance (`sandbox.seeds`) | circle-packing | partial |
| `--resume` after a killed run | — | **gap** |
| concurrent runs, distinct ids | ad hoc, 2026-09-06 | covered |
| no `DATABASE_URL` (in-memory run) | — | **gap** |

Most rows are gaps. That is the honest state and the reason this repo exists.
