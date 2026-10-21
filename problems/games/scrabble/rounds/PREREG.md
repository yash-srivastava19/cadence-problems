# Expectations, written before each experiment runs

## 2026-10-04 · Round 2 gate re-check (no API)
Question: did Gemini's look-ahead player (run 20261003-033748-9bb3ee, best
trial, 0.535 vs champion_1 in training) really lose the gate at 0.340, or were
timeouts counted as losses?
Expect: most of its gate losses are forfeits by timeout (> 10 s/move under
12-way parallel load). With fewer games at once, its gate score rises to
roughly its training score (~0.5), and spread over finished games stays ~0.
Settles: whether our harness, not the player, produced 0.340.

## 2026-10-04 · Gemini budget: ~12 calls, two arms, same start, same hint
Start: the current champion after the gate re-check (champion_2 if round 2's
player is promoted, else champion_1). Pool: greedy + every champion.
One hint for every trial in both arms (prompt.hints, so trial 0 is not told
to keep behaviour the same):
  "play better than the current champion; the moves it chooses must change"

E1 · Search: one run, 5 trials, Evolution as usual. Children build on the
best so far.
E2 · Control: 5 runs of 1 trial each from the same start. No child ever sees
another's result: best-of-5 recall at the same number of model calls.

Question: does cadence's search add anything over asking the model five times?
Expect (honest prior): the two arms end within noise of each other (±~0.07 at
200 games), as on the cache and in round 1; E1 is more likely to produce a
look-ahead player because later trials see the earlier ones.
A difference counts only if the gate (400 fresh games) confirms it.

### Amended before E1/E2 ran (2026-10-04)
- The round 2 gate re-check was paused so the arms could run; both arms start
  from champion_1.
- Scoring plays 6 games at once (half the cores) instead of 12, the same for
  both arms, to keep timeouts from deciding results.

## 2026-10-04 · Gate for search vs recall (no API), written before it runs
Candidates: E1 best (trial 1), E1 trial 4 (fastest, no timeouts), E2 best
(run 5). Each plays champion_1 on the same 400 fresh games (seeds 520000+,
untouched by any run), 6 at once.
Expect: all three within ±0.05 of 0.5 against the champion; none reaches the
0.55 bar. E1 trial 4 has the fewest timeouts.

## Outcomes (2026-10-04)
- E1 (search, 4 scored trials): best 0.650 overall; vs champion 0.53, 0.565,
  0.545, 0.565; timeouts fell 2 → 0.5 → 0 → 0; ms/move 989 → 457.
- E2 (recall, 5 runs): best 0.650 overall; vs champion 0.49, 0.46*, 0.51,
  0.53, 0.59 (*kept its baseline); timeouts 5, 5, 3.5, 7, 0.5.
- Gate, same 400 fresh games vs champion_1: E1 best 0.507 (10 timeouts),
  E1 trial 4 0.505 (0 timeouts, 693 ms), E2 best 0.495 (13 timeouts).
Matches the prior: within ±0.05 of 0.5, none reaches 0.55. Search and recall
tie on strength; search gave the only player with no timeouts. Training gains
of +3 to +9 points were selection on noise. Not promoted; champion_1 stands.

## 2026-10-04 · Step 1: what the tiles you keep are worth (no API)
Data: greedy vs greedy self-play (greedy picks on points alone, so what it
keeps is close to random with respect to leave quality). Every turn with the
bag at 7+ tiles: the leave, and that player's points on their next turn
(bingo bonus included). Fit: next-turn points ~ count of each tile kept, plus
duplicates and Q without U.
Expect: blank and S clearly positive (blank largest); Q clearly negative,
less so with U; duplicates negative; the rest within a few points of zero.
Champion_1's hand-written values will get the order mostly right and the
sizes wrong somewhere, which is what this is for.

### Outcome (2026-10-04)
95,858 turns from 5,000 games (seeds 800000+). Matches: blank +15.0 and S
+3.2 the largest; duplicates −4.6 each; Q without U −8.4 (Q itself +2.5, so
net ≈ −6). Surprises: X and Z positive (+2.1), and every common letter
(E, A, R, N, T) slightly negative, i.e. worse than a fresh draw. The
hand-written values (leave bot, champion_1) have the order mostly right and
the sizes off: blank and S too high, E/R/N/T the wrong sign, duplicates
punished half as much. Caveats: next turn only; greedy players' games; linear.

## 2026-10-04 · Step 1b: do measured values play better? (no API)
Players: the leave bot with its tile table, duplicate and Q-without-U terms
replaced by the measured ones. Two versions, since the vowel balance term was
not measured: "measured" (term dropped) and "measured_vowels" (term kept).
Each plays champion_1, the leave bot and greedy on the same 400 fresh games
(seeds 600000+, untouched), seats swapped.
Expect (honest prior): both beat greedy clearly. Against the leave bot and
champion_1, within ±0.05 of 0.5. Measured from greedy play, the blank and S
values are likely too low (Quackle's are ~+25 and ~+8, close to the hand
values), so a small loss to the leave bot would not surprise me. A win
≥ 0.55 would say evidence beats memory even from weak games.

### Outcome (2026-10-04)
400 fresh games each (±0.05 at 95%), no forfeits, ~16 ms per move:

| | vs champion_1 | vs leave bot | vs greedy |
|---|---|---|---|
| measured | 0.472 (−7.9) | 0.504 (+1.1) | 0.598 (+24.3) |
| measured_vowels | 0.487 (−6.0) | 0.520 (+3.0) | 0.595 (+23.6) |

Matches the prior: all within ±0.05 of 0.5 against the leave bot and
champion_1; both beat greedy clearly. Evidence from greedy games, next turn
only, ties the hand-written guesses; it does not beat them. The vowel term
adds nothing visible. Results in rounds/measured/results.txt.

## 2026-10-05 · Step A: measure again from better games (no API)
The step 1 values now choose the moves (20% of moves picked at random from the
top five, so leaves still vary). 5,000 games each, fresh seeds 810000+. Two
fits, to separate the two causes named in step 1b:
- A1: better games, horizon 1 (next own turn).
- A2: better games, horizon 2 (next two own turns).
Then each set plays the leave bot and champion_1 on the step 1b games
(seeds 600000+, 400 games each).
Expect: the blank and S rise toward the hand values (A2 more than A1),
duplicates stay clearly negative. In play, still within ±0.05 of 0.5 against
both; one round of this loop will not be enough to beat them. If A2 beats A1
in values but not in play, the leave is not what separates these players.

### Outcome (2026-10-05)
Values (blank / S / each duplicate / Q without U): round 1 +15.0 / +3.2 /
−4.6 / −8.4; A1 +13.9 / +3.7 / −5.7 / −10.6; A2 +19.2 / +5.1 / −6.7 / −15.1.
Better games alone did not raise the blank (prediction wrong for A1); the
two-turn horizon did. Good tiles and bad tiles both grow with the horizon.
Play, 400 games each (±0.05): A1 0.505 vs leave, 0.453 vs champion_1;
A2 0.532 (+7.1) vs leave, 0.496 (−6.5) vs champion_1. Within the prior's
band; A2 is the best leave set so far but crosses no bar. champion_1 still
leads on spread; it uses the board (open triple-word squares, unseen tiles),
which no leave value can.

## 2026-10-11 · H1: fast and slow inside the player (no API)
Fast = the equity rule: points + A2 leave values. Slow = simulation: the fast
rule's top 6 moves, each played into the same 20 sampled worlds (unseen tiles
only), the opponent replies with the fast rule, scored by points ahead + leave
difference. ~12 s per slow move.
- H1a: slow vs fast, 200 duplicate games (seeds 610000+).
- H1b: from slow's decisions in those games (bag 7+), fit the fast rule's
  weights to slow's outcomes within each position (score, leave, empty TW/DW/TL
  squares the move newly opens, tiles played). The distilled rule plays the
  old one on 200 different games (seeds 620000+).
Expect: H1a slow wins 0.55-0.60 (+10 to +20 spread). Its edge comes from the
opponent's reply, so the fit gives opened premium squares clear negative
weights (TW most), score ~1, leave ~1. H1b: the distilled rule beats the old
one by a small margin (0.52-0.56); it cannot see the board as well as slow, so
it recovers only part of slow's edge. If slow does not beat fast, H1b is not
run: there is nothing to distil.

### Amended before the larger check (2026-10-11)
H1b at 200 games was 0.532 ±0.069, spread +10.4 ±13.9: inside the prediction
but not distinguishable from a tie. Both players are instant, so the same
check runs on 2000 games (seeds 620000-620999, none used for fitting). The
prediction stands: 0.52-0.56. Judged on spread, which is the more sensitive
number.

### Outcome (2026-10-11)
- H1a, slow vs fast, 200 games: **0.580 ±0.068, spread +17.2 ±12.9**, 14 s per
  slow move. Matches the prediction: slow is clearly better.
- Fit over 1825 slow decisions (bag 7+): score +1.02, leave +0.83, opens a TW
  -3.4, a DW -0.95, a TL -0.62, each tile played -1.7. Slow's edge is defence,
  as predicted; the tiles-played penalty was not expected.
- H1b, distilled fast vs old fast: 200 games 0.532 ±0.069 (+10.4 ±13.9);
  2000 unseen games **0.519 ±0.022, spread +3.4 ±4.2**. Inside the predicted
  range, but the spread interval includes zero: at best a small gain.
Reading: slow knows something real (+17 a game); the fast rule recovers at
most a fifth of it. The bottleneck is what the fast rule can express. Three
counts of opened premium squares are a crude stand-in for "what can the
opponent score next", which slow sees directly. Distillation works only as
far as the features let it.

## 2026-10-11 · H1c and H3: how far does distilling go?
H1c (done before writing this): fitted on half of slow's decisions, tested on
the other 913, the distilled rule picks slow's move 62.8% of the time (fast
today 57.8%) and loses 1.36 points a move against slow (fast today 1.79): a
quarter of the gap closed.

H3, expert iteration: round k, slow thinking with fast_k (shortlist and
rollouts) plays fast_k for 100 games (seeds 630000+1000k); fit fast_k+1 on
those decisions; fast_k+1 plays the original fast on the same 2000 games as
H1b (seeds 620000+). Three rounds, starting from H1b's fast_1 (0.519, +3.4).
Expect: a plateau. With six features the rule can hold little more than it
has, so fast_2..fast_4 stay within +3 spread of fast_1 against fast_0, and the
weights settle. If the spread keeps rising round on round, iteration is doing
more than the representation lets one round do.

H3 outcome (same 2000 games each, vs fast_0):

| rule | win | spread | slow(fast_k) vs fast_k, 100 games |
|---|---|---|---|
| fast_1 | 0.519 ±0.022 | +3.4 ±4.2 | 0.580, +17.2 (H1a, slow on fast_0) |
| fast_2 | 0.508 ±0.022 | +2.0 ±4.2 | 0.500, +9.3 |
| fast_3 | 0.513 ±0.022 | +2.4 ±4.2 | 0.610, +23.6 |
| fast_4 | 0.512 ±0.022 | +2.3 ±4.2 | 0.475, +6.6 |

**Plateau, as predicted.** No round beats fast_1; the weights wander inside
a small band (DW -0.95 to -1.48, TL -0.62 to -1.19, tiles -1.35 to -1.71)
without a trend. Slow still beats each new fast (about +14 a game on average,
noisy at 100 games), so the knowledge is there and the rule cannot hold it.
Iteration with a fixed six-feature rule adds nothing after one round. The
next lever is the representation (H2: new features, weighed by slow's lessons).

## 2026-10-14 · S1: does choosing a plan beat sticking to one?
H1–H3 tuned how one move is scored. Strong players think a level up: what
kind of game to play for the next few turns. S1 asks whether that level
matters for our bots at all.

Plans, each a fast rule over the same six features (scrabble/plans.py):
- steady: fast_1, the distilled rule (also the opponent in every game)
- open: steady, but opening premium squares is rewarded (T +2, D +1, t +0.5)
- close: steady with the board penalties doubled (T -7, D -2, t -1.2)
- turnover: steady, but each tile played +1.5 and leave weighted 0.6

Players, all against steady:
- each fixed plan: 2000 games (bags 640000+, both seats)
- shuffle: a random plan at each checkpoint (control: mixing without choosing)
- planner: at its first turn with the bag at 70, 45 and 20 tiles or fewer,
  plays the rest of the game out 12 times under each plan (same 12 invented
  worlds for every plan, opponent playing steady) and commits to the plan
  that won most often. 400 games (the first 200 bags), for cost.

Prediction: the planner beats the best fixed plan on the same 200 bags by at
least 0.05 win rate, and beats shuffle. Power: with 400 games the margin is
about ±0.05, so a smaller gain will read as "not shown", not "absent".
If the fixed plans all score about the same, plans barely matter at this
level and S2 (the model writes plans) has nothing to build on.
Known bias: the planner's rollouts assume the opponent plays steady, which is
true here. Against an unknown opponent the edge would be smaller.

S1 outcome. Fixed plans vs steady, 2000 games: open 0.501, close 0.502,
turnover 0.439 (-12.2 a game), shuffle 0.481. Planner, 400 games (first 200
bags): 0.491 ±0.049, spread -3.7. Paired on the same games, planner minus:
open -0.022 ±0.050, close -0.001, shuffle -0.003 ±0.047, turnover +0.060.

**Not shown.** The planner plays exactly like random switching. Its 1200
choices are near uniform (open 336, steady 307, turnover 308, close 249),
though turnover is clearly the worst plan. Twelve rollouts per plan give each
plan's win rate an error of about ±0.14, far larger than the gaps between
plans, so the argmax is mostly noise. What S1 does show: plans change the
result (turnover costs 12 a game), and no fixed plan beats the distilled rule.
Whether choosing helps is untested at this budget; the next test needs many
more rollouts per decision (or fewer, more different plans).

## 2026-10-15 · N1: does a network that reads the board beat six features?
H3 and S1 both hit the same wall: six hand-picked features can't hold what
search knows. N1 replaces them with a small network (scrabble/value.py).

Data: 18000 new self-play games (bags 700000+, none used anywhere else),
steady against itself, taking one of its other top five moves 15% of the time.
Every move's position after the move is saved, seen by the player who made it.
Target: final spread minus the spread just after the move (Monte Carlo, the
result of the game; TD bootstrapping is a later step). A tenth of the games
(seed % 10 == 0) is held out.

Players: among steady's top ten moves, choose by spread after the move plus
V(position after). Network V: 7 board planes (filled, tile values, open TW/DW/
TL/DL, empty next to a tile) through 3 small conv layers, plus leave, unseen
tiles, bag, lead and the five non-score features. Control V: a linear fit of
the same five features on the same rows and target. Same shortlist, same data,
so a difference between them is the representation's alone.

Gate: if the network's held-out error is not below the linear control's, the
network duels are skipped and that is the result.

Yardstick: the H3 check games (bags 620000+, 2000 games), vs fast_0, where
fast_1..fast_4 scored +2.0 to +3.4; and vs steady.
Prediction: the network beats the linear control by at least +8 spread a game
against fast_0 (the smallest gain 2000 games can show, ±4.2), and beats steady.
If it doesn't, the likely reason is the target: a whole game's luck is in
every label (held-out spread varies by about ±70), and 400k positions may be
too few to average it out. Then TD targets or more games come next.

N1 outcome. Held-out error (45158 positions, 1800 games): mean only 4008,
linear 3910, net 3877 (2.4% vs 3.3% of the variance). Gate passed.

| player | vs fast_0 (2000) | vs steady (2000) |
|---|---|---|
| linear control | 0.486, -1.6 ±4.3 | 0.496, +0.6 ±4.4 |
| network | **0.525, +5.7 ±4.3** | 0.511, +3.4 ±4.3 |
| net minus linear, paired | **+0.039 ±0.025, +7.3 ±4.4** | +0.015 ±0.025, +2.8 ±4.4 |

**Partly shown.** Against fast_0 the network beats the same-data control by
+7.3 a game (interval excludes zero), just short of the predicted +8, and is
the best fast player so far (fast_1..4: +2.0 to +3.4). Against steady the
edge shrinks to +2.8 and is not shown. Reading the board carries real signal
the six features miss; this first version (Monte Carlo targets, 8 epochs,
400k positions) captures a little of it. Next levers: TD targets (less noise
per label), more games, and the network inside the slow player (expert
iteration with a rule that can grow).

## Y1: score decisions, not games (2026-10-17)

Why. The literature (rounds/LITERATURE.md) says static evaluators gain about
2% in win rate (Del Solar's CNN: 51.7% over 255k games); our 2000-game duels
see about 2.5%. The next players put the network inside search, and a slow
game costs ~100 s, so duels of search players cost ~50 CPU-hours each.

Method (`oracle.py`). 1000 positions, one per bag from 900000 (unused), at a
random turn of an exploring steady self-play game. Candidates: steady's top
ten plus fast_0's pick. Each is played out to the end in the same 24 invented
worlds, steady on both sides (one world when the bag is empty), and valued by
its win rate and final spread. A player's score is the value of the move it
picks; regret is the best candidate's value minus that. Labels cost ~210
CPU-seconds a position (~5 h on 12 cores), once; scoring a player costs one
decision per position. The suite is never trained on.

Known from duels: slow beats fast_0 (0.580, +17); net beats linear (+7.3 vs
fast_0). Per decision that is about +0.6 spread on average (a game has ~12).

Predictions:
- P1 (agrees with duels): slow - fast_0 and net - linear both positive on
  spread with intervals excluding zero. If either reverses, the oracle (steady
  rollouts) is biased and Y1 is not used.
- P2 (power): net - linear is shown on spread (z >= 2). On win rate it may not
  be: the per-decision edge (~0.003) is below what 1000 positions resolve.
- Cost honesty: for two fast players a duel is cheaper than building the
  suite. Y1 pays for itself on reuse and on search players.

## N2: what the network reads, and what it predicts (2026-10-17)

From the literature (LITERATURE.md, Del Solar 2025): letters and cross-sets
on the board helped; win as the target beat spread.

Method (`value2.py`). N1's 450k positions and held-out games, unchanged. Two
networks with the same trunk (4 conv layers, 48 channels), trained 8 epochs
with the transpose (which swaps across and down) as augmentation:
- v1 reads N1's seven planes;
- v2 adds the letter on each square (embedded) and, for each empty square,
  how many letters hook there across and down.
Each has two heads trained together: the spread to come and the chance of
winning (tie 0.5). Four players, inputs x head; each picks among steady's top
ten (spread head: lead + V; win head: highest chance).

Measures. Held-out spread error and win log-loss. Then each of the four
players duels steady on the check games (620000, 2000 games): this is
exploratory, for picking the best arm. The best arm is then confirmed alone on
fresh bags (650000+, 2000 games) against steady, with N1's net on the same
bags. Y1 scores are reported as secondary (Y1 has not yet passed its own check).

Primary comparison (one): best arm minus N1 net, paired, against steady, on
the fresh bags. Prediction: positive, +0.025 win rate or more (about what the
paired comparison can show at 2000 games).
Secondary predictions: v2 has lower held-out loss than v1 on both heads; for
the same network, the win head wins more often than the spread head, maybe
while scoring fewer points (Del Solar's finding).

## S2: the network inside search (2026-10-17)

From the literature: AlphaGo (a value network judges where simulations stop),
Gumbel AlphaZero (with few simulations, sequential halving over the prior's
top moves), Maven (simulation is Scrabble's strength).

Method (`search.py`). The network (the N2 arm chosen by N2's exploratory
duels, fixed by that rule before its numbers are in) proposes its top 8 of
steady's top ten. Each simulation plays the move in an invented world, lets
steady play two more plies, and the network values the position there.
Sequential halving: each round the surviving candidates get an equal share of
the budget in the same worlds, the worse half is dropped. Budget 64
simulations a decision. Ablation 'flat': the same budget split evenly.

Measures (Y1 positions, decision values from the oracle; plus one duel).
Primary: s2 minus slow (the Maven-style player, 6 candidates x 20 worlds,
1 ply, fixed rule) on Y1 spread value, paired. Prediction: positive, shown.
Secondary: s2 minus its own network without search (does search add to the
network?); s2 minus flat (does halving beat even spending?); s2 against steady
on fresh bags (660000+, 1000 games), predicted above 0.5.
If Y1 fails its own check, the duel against steady becomes the primary.

N2 exploration (check games 620000, 2000 games each vs steady):
v1-spread 0.517, +4.2 ±4.3; v1-win 0.496, -3.8; v2-spread 0.505, +1.3;
v2-win 0.480, -5.4. Held-out: v1 best spread mse 3864, win log-loss 0.409;
v2 best 3878 / 0.415, then overfit (4336 by epoch 8).
Secondary predictions not shown: v2's richer board did not lower held-out
loss (18k games are too few for it; Del Solar had 7.5M), and the win head
played worse than the spread head for both networks.
Arm carried forward by the rule: v1-spread. Confirmation (primary) queued on
bags 650000+, and S2 uses v1-spread.

Y1 outcome (1000 positions, 24 worlds; labelled on laptop 256, EC2 744).
Regret in spread a decision: slow 10.99, steady 11.19, fast_0 11.22,
net 11.48, linear 11.65 (each ±0.9).
- slow - fast_0: +0.23 ±0.80 spread, +0.003 ±0.005 win.
- net - linear: +0.17 ±0.54 spread, -0.000 ±0.004 win.
**P1 not shown, P2 not shown.** Neither pair reversed, but neither interval
excludes zero: Y1 is not biased as far as it can tell, it is too weak. The
players agree on most positions (those add nothing), and where they differ
the edge is a fraction of a point against ±4-8 points of world noise per
position. Split halves of the worlds agreed on the best move in 22% of
positions. Y1 is not used as a yardstick; S2's primary falls back to the
duel against steady, as pre-registered.
Lesson, and the fix the active-oracle paper describes: spend labels on the
positions where the players being compared disagree, and many worlds on just
the moves they chose, not 24 worlds on ten candidates everywhere.

N2 outcome (primary, fresh bags 650000+, 2000 games vs steady, paired):
v1-spread 0.533, +7.3 ±4.4; N1 net 0.516, +2.8 ±4.4.
v1-spread minus N1 net: **+0.017 ±0.026 win, +4.4 ±4.7 spread. Not shown**
(predicted +0.025 or more). Same inputs as N1; the changes were a wider
trunk, the transpose augmentation, and the extra win head in training.
Not pre-registered, but worth recording: on fresh bags v1-spread beats steady
by itself (0.533 ±0.022, +7.3 ±4.4), the first fast player whose interval
clears steady. With N1's net the same bags gave +2.8, not clear.

## W1: against the world's yardstick, Macondo's HastyBot (2026-10-17)

Why. Steady is our own bot; the world measures against HastyBot (BestBot
beats it ~60%, Del Solar's CNN 51.7%). `macondo.py` runs Macondo v0.13.8 as
a shell; each HastyBot turn gets a standard CGP from its side (own rack only)
and its top static move (points + NWL23 leave table, on our ENABLE word list,
built with wolges buildlex) is matched back to our legal moves by the tiles
placed. Games where a move cannot be matched are skipped and counted.

Players vs HastyBot, bags 670000+ (1000 games each): steady, v1-spread, S2.
Predictions: steady loses to HastyBot (below 0.5; HastyBot's leave table is
far richer than steady's); v1-spread and S2 do better than steady, in that
order. Target for the section: reach 0.5 against HastyBot, then ~0.6 (BestBot's
level).

## E0: how much does steady lose once the bag is empty? (2026-10-17)

Measure before building (`endgame.py`). 300 steady self-play games, bags
680000+, stopped at the first turn with an empty bag. Macondo's endgame
solver (6 plies) gives the final spread under best play; steady's move is
valued by solving the position after it from the other side.
Prediction: steady loses 5 or more points a game on average to best play, and
the result flips in at least 3% of games. If so, an exact endgame is the next
thing to build; if under 2 points, skip it. (First three test positions: 11,
0, 69 points lost; one flip. Not counted.)

S2 outcome (duel, primary after Y1 failed): s2 vs steady, bags 660000+,
1000 games: **0.532 ±0.031, +6.3 ±6.0. Shown**, narrowly. The Y1 secondaries
(s2 vs slow, vs its own network, vs flat) were all within noise on Y1.

W1 so far (bags 670000+, 999 games each; one game skipped in both, a parsing
slip now fixed: a long word ran into Macondo's leave column):
steady 0.490 ±0.031, -3.4 ±6.2; **v1-spread 0.533 ±0.031, +5.4 ±6.1.**
Paired v1-spread minus steady: +0.042 ±0.039 win, +8.8 ±7.1 spread (shown).
Predictions so far hold: steady below 0.5 (not clear of it), v1-spread above
steady. v1-spread above 0.5 against HastyBot, interval just clear of it:
about where Del Solar's CNN is (51.7%), on 1000 games rather than 255k.

W1 confirmation (pre-registered before running): v1-spread vs HastyBot on
fresh bags 690000+ (2000 games). Prediction: above 0.5 with the interval
clear of it (about ±0.022 at 2000 games). Only this run decides whether
"beats HastyBot" is claimed.

W1 confirmation outcome: v1-spread vs HastyBot, fresh bags 690000+, 2000
games: **0.493 ±0.022, -1.2 ±4.4. Not shown.** The first run's 0.533 (999
games) was the lucky end of the noise; pooled over 2999 games, about 0.506.
S2 vs HastyBot (bags 670000+, 1000 games): 0.528 ±0.031, +6.3 ±6.3, not clear
of 0.5. Verdict: our best players are about level with HastyBot, not ahead.
This is why the confirmation was pre-registered: claiming a win on the first
run would have been the winner's curse.

E0 outcome: 320 endgames (bags 680000+): steady loses **9.35 ±1.37 points a
game** to best play once the bag is empty, and the result flips in **11 of
320 (3.4%)**. **Shown** (predicted 5+ points and 3%+ flips). An exact
endgame is the next thing to build. Caveat: the solver ran 6 plies, near
exact for most endgames but not all.

## S3: the BestBot shape with learned leaves (2026-10-18)

Why: TileFish's ablations put trained leaves at +39 points a game over none
(+3.7 over a good hand-made table), exact endgames at +5.5, simulation over
static play at +12. Our A2 leaves are crude; E0 measured 9.35 points a game
lost in endgames. 60% against HastyBot needs about +25 to +30 a game.

Players: `klv` (HastyBot's own rule in our code: points + NWL23 leaves),
`s3-<leaf>-<budget>` (shortlist, prior and rollouts by the klv rule,
sequential halving, leaf = points + leaves or the v1 network), `s3e-...`
(the same, plus Macondo's exact solver once the bag is empty).

G0 gate (bags 710000+, 500 games): `klv` picks HastyBot's move on 90%+ of
its turns and wins 0.50 ±0.045. If not, the leaves are wired wrong; stop.

Development (bags 710000+ only, 500 games each): budget, plies and leaf are
chosen here. Secondary readings: s3e minus s3 (what the endgame is worth),
net leaf minus klv leaf.

Primary (bags 720000+, 1000 games, run once, after development is frozen):
the chosen s3e player vs HastyBot. Prediction: win above 0.5 with the
interval clear of it (±0.031). 0.55+ would be a strong result; 0.60 is
BestBot's level and not expected today. Seconds per move reported with it.

Discarded (2026-10-18 04:20 UTC): the first s3e-klv-64 run skipped 42 of
142 games. A Macondo startup log line contains "error=", which the solver
read as a failed solve; every later answer was the previous position's
move. The skipped games were the ones reaching a solved endgame, so the
partial result (0.515 over 100) is biased and thrown away (kept on the
runner as held/bad-s3e-klv-64.jsonl). Fixed (only the shell's own "Error:"
lines count as failures); all 25 endgame moves in 10 test games now match.

S3 development, first arm (bags 710000+, 500 games): s3e-klv-64 vs HastyBot
**0.502 ±0.044, -0.1 ±9.2**, 8.6 s a move. Paired against static `klv` on
the same bags: **-0.031 ±0.057 win, -8.2 ±10.9 spread**. Simulation at this
budget does not beat its own prior, even with the exact endgame added.
Suspected cause: sequential halving makes its first cut on about 2 rollouts
per candidate, so noise overrides a good prior. The other budget-64 arms
were stopped (s3e-net-64 at 45 games, set aside) until this is checked.

Added before any confirmation run: `klve` (klv until the bag is empty, then
Macondo's exact solver; no simulation). It is an eligible primary
candidate for the 720000 confirmation alongside any fixed S3. The choice
between them is made on 710000 data only. Solver give-ups and seconds per
solve are now logged per game. Diagnosis (s3diag, 200 positions): how
often S3 overrides klv, the spread of one rollout, and the top-8 equity
gaps.

Diagnosis outcome (s3diag, 200 mid-game positions): S3 picks klv's top
move only 50% of the time. One rollout's sd is 25.9 points; the paired
difference between the top two candidates on the same worlds still has sd
25.1, while their equity gap is 3.0 (median). Sequential halving cuts on
about 2 rollouts each (se ~18 against a gap of 3): the cut is a coin flip.
Confirmed: noise, not the leaf. Resolving 3-point gaps needs ~280 rollouts
per candidate; our Python does ~8 s a move at 64 in total.

klve outcome (bags 710000+, 500 games): **0.564 ±0.043, +15.0 ±9.1** vs
HastyBot, 0.43 s a move; 964 endgame solves, none gave up, 2.7 s each.
Paired against klv (same bags; games identical until the bag empties):
**+0.031 ±0.016 win, +7.0 ±1.4 spread**. The exact endgame is worth about
7 points a game in play (E0 measured 9.35; TileFish reports 5.5).

Primary choice, frozen now from 710000 data only: **klve**. Confirmation:
klve vs HastyBot on bags 720000+, 1000 games, run once. Prediction: win
above 0.5 with the interval clear of it; best guess 0.54-0.56. Secondary
(development, 710000 only): S3 with the prior shrinkage fix,
s3e-klv-64-k4-n16 (4 candidates, the static value counted as 16
rollouts), paired against klve.

Confirmation outcome (bags 720000+, 1000 games, run once): **klve vs
HastyBot 0.547 ±0.031, +9.1 ±6.2. Shown**: the interval (0.516 to 0.578)
is clear of 0.5. 0.42 s a move; 1921 endgame solves, none gave up. The
first confirmed win over HastyBot. Within the predicted 0.54-0.56.
What it is: HastyBot's own leaves plus an exact endgame. The gain is the
endgame (+7 points a game, measured paired), the step from HastyBot
towards BestBot (about 0.60), which also simulates and solves
pre-endgames.

S3 shrinkage (secondary, bags 710000+): s3e-klv-64-k4-n16 stopped at 422
games when one Macondo process exited ("macondo exited"; not yet
diagnosed). On those 422, paired against klve: **+0.017 ±0.056 win, +2.5
±10.7 spread**: no gain shown. Shrinkage stops simulation from doing harm
but cannot add skill at this budget. Simulation waits for a faster engine.

## B0: our best against a BestBot-shaped opponent (2026-10-18)

Why: 54.7% against HastyBot says nothing about BestBot, the bot that matters.
Macondo's own SIMMING_INFER_BOT plays about one game pair per 45 minutes on
this machine, too slow to measure. Instead `macondo.py --vs sim` builds the
opponent from the Macondo shell: the top 15 plays by equity, a 2-ply sim that
stops once the best play is 99% sure (one thread), and the exact endgame
solver once the bag is empty. It is BestBot's shape without rack inference or
the pre-endgame solver, so it is weaker than BestBot, and a win here is not a
win over BestBot. The opponent never sees our rack.

Run: klve vs sim, bags 740000+, 500 bags x 2 seats = 1000 games (about
+-0.03), run once. Smoke test (bags 739000, 2 games) only checked the
plumbing and is not counted.
Prior: klve loses, about 0.40-0.45; simulation plus the same endgame should
beat static play plus endgame. Below 0.45 means the gap to BestBot is
simulation, which is what the luck-cancelled rollouts (H1) are for.

Outcome (run once, 1000 games, nothing skipped): klve vs sim @740000: win
0.420 +-0.031, spread -10.0 +-6.2. Inside the prior and below 0.45: the
sim opponent beats klve, so the gap to BestBot is simulation, and H1 is the
next thing worth testing. 0.40 s a move on average (sim with
early stop); 1568 endgame solves, none gave up. Results:
macondo/duel_klve_vs_sim_740000.jsonl, line in macondo/duels.txt.

## B1: from 0.42 to 0.53 against the sim opponent (2026-10-19)

Goal set by the user: 0.53 against `--vs sim` with 2-3 hypotheses, each
from first principles, each found by measuring where klve loses.

What the B0 file already says (per game only): seat 0 (first) 0.469, seat 1
0.371. To reach 0.53 about 110 of 1000 games must flip; 11% of games were
lost by 24 points or less, so a change has to be worth roughly 24+ points a
game against this opponent (more, since some close wins also flip back).
That is about what simulation is worth in total (TileFish: +12 over static
play, plus inference and pre-endgame). A stretch; said so up front.

D1 (diagnosis, not a test): klve vs sim with every move logged, bags
750000+, 100 bags x 2 seats. Then each of klve's moves is re-scored offline
by a reference stronger than the opponent (Macondo sim, 3 plies, more
candidates, klve's move always included, same iterations for every
candidate). Loss per move = reference best minus klve's move, in equity.
Grouped by bag (50+, 8-49, 1-7, 0), move type (exchange, bingo, other),
and lead. Check of the method: bag 0 should show about zero loss (exact
solver). Hypotheses are chosen from the largest groups, written here
before they are tested.

Rules for every B1 test, fixed now:
- Development bags 760000+, paired against klve on the same bags.
- Compute: our time per move is at most the opponent's measured time per
  move (logged from D1 on), and both are reported. If Macondo's simulator
  is used inside our player, that is stated, as klve states its solver.
- Confirmation: the frozen best player, bags 800000+, 2000 games, run
  once. Success = point estimate 0.53 or more. Interval clear of 0.50 is
  reported as the weaker claim.
- 0.53 against this opponent is not a win over BestBot (no rack inference,
  no pre-endgame solver on its side).

Amended before any B1 test (2026-10-19, time limit set by the user):
development runs are 300 games each (paired against klve on the same
bags), confirmation is 1000 games on bags 800000+ (about +-0.031), run once.
Success rule unchanged.

D1 outcome (bags 750000+, 200 games, klve 0.435): 2068 of klve's moves
re-scored (Macondo sim, 3 plies, top 20 + klve's move, 15 s each). klve
loses 19.2 points and 10.0 win-% a game to the reference, about the size
of the gap, so the method sees it. By bag: 50+ 4.7 pts / 1.9 win-%; 8-49
7.6 / 3.5; **1-7: 6.9 / 4.6 from only 185 moves (7.5 pts a move)**. By
move: ordinary plays carry it (18.1 pts); bingos 1.0, exchanges 0.2. By
lead: close games 5.7 win-%, behind 40+ 3.2, ahead 40+ 1.1.

Hypotheses (development bags 760000+, 300 games each, each paired against
klve on the same bags; ours <= the opponent's seconds a move):
- H1 pre-endgame: klve+peg. Bag 1: Macondo's pre-endgame solver (every
  draw played out, 8 s); bag 2-7: the 2-ply sim. Prediction: +0.02 to +0.04
  win (recovers much of the 4.6 win-% measured at bag 1-7).
- H2 midgame lookahead: klve+peg+sim, i.e. H1 plus the 2-ply sim for bag
  8+ (the opponent's own method, so on its own it should reach about even).
  Read as (H1+H2) minus H1. Prediction: +0.03 to +0.06 over H1.
- H3 depth for breadth: klve+peg+sim3, the same with 3 plies over 10
  candidates instead of 2 over 15, same stopping rule. Why: the reference
  that measured the losses is 3-ply, and the 11th-15th candidates are
  rarely best. Prediction: +0.01 to +0.03 over H2, if the time fits.
The earlier H3 (static win chance) is dropped before testing: with the bag
fixed, win chance is monotone in points, so it would rarely change a move.
The frozen player is the best of these on development data; confirmation
as amended (1000 games, bags 800000+).

Note (2026-10-19 06:40 UTC): all four development runs stopped early when
a Macondo process died (out of memory from the pre-endgame solver's tables,
16 workers x 3 shells; one earlier crash not memory). Games already
written are kept (39 / 59 / 136 / 42). Fix: a dead Macondo is restarted
and the move retried, shells use a smaller table, 12 workers. The runs
resume on the same bags to 300 games each. Nothing else changes.

H1 development outcome (bags 760000+, 300 games): klve+peg 0.420 vs klve
0.465 on the same bags, paired -0.045 +-0.047 win, -5.9 +-8.3 spread. Not
shown; leaning negative, against the +0.02..+0.04 predicted.

Process amendment (2026-10-19): H1 went to a duel without the isolation
step. From now on every fix must first pass an offline gate on logged
positions, judged by something trustworthy in that region, before any
duel.

I1 (isolation, bag 1, run after the H1 duel): the 29 D1 positions with one
tile in the bag, judged by a 60 s pre-endgame solve on an idle core.
Mean win share of the chosen move: klve 42.6 (optimal 18 of 22), 8 s
solver 51.4 (26 of 27), 2-ply sim 53.8 (20 of 23). Paired klve vs 8 s
solver (22): solver better 3, worse 0, +4.5 win-% a position. Reading:
the bag-1 fix is sound but small (about +0.005 a game, at one bag-1 turn
per 7 games); D1's large bag 1-7 loss was mostly the 3-ply sim yardstick's
own error there. H1's duel loss, if real, must come from its bag 2-7 sim
branch, which has no trusted judge yet.

I2 (isolation, bag 2, D1 positions, judged by a 120 s pre-endgame solve):
mean win share klve 44.8 (optimal 19 of 31), 16 s solver 47.9 (24 of
32), 2-ply sim 48.2 (20 of 31). Paired against klve: solver better 9,
worse 0 (+4.6); sim better 8, worse 2 (+3.4). Reading: H1's sim branch is
not harmful at bag 2; H1's duel dip is most likely noise (bags 3-7 still
have no trusted judge). The pre-endgame is worth about +0.01 a game in
total, not the 0.046 D1 suggested. Solver at bag 2 beats the sim there:
a candidate for later, not added to the frozen player untested.

H1+H2 development outcome (bags 760000+, 300 games): klve+peg+sim 0.530
+-0.056, +2.8 spread; ours 8.32 s a move, theirs 8.24. Paired: vs klve
+0.065 +-0.070 win (not shown), vs H1 +0.110 +-0.067 (shown).

Frozen (2026-10-19, development data only, before H3 finished):
**klve+peg+sim**. H3 (klve+peg+sim3) read 0.536 at 235 games but used
10.8 s a move against the opponent's 7.1, outside the compute rule, so it
is not eligible. Confirmation: klve+peg+sim vs sim, bags 800000+, 500 bags
x 2 seats = 1000 games, run once. Projection written now: about 0.51
(0.49-0.53); H2 is the opponent's own method, the exact endgame is on
both sides, and the pre-endgame edge measured offline is about +0.01.

H3 development outcome (bags 760000+, 300 games): klve+peg+sim3 0.533
+-0.056, 10.74 s a move (opponent about 8); paired against H1+H2 +0.003
+-0.067. Depth for breadth bought nothing at this budget and cost 30% more
time. Not eligible (compute rule) and not better.

C1: the ceiling of rack inference (written while the confirmation runs,
before its result). klve+peg+sim+oracle: H1+H2, but every sim is told the
opponent's real rack (cheating; never a candidate player). Development bags
760000+, 300 games, paired against H1+H2 on the same bags. It measures the
most any rack inference could add. Read: under +0.03, inference cannot
reach the high 50s and is not built; +0.06 or more, inference is worth
building and gating offline (judge: the sim with the true rack, known in
logged games).

Confirmation outcome (bags 800000+, 1000 games, run once): klve+peg+sim vs
sim **0.505 +-0.031**, spread +0.0 +-6.2; 7.60 s a move, endgame solves
1675 (gave up 0). Seat 0 0.582, seat 1 0.428. Close games (|spread| <= 20)
0.548 of 166. Against the rule: the point estimate is under 0.53, so B1's
goal is **not met**; the interval (0.474-0.536) does not clear 0.50, so
the weaker claim is not met either. The projection (about 0.51) held. Read:
klve+peg+sim is level with the BestBot-shaped opponent; against B0's 0.420
on 740000+ that is +0.085 on separate bags (unpaired). The 300-game 0.530
on development bags was the winner's curse of picking the best of three
arms.

C1 outcome (bags 760000+, 300 games): klve+peg+sim+oracle 0.647 +-0.054,
spread +35.4; 4.50 s a move. Paired against H1+H2 on the same games:
**+0.117 +-0.071 win, +32.6 +-12.9 spread** (vs klve +0.182 +-0.072).
Over the +0.06 bar: rack inference is worth building and gating offline.
A perfect read is worth about 12 points of win rate; a real inference gets
a fraction of that.
