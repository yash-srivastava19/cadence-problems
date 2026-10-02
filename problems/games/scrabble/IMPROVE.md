# What to improve

`choose(view, moves)` plays Scrabble. Every turn it is handed every legal
move and must return the index of one of them. Right now it is greedy: it takes whatever
scores the most points this turn.

The score is its win rate against that same greedy player, over games played
in pairs with the same bag and the seats swapped. Greedy against itself wins
exactly half. A simple "points plus the value of the tiles you keep" player
wins about 66%.

The "What to try" line in each request is generic and rotates. If it says
to keep behaviour the same, ignore that part here: the goal is to play
better, and a player that makes the same choices as greedy scores 0.5.

## What you get

- `view["rack"]`: your tiles, `"?"` is a blank.
- `view["scores"]`: `[player 0, player 1]`; `view["me"]` is your index.
- `view["bag"]`: tiles left in the bag.
- `view["unseen"]`: counts of every tile you have not seen, which is the
  opponent's rack and the bag together.
- `view["grid"]`: the 15×15 board, each square `None` or `(letter, is_blank)`.
- `moves`: a list of dicts with `kind` (`"play"`, `"exchange"`, `"pass"`),
  `label`, `score` (points this turn), `word`, `where`, `tiles`
  (`[row, col, letter, is_blank]`), `returned` (for exchanges) and `leave`
  (the tiles you keep after the move).

Your code runs in its own process and is sent these as JSON each turn.

## What you may change

Only the code between the markers. Keep `choose(view, moves) -> int`, and
return an index into `moves`: anything else forfeits the game. You may add
helper functions and constants inside the markers.

## What you may not do

Import anything outside the standard library, read files, or look at the bag
or the opponent's rack. Be deterministic: the same view and moves must give
the same answer. Stay fast: there are hundreds of moves on a turn and many
games per score.

## Worth knowing

Points now are not everything. The tiles you keep decide your next turns:
blanks and S are valuable, Q without U, duplicates and too many vowels or
consonants are not. Opening a triple-word square for the opponent costs you.
Late in the game, with the bag nearly empty, only points and going out
matter. The word list is ENABLE, which has no QI or ZA.
