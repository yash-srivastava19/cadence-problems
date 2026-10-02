# Scrabble

A Scrabble engine, a ladder of fixed bots, a viewer to watch their games, and
a cadence project that evolves a player against the greedy bot.

```bash
cd examples/games                               # see ../README.md for the layout
python -m scrabble.bench --games 200            # 200 seeds per matchup, duplicate
open scrabble/out/viewer.html                   # watch the games (3 seeds per matchup)
open scrabble/viewer.html                       # or open any records.json from a picker
python -m pytest scrabble                       # the engine's checks
```

The first run downloads the ENABLE word list (pinned by sha256) into
`lexica/`. It is not committed.

| File | What it is |
|---|---|
| `RULES.md` | The rules the engine implements. Read this first |
| `english.json` | The English ruleset: tiles, board, word list, rule settings |
| `toy.json` | A tiny ruleset with a two-letter `QU` tile, used by the tests |
| `ruleset.py` | Loads a ruleset and builds the word trie. Knows no language |
| `board.py` | Move generation (Appel and Jacobson) and scoring |
| `game.py` | The bag, turns, exchanges, and the end of a game |
| `bots.py` | random, greedy (most points), leave (points + a simple leave value) |
| `env.py` | Scrabble as a kit `Env`: moves as plain JSON |
| `bench.py` | Plays the ladder and writes `out/records.json` and `out/viewer.html` |
| `viewer.html` | The viewer. Open it and pick a `records.json`, or let `bench.py` embed games in `out/viewer.html`. It draws what the engine recorded; it never scores |

## Evolve a player

```bash
cadence check . --config scrabble/.cadence   # free: the baseline must score 0.5
cadence run . --config scrabble/.cadence
python -m scrabble.rehearse                  # cadence with known answers, no LLM
```

`player.py` holds the region, `choose(view, moves) -> index`, starting as
greedy. It runs in its own process and gets JSON, through `kit.player.Remote`.
`score.py` plays 25 bags per seed, each twice with the seats swapped, against
the frozen greedy bot. Greedy against itself wins exactly 0.5. The leave bot's
0.656 is the bar to beat.

## What each player gets

`choose(view, moves) -> move`. `view` is the board, the player's rack, both
scores, the bag count, and the unseen tiles. `moves` is every legal move, in a
fixed order. This is the shape the evolved player will have.

## Measured (200 seeds per matchup, 2026-09-29)

| matchup | games | win rate of first | ±95% | avg spread |
|---|---|---|---|---|
| greedy vs random | 400 | 1.000 | 0.000 | +373.9 |
| leave vs greedy | 400 | 0.656 | 0.047 | +38.2 |
| leave vs random | 400 | 1.000 | 0.000 | +417.1 |

`out/records.json` keeps every game, turn by turn: rack, move, tiles,
scores, bag count, the top alternatives, and end-of-game adjustments.

1,200 games in 136 s on 12 cores: 8.8 games per second, 41 ms per move
generation. The ±95% treats games as independent; duplicate pairs share a
bag, so it is approximate.

## Not yet

- HastyBot (Macondo) as the yardstick and as a second check on move lists.
- Replaying recorded tournament games (GCG) to check every score.
- GCG export. Records are JSON for now: the seed plus every move.
