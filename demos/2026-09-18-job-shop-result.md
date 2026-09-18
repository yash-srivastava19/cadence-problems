# 2026-09-18 — job shop: 17.29% to 12.20%, and it generalised

Run `20260917-032417-42409b`, experiment `job-shop-dispatch`, gemini-3.6-flash.
Resumed twice after the first-contact run on 2026-09-17: once by hand to trial
15, once more to trial 16. Every stop was the daily 429. Status `failed`,
resumable, four trials left in its budget.

## The result

Held out, 33 instances, 29 with a proven optimum. Excess over optimal makespan:

    |               | pooled |  mean  |  la (seen) | other (unseen) |
    | MWKR, seed    | 17.29% | 17.74% |   12.95%   |     22.56%     |
    | cadence       | 12.20% | 13.02% |    8.38%   |     16.84%     |

It gains 5.72 points on the families it never saw and 4.57 on the shape it
was tuned on. On 2026-09-16 a bin-packing lineage improved validation by 5.8%
and got 11% and 16% worse held out, and the `la` / `other` columns were built
so that failure would show up here if it happened. It did not.

Selection metric, for the record: `excess_valid` 13.7445 -> 10.6901, best at
trial 11.

## Verified

`winners/20260917-032417-42409b.py`, copied into a fresh directory, rescores
`excess_train 9.107723`, `excess_valid 10.690138` -- the recorded verdict to
six decimals.

## What it built

A weighted sum of ten terms: work remaining, the work after this operation,
that tail divided by duration, normalised progress through the job, and a
penalty for starting a long operation on a machine others are queueing for.
The last one is what `IMPROVE.md` says MWKR lacks.

That is the hyperparameter-tuning kind of edit, and a person could write it.
The unseen-family column is the evidence that it is not only tuning.

## Two things this run found that are wrong in the repo

**A dead term, and the guidance that caused it.** The rule includes
`+ 0.8 * wait` where `wait = now - o.ready_at`. Under this simulator that is
always zero: every operation in a contest shares `ready_at`, checked over
6,836 contests and 13,464 operations. The model used the term because
`IMPROVE.md` says "`now - ready_at` is how long an operation has already
waited". On bin packing the guidance handed over a real constraint; here it
handed over a false one.

**The FIFO baseline was not FIFO.** For the same reason, scoring `-ready_at`
gives every operation the same score, and the tie-break -- lowest job index --
decides everything. The published 29.98% measured a fixed job order. With
`ready_at` set to when the operation became eligible, true FIFO is 23.65%.
MWKR and SPT are unchanged under that patch, confirming nothing else moved.

Neither is fixed in place. Changing `shop.py` changes the scorer and changing
`IMPROVE.md` changes the prompt digest, and either would make the rest of
this lineage incomparable with its first sixteen trials. Both go in the next
lineage.

## The same numbers as everywhere else

Duplicates: trials 1, 4 and 16 all score 12.159 valid; 5 and 8 score 10.8067;
11 and 12 score 10.6901. Seven of seventeen, about 41% -- identical to
bin-packing run 2, on a problem with a different interface. Third measurement.

Retries: the 429 landed with 15 calls counted against a cap of 20.
