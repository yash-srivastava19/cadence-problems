# Rules

The rules the engine implements. When the engine and this page disagree,
the engine is wrong. Everything language-specific lives in the config
(`english.json`); nothing here names a letter.

## The pieces

- **Board**: a square grid (15×15 in English) with premium squares:
  double letter, triple letter, double word, triple word. The centre square
  is a double word and is where the first move must go.
- **Tiles**: each tile is a *token* from the config, with a count and a
  point value. A token is usually one letter but need not be (Spanish `CH`).
- **Blanks**: worth 0 points. The player names the token when placing one,
  and it stays that token for the rest of the game.
- **Rack**: 7 tiles. Refilled from the bag after every play.
- **Bag**: every tile not on a rack or the board.

## A game

1. `reset(seed)` shuffles the whole bag once. Player 0 draws 7, then
   player 1 draws 7. Player 0 moves first.
2. Players alternate. On a turn a player does exactly one of: **play**,
   **exchange**, **pass**.
3. The game ends when a player goes out, or after six scoreless turns in a
   row.

## Play

A play places one or more tiles from the rack onto empty squares.

- All placed tiles are in **one row or one column**.
- Together with tiles already there, they form **one unbroken line**: no
  empty square between the first and last tile of the main word.
- The first play covers the **centre square** and places at least two tiles.
  Every later play touches at least one tile already on the board.
- Every word formed is in the word list: the **main word** along the line,
  and every **cross word** a placed tile makes in the other direction.
  A word is two or more tiles.
- There are no challenges. A play that forms an invalid word cannot be made.

## Scoring a play

For each word formed (main word and each cross word):

1. Add the value of every tile in the word. A blank is 0.
2. A letter premium under a **newly placed** tile multiplies that tile's
   value. Premiums under tiles already on the board count for nothing.
3. Multiply the sum by every word premium under a **newly placed** tile in
   that word. Two double-word squares make ×4.

The play scores the sum over all words formed. Placing all 7 tiles adds the
**bingo bonus** (50).

## Exchange

Allowed only when the bag holds at least 7 tiles. The player puts 1 to 7
tiles back, draws the same number, then the bag is reshuffled. The reshuffle
uses the game's own random stream, so the same seed and the same moves give
the same game. Scores 0.

## Pass

Always allowed. Scores 0.

## The end

- **Going out**: a player plays their last tile while the bag is empty. The
  game ends. That player adds **twice** the value of the opponent's rack.
  The opponent loses nothing. (North American rule.)
- **Six scoreless turns**: six turns in a row, counting both players, score
  0 (passes, exchanges, and plays worth 0). The game ends and each player
  subtracts the value of their own rack.

The higher final score wins. Equal scores are a tie.

## What each player sees

- The board, both scores, whose turn it is, how many tiles are in the bag.
- Their own rack.
- The **unseen tiles**: the full tile set minus the board and their own rack.
  This is the opponent's rack and the bag together, not told apart.
- Never the bag's order or the opponent's rack.
