# Games

Games and environments that cadence evolves players for, on one shared kit.

```text
games/              ← the folder cadence copies into every trial
  kit/              ← shared: the Env interface, the player wall, play
  scrabble/         ← one game
```

Run everything from this folder:

```bash
python -m pytest kit scrabble                      # tests
python -m scrabble.bench --games 200               # the benchmark ladder
cadence check . --config scrabble/.cadence         # a cadence project, free
cadence run . --config scrabble/.cadence
python -m scrabble.rehearse                        # cadence with known answers
```

## Adding a game

Write an `Env` (see `kit/env.py`): `reset(seed)`, `to_move`, `observe`,
`legal`, `step`, `done`, `returns`. What `observe` and `legal` return must be
plain JSON, because the player gets it in another process.

The player is always `choose(observation, legal) -> index`. It runs in its own
process (`kit.player.Remote`), so it cannot read the game's memory. A canary
test in `kit/test_kit.py` checks that.

Then a `score.py` that plays the candidate against something with
`kit.play.duplicate`, and a `.cadence` whose `program` and `run` are paths
from this folder.
