# Strategies to beat BestBot

A menu, not a plan. Pick a few, write their predictions into PREREG.md before
anything runs, then send them through the funnel below.

Drafted 2026-10-23, after B1: our best player (klve+peg+sim) is level with a
2-move-deep copy of BestBot (0.505 over 1000 games). The real BestBot looks 5+
moves ahead, uses all cores for up to 3 minutes, guesses tiles and solves
1-in-bag positions exactly
(https://blog.woogles.io/posts/2025-05-04-the-mathematics-and-algorithms-behind-bestbot/).

## Where an edge can come from

Search and endgames are close to solved on both sides; equal compute only
ties. What is left is knowledge: what the opponent probably holds, and how
good a position really is. The one number we have: seeing the opponent's real
rack is worth +0.117 win rate (C1).

## The funnel

| Stage | What | Who gets in | Sees differences of about |
|---|---|---|---|
| 0. Positions | pick moves on ~500 logged positions, judged by a very long search | every strategy | 1 win-% a move |
| 1. Cheap games | 200 seeded, paired games vs a fast opponent | top 5 | 5 points |
| 2. Full-strength games | 500 games vs the full BestBot copy, same compute | top 1-2 | 3 points |
| 3. Confirm | 1000 games on fresh bags, run once | the winner | the honest number |

Before stage 1: seed the opponent's randomness (it flips 118 of 300 paired
games today), and build the full-strength copy (M1, M2 below).

## Measurement (needed first, not strategies)

- **M1. Full-strength BestBot copy.** Macondo with 5+ plies, the statistical
  cut-off, inference, peg at bag 1, exact endgame, a fixed clock per move.
  Time it and measure memory at full parallelism before any run.
- **M2. Seeded opponent.** The opponent's random choices come from a seed
  tied to the bag, so a paired game differs only by our moves.
- **M3. Position benchmark.** ~500 positions from logged games, spread over
  the game's stages, each with a long-search verdict saved once and reused.

## Strategies

Each has: the idea in one line, why it might work, how stage 0 tests it, and a
first guess at the gain against the full-strength copy. The guesses are
guesses; writing them down is how we learn whether our intuition is any good.

### Guessing the opponent's tiles

| # | Idea | Why it might work | Stage 0 test | Guess |
|---|---|---|---|---|
| T1 | Weight the opponent's possible racks by how likely their last move was from each (play-again-and-compare), and sim against those racks | C1 says perfect knowledge is worth +0.117; a third of it would be a clear edge | rack-guess accuracy on logged games where the real rack is known, then move quality | +0.02 to +0.04 |
| T2 | T1 over the last two moves, carrying kept tiles forward | kept tiles stay on the rack, so two moves say more than one | same as T1, compared with it | +0.005 over T1 |
| T3 | Read exchanges: what they threw back says what they kept | exchanges are rare (30 of 2068 moves in D1) but very telling | accuracy on exchange turns only | under +0.005 |
| T4 | Guess the chance they hold a 7-tile play next turn, and block or open lines by it | bingos swing ~50 points; blocking when likely is cheap | move quality on positions with an open bingo line | +0.005 to +0.01 |

### Scoring a position

| # | Idea | Why it might work | Stage 0 test | Guess |
|---|---|---|---|---|
| V1 | Retrain the tile-value table on many more self-play games from the sim player | better players' games give better values (TD-Gammon) | move quality with the new table, sim off | +0.005 |
| V2 | Add board features to the static score: open triple lanes, hooks, vowel balance of the unseen pool | BestBot's static score ignores the board; our D1 losses were in ordinary plays | move quality, sim off | +0.01 |
| V3 | Small neural network as the static score (Del Solar-style CNN) | it beat tile tables 51.7% over ~250K games | move quality, sim off | +0.01 |
| V4 | Network scores the board at the end of each sim, so sims can be shorter and more accurate | AlphaZero's lesson: a learned value beats long random play-outs | move quality at a fixed clock | +0.02 to +0.03 |
| V5 | cadence evolves the static-score features, judged on M3 | our own loop as the search; M3 makes each trial cheap | the evolved score's move quality vs V2 | unknown; this is the cadence bet |

### Which moves to check

| # | Idea | Why it might work | Stage 0 test | Guess |
|---|---|---|---|---|
| P1 | Always include the best exchange, the best defensive play and the best keep-good-tiles play among the candidates | top-15-by-score can miss whole kinds of moves | how often the judge's best move is among the candidates | +0.005 |
| P2 | More candidates when the top scores are close, fewer when one move dominates | spends time where the choice is hard | move quality at a fixed clock | +0.005 |
| P3 | Statistical cut-off (Welch's t-test) to drop hopeless moves early | BestBot does it; frees time for contenders | move quality at a fixed clock | +0.005 (catching up, not passing) |

### Time and endgame

| # | Idea | Why it might work | Stage 0 test | Guess |
|---|---|---|---|---|
| E1 | Exact solver at bag 2 as well as bag 1 | I2: solver 9 better, 0 worse than klve; beat the sim there | already passed offline; goes straight to stage 1 | +0.005 |
| E2 | Spend more of the clock in the middle game (bag 8-49), less on obvious moves | D1's biggest total loss was there | move quality per second spent | +0.005 |

### Playing the score

| # | Idea | Why it might work | Stage 0 test | Guess |
|---|---|---|---|---|
| W1 | Risk by score: take swingy plays when behind, safe ones when ahead | win chance, not points, is what counts; humans do this | move quality split by lead | +0.005 |
| W2 | Second-seat play: different openings or risk when going second | the seat gap is 15 points and has never moved | move quality, seat 1 only | under +0.005 |

### Learning from self-play

| # | Idea | Why it might work | Stage 0 test | Guess |
|---|---|---|---|---|
| L1 | The best player plays itself; retrain V1/V3 on those games; repeat | AlphaZero loop; each round's data comes from better play | move quality per round, stop when flat | +0.01 to +0.03 over rounds |
| L2 | Rollouts use a better reply policy (the opponent plays like V3, not like the tile table) | sims are only as good as the moves imagined in them | move quality at a fixed clock | +0.005 |

### Checks on the funnel itself (always run)

| # | Idea | Expected |
|---|---|---|
| K1 | A change that should do nothing (candidates shuffled, same set) | 0; if it "wins", the funnel is fooling us |
| K2 | A change that should hurt (top 5 candidates instead of 15) | clearly negative; if not seen, the funnel is too blunt |

## Already tested (don't redo)

- Deeper instead of wider at the same clock (H3): +0.003, 30% slower.
- Static win-chance tweak: no-op.
- Exact solver at bag 1 (H1/I1): right but small, about +0.005.
- 2-ply sim in the middle game (H2): the +0.11 that took us to level.

## Notes for whoever picks this up

- Guesses add up to more than they will; overlapping ideas share the same gain.
- T1 and V4 are the two big bets. Everything else is a few tenths of a point.
- Every stage-0 test needs M3 first; every game stage needs M1 and M2.
