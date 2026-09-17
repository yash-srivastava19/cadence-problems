# 2026-09-16 — thirty calls, three days, 0.155% short

Run `20260907-025816-571b77`, experiment `circle-packing-26`, resumed twice
today with `arms/circle-packing-resume.cadence`. cadence at `1504bae`
(`feat/a-dashboard-for-what-was-recorded`, working tree dirty). Local Postgres
on 5433.

## The result

    2.166667  grid seed
    2.631790  trial 24        +21.47%
    2.634     Friedman 2012, by hand          0.084% above us
    2.635863  AlphaEvolve                     0.155% above us
    2.635983  ShinkaEvolve, 150 samples       0.159% above us

Thirty model calls, spread over 2026-09-07 (5), 09-11 (14) and 09-16 (11).
One run id throughout. No day could have held it: the free tier allows twenty
requests and retries eat roughly another 40% that cadence does not count.

Verified out of band. `cadence apply` into a directory the program had never
run in, then `score.py` at each seed:

    CADENCE_SEED=0  2.629627
    CADENCE_SEED=1  2.630866
    CADENCE_SEED=2  2.634877   <- above Friedman's 2.634 on this seed alone

Mean 2.631790, matching the recorded verdict to six decimals, overlap and
containment checks passing on all three.

Winner saved to `problems/circle-packing/winners/20260907-025816-571b77.py`.

## What actually produced it

The sandbox cap, again. At pickup the arm allowed 120s per seed and four
trials — 9, 11, 13, 15 — had been killed by it, each *after* its model call
was bought. Raised to 300s.

    trial 24   2.631790   153s/seed   <- the winner
    trial 25   2.629759   144s/seed
    trial 26   2.629551   120s/seed
    trial 29   2.629059   248s/seed

Three of those four would have been killed under the old cap and the run would
have finished around 2.6265. This is the same failure that suppressed the first
two runs of this experiment at 30s, which was written up on 2026-09-07 as a
lesson — and then left in the arm file at 120s for the next nine days.

I also got this wrong in the middle of the session: after six trials under the
new cap scored well at 6–16s/seed, I concluded the compute-time correlation had
not survived and that the only defensible claim was about eliminating waste.
Twelve trials later the winner arrived at 153s/seed. Six trials is not enough to
overturn a hypothesis.

## What it built

A change of formulation, not of constants. Given fixed centres, the optimal
radii are a linear program, so it solves that exactly with primal simplex and
uses the LP's dual shadow prices as the gradient for moving the centres, with
Adam, bottleneck-targeted basin-hopping and a pattern search on top. Earlier
winners were multi-start Adam over positions and radii together.

## Friction

**`resume` does not update `runs.manifest_hash`.** The row still records
`c629976db40d6764` (`circle-packing-full`: 120s, 6 trials) while trials 18–29
ran under `dfeddf85427282f3` (`circle-packing-resume`: 300s, 30 trials). The
database's account of the experiment is now false, and `cadence apply`
consequently refuses the manifest the winner was scored under and accepts the
one it was not. For a system whose claim is that the database is the record,
this is the most serious thing found today.

**A killed run still reports `status=running`.** Seen on 2026-09-06, still
open. Does not block resume.

**`spend` reported `calls: 6, replayed: 1`.** First observed firing of the
replay path in a real run — a `COVERAGE.md` row that was previously
theoretical.

## Still open

- No control arm. `baselines/` is still empty, so "the search did this" and
  "thirty samples did this" remain indistinguishable.
- One lineage, resumed five times. A second lineage from the same seed has
  never been run, so nothing here speaks to variance.
- Bin packing next: `arms/bin-packing-resume.cadence` is written and checked
  (15 keys, only `budget.trials` 10 → 24, `verifier.tolerance` preserved) and
  has not been launched. Fourteen trials is close to a full day's quota.
