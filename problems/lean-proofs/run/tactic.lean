/-
The tactic that every theorem is proved by.

score.py splices whatever is between the markers into each statement in
train.lean, directly after `:= by`, and counts how many theorems close. One
tactic, twenty-five theorems -- so it has to generalise, not memorise.

The theorem statements, how they are compiled and how closing is counted live
in train.lean and score.py and stay put.

The seed is the tactic list from the miniF2F paper's `tidy` baseline
(nlinarith, linarith, ring_nf, norm_num). Each alternative ends in `done` on
purpose: `first` commits to the first tactic that does not fail, and several
of these make progress without closing the goal, so without `done` the
combinator settles for a tactic that leaves the goal open.
-/

-- CADENCE:BEGIN
first
  | (norm_num; done)
  | (ring_nf; done)
  | (linarith; done)
  | (nlinarith; done)
-- CADENCE:END
