# Job shop scheduling

Each job is a fixed sequence of operations, each needing a named machine for a
known time. An operation waits for the one before it in its job and for its
machine to be free. Minimise the makespan, the moment the last job finishes.

When a machine comes free and several operations could start, something has to
choose. In real plants that something is almost always a one-line priority
rule, because anything cleverer does not survive the shop floor. The rule is
what this problem evolves.

Source: instances from [OR-Library](https://people.brunel.ac.uk/~mastjjb/jeb/info.html),
contributed by Dirk Mattfeld and Rob Vaessens. `ft` from Fisher and Thompson
(1963), `la` from Lawrence (1984), `orb` from Applegate and Cook (1991), `abz`
from Adams, Balas and Zawack (1988).

## Why this problem is here

**The reference is computed, not quoted.** `optimum.py` solves each instance
with OR-Tools CP-SAT and writes the answer down. 29 of the 33 held-out
instances have a *proven* optimum; the other four stopped at a bound and are
labelled `bound`, because "3% above optimal" and "3% above the best bound in
60s" are different claims. Circle packing's baseline was ours and could check
nothing. Bin packing's L2 is published but is a bound, so 0% is unreachable
and the true gap is never known. Here 0% means optimal.

It also validates itself. CP-SAT returns 55, 930 and 1165 for ft06, ft10 and
ft20 -- the three most-quoted optima in the literature, to the digit. Parser,
instance data and model are all confirmed before a model call is spent.

**The solver never enters the sandbox.** `optimum.py` runs once, separately,
and needs `ortools`. `score.py`, `shop.py` and the candidate are standard
library only, so the sandbox needs nothing installed and a candidate cannot
import a solver to cheat with.

## The textbook rules, measured

Excess over the optimal makespan, pooled (total makespan over total optimum).
Lower is better. `python evaluate.py`, no key and no database required.

| rule | pooled | mean | `la` (seen shape) | other families |
|---|---|---|---|---|
| SPT   shortest processing time | 21.49% | 23.21% | 19.94% | 23.36% |
| LPT   longest processing time  | 34.41% | 34.51% | 32.91% | 36.24% |
| FIFO, as scored here ¹         | 29.98% | 30.08% | 29.75% | 30.27% |
| **MWKR  most work remaining**  | **17.29%** | 17.74% | **12.95%** | 22.56% |
| LWKR  least work remaining     | 34.99% | 36.10% | 34.83% | 35.20% |
| MOPNR most operations remaining| 19.67% | 20.13% | 14.37% | 26.11% |

MWKR is the seed, and is the best simple rule here, which is what the
dispatching-rule literature reports.

¹ **This is not FIFO.** Every operation in a contest has the same `ready_at`
(verified over 6,836 contests and 13,464 operations), so a rule that scores
`-ready_at` scores them all equally and falls through to the tie-break: lowest
job index first. It is a fixed job-order rule. True FIFO needs `ready_at` to
be the moment the operation became eligible -- its predecessor finishing --
rather than the contest time. Measured that way, in a scratch copy that
changes nothing else, FIFO scores **23.65%** pooled (19.30% `la`, 28.93%
other), and MWKR and SPT come out byte-identical, which confirms only rules
reading `ready_at` are affected. `shop.py` is left as it is while run
`20260917-032417-42409b` can still be resumed; the fix belongs to the next
lineage.

Both columns are printed because they disagree and the literature usually
quotes the mean. Pooled is the one that does not let a six-machine toy outvote
a thirty-job shop -- the same correction that mattered on bin packing, where
averaging gave 6.4111 and the paper said 6.42.

## Result

Run `20260917-032417-42409b`, gemini-3.6-flash, 16 trials across two days,
stopped by the daily quota and resumable. Best at trial 11.

| | pooled | mean | `la` (seen shape) | other families |
|---|---|---|---|---|
| MWKR, the seed | 17.29% | 17.74% | 12.95% | 22.56% |
| **cadence** | **12.20%** | **13.02%** | **8.38%** | **16.84%** |

Pooled excess over the proven optimum falls by 5.09 points, closing 29% of
MWKR's gap. It improves on the families it never saw (-5.72) by as much as on
the shape it was tuned on (-4.57) -- the opposite of bin-packing's second
lineage, which gained on validation and lost held out.

Verified out of band: `winners/20260917-032417-42409b.py`, copied into a
directory it never ran in, rescores `excess_train 9.107723`,
`excess_valid 10.690138`, matching the recorded verdict to six decimals.

The rule is a weighted sum of ten terms with hand-set constants -- the
parameter-tuning kind of edit that dominates evolutionary runs and that could
plausibly be derived by hand. What argues against pure tuning is the
unseen-family column. It adds what `IMPROVE.md` says MWKR lacks, a penalty
for blocking a contested machine (`-0.4 * duration * (n - 1)`,
`-0.0012 * duration * other_work`), so the problem statement pointed at the
mechanism, as it did on bin packing.

One of its ten terms is dead. `+ 0.8 * wait` reads `now - ready_at`, which is
always zero under this simulator, so the rule in effect has nine. It used that
term because `IMPROVE.md` said "`now - ready_at` is how long an operation has
already waited", which is false here. On bin packing the problem statement
handed over a real constraint; here it handed over a phantom one, and the
model took it. That line is fixed in the next lineage, not this one, because
editing `IMPROVE.md` changes the prompt digest and would refuse the resume.

## The split, and the trap it is built to catch

`la01`-`la40` is eight groups of five by shape, from 10x5 up to 30x10 and
15x15. Two of each group train, one validates, two are held out, so all three
sets span the same shapes. `ft`, `orb` and `abz` are held out entirely and are
a different distribution.

That is deliberate. On 2026-09-16 a bin-packing run improved its validation
score by 5.8% and got 11% and 16% *worse* on the two largest held-out sets,
because validation was one instance size and the held-out sets were not. The
`la` and `other` columns above make that visible here: MWKR gains 9.6 points
moving from other families to the shape it was tuned on, MOPNR gains 11.7, and
FIFO gains half a point. A rule that improves the first column and loses the
second has been tuned, not improved.

Seed on the training instances: `excess_train 11.41`, `excess_valid 13.74`.

## Running it

```sh
python evaluate.py                      # the textbook rules, no key needed
python evaluate.py winners/<run>.py     # those, and an evolved rule

cadence check run
cadence run   run
```

To recompute the optima from scratch:

```sh
pip install ortools
python optimum.py heldout/orlib.txt heldout/optima.txt 60
```
