# What to improve

`choose(view, moves)` plays Scrabble. Every turn it is handed every legal
move and must return the index of one of them. It starts as the current
champion: the best player found so far.

This is self-play. The score is the win rate against a pool of frozen
players: greedy (most points now) and every earlier champion. Each bag is
played twice with the seats swapped, so luck is shared. A copy of the
champion scores exactly 0.5 against itself, so beating the pool means
beating the champion, not just greedy. A winner is then checked on bags no
run has seen before it joins the pool.

The "What to try" line in each request is generic and rotates. If it says
to keep behaviour the same, ignore that part here: the goal is to play
better. A player that makes the same choices as the champion changes nothing.

## What you get

- `view["cgp"]`: the position as you see it, in CGP (the FEN of Scrabble):
  board rows, your rack, both scores, scoreless turns, the turn number, how
  many tiles the opponent holds and how many are in the bag.
- The same facts as fields: `view["rack"]` (`"?"` is a blank),
  `view["scores"]` (`[player 0, player 1]`), `view["me"]` (your index),
  `view["bag"]` (tiles in the bag), `view["unseen"]` (counts of every tile you
  have not seen: the opponent's rack and the bag together), `view["grid"]`
  (15×15, each square `None` or `[letter, is_blank]`).
- `moves`: every legal move, as dicts with `kind` (`"play"`, `"exchange"`,
  `"pass"`), `label`, `score` (points this turn), `word`, `where`, `tiles`
  (`[row, col, letter, is_blank]`), `returned` (for exchanges) and `leave`
  (the tiles you keep after the move).

Your code runs in its own process and is sent these as JSON each turn.
Every move and the view are dicts that can also be read with dots:
`move["score"]` and `move.score` are the same thing.

## Tools: you may look ahead

`scrabble.tools` holds the rules, and nothing hidden:

```python
from scrabble import tools

world = tools.sample_world(view["cgp"], rng)  # a full state that fits what you know
moves2 = tools.legal(world)                   # the same moves as `moves`, same order, same form
after = tools.play(world, moves2[i])          # the state after a move; world unchanged
after = tools.play(world, i)                  # an index works too
tools.legal(after)                            # the opponent's replies there
tools.spread(after, view["me"])               # your points minus theirs
tools.over(after)                             # has the game ended
tools.unseen(view["cgp"])                     # the tiles you cannot see
```

`sample_world` shuffles the tiles you cannot see into a possible opponent rack
and bag. Each call is one possible world; different worlds can disagree. Once
the bag is empty nothing is hidden: the unseen tiles are exactly the
opponent's rack, and every sampled world is the real one.

A move list takes about 40 ms to generate, more with blanks on the rack.

## Time

Aim for about 2 seconds a move (`tools.BUDGET_SECONDS`). Past 10 seconds a
move forfeits the game. Average time per move is reported as `ms_per_move`.

Do a fixed amount of work, not "until the clock runs out": a player that
stops on the clock plays differently when the machine is busy, and then the
same player scores differently twice. Seed any randomness from the view, for
example `random.Random(view["cgp"])`, so the same position gets the same answer.

## What you may change

Only the code between the markers. Keep `choose(view, moves) -> int`, and
return an index into `moves`: anything else forfeits the game. You may add
helper functions and constants inside the markers.

## What you may not do

Import anything except the standard library and `scrabble.tools`, read files,
or look at the bag or the opponent's rack any other way.

## Worth knowing

Points now are not everything. The tiles you keep decide your next turns:
blanks and S are valuable, Q without U, duplicates and too many vowels or
consonants are not. Opening a triple-word square for the opponent costs you.
Late in the game, with the bag nearly empty, only points and going out
matter. The word list is ENABLE, which has no QI or ZA.
