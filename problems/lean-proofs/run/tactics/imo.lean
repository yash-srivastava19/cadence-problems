/-
The tactic every theorem in this tier is proved by. score.py splices what is
between the markers in after `:= by`, once per theorem, and counts how many
close. One tactic, many theorems -- it has to generalise, not memorise.

The seed is the tactic list from the miniF2F paper's `tidy` baseline. Each
alternative ends in `done` on purpose: `first` commits to the first tactic
that does not fail, and several of these make progress without closing the
goal, so without `done` the combinator settles for one that leaves it open.
-/

-- CADENCE:BEGIN
first
  | (norm_num; done)
  | (ring_nf; done)
  | (linarith; done)
  | (nlinarith; done)
-- CADENCE:END
