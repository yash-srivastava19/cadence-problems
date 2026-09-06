# Control arms

Plain scripts, not cadence plugins. Two reasons: cadence's `method` registry
is not pluggable from outside, and a control that shares no code with the
thing it controls is a better control.

Each arm takes a problem directory, spends the same budget, and prints the
best score it found. Same program, same verifier, same trial count.

- `single_shot.py` -- one model call, keep it. The floor.
- `random_search.py` -- N independent calls from the same seed program, keep
  the best. **This is the one that matters:** if cadence cannot beat it,
  the evolution loop is decoration.
- `hill_climb.py` -- always mutate the current best. Greedy, no population.

None are written yet.
