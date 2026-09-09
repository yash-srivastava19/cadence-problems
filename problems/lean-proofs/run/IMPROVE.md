# One tactic, twenty-five theorems

Every theorem in the set is proved by the same tactic. Your job is to write a
tactic that closes as many of them as possible.

The theorems are high-school competition algebra from miniF2F: equalities and
inequalities over ℝ and ℕ, usually with a few hypotheses naming values.

## Rules

- Whatever you write is spliced in directly after `:= by`, once per theorem.
  It cannot be specialised to any single one, and it cannot name a theorem.
- A theorem counts only if it closes with no error and no `sorry`. Leaving a
  goal open scores the same as failing.
- Mathlib is fully available. `import Mathlib` and
  `open BigOperators Real Nat Topology Rat` are already in scope.

## What works, and what to watch

The seed is the tactic list from the miniF2F paper's `tidy` baseline. Each
alternative ends in `done` deliberately: `first` commits to the first tactic
that does not *fail*, and several of these make progress without closing the
goal. Without `done`, the combinator settles for a tactic that leaves the goal
open, and the theorem scores as unproved.

Tactics worth knowing, roughly in order of how often they finish one of these
on their own: `nlinarith`, `linarith`, `norm_num`, `omega`, `decide`,
`positivity`, `simp_all`, `aesop`, `ring_nf`, `field_simp`, `polyrith`,
`bound`, `interval_cases`, `nlinarith [sq_nonneg _, sq_nonneg _]`.

Order matters: `first` tries alternatives left to right, so a cheap tactic
that often succeeds belongs early, and an expensive one belongs late.

Preprocessing before the alternatives often helps more than adding another
alternative — `intro`, `obtain`, `subst`, `norm_num at *`, `field_simp` can
turn a goal none of them close into one that several do.

## Constraints

- Standard Mathlib tactics only. No `sorry`, no `native_decide`, no axioms.
- The whole set is compiled once with a time limit, so a tactic that searches
  forever costs every theorem, not just the one it is stuck on. `maxHeartbeats`
  is set to 400000.
