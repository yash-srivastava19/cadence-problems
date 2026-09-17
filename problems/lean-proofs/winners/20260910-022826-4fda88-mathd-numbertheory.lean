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
intros
try subst_vars
try dsimp at *
try norm_cast at *
try zify at *
try norm_num at *
try field_simp at *
try norm_cast at *
try norm_num at *
try ring_nf at *
try subst_vars
try split_ifs
try split
all_goals
  first
    | (ring; done)
    | (omega; done)
    | (linarith; done)
    | (nlinarith; done)
    | (positivity; done)
    | (norm_num; done)
    | (ring_nf; done)
    | (decide; done)
    | (bound; done)
    | (field_simp; ring; done)
    | (field_simp; linarith; done)
    | (field_simp; nlinarith; done)
    | (field_simp; positivity; done)
    | (zify; linarith; done)
    | (zify; nlinarith; done)
    | (simp_all; ring; done)
    | (simp_all; linarith; done)
    | (simp_all; nlinarith; done)
    | (simp_all; omega; done)
    | (simp_all; positivity; done)
    | (simp_all; ring_nf; done)
    | (simp_all; done)
    | (aesop; done)
-- CADENCE:END
