# How game-playing networks were built and measured

Read 2026-10-17, for the next section: a strong, general Scrabble player.

## What each one teaches

- **TD-Gammon** (Tesauro 1995). A small network over the position, trained by
  self-play on what happened next. Measured against humans and other programs.
  The idea we copied in N1.
- **AlphaGo Zero / AlphaZero** (Silver et al. 2017, 2018). Search makes the
  network's choices better; the network learns from the search; repeat. Each
  new network had to beat the last in 400 games (55%) before it replaced it.
  Strength was shown as Elo against fixed opponents, with ablations of each
  part and curves of strength against thinking time.
- **Stochastic MuZero** (Antonoglou et al. 2022). For chance games
  (backgammon, 2048), values live on afterstates: the position after a move and
  before the dice. Our value is already on the afterstate.
- **Gumbel AlphaZero** (Danihelka et al. 2022). With very few simulations,
  sample a few candidates and use sequential halving: give more simulations to
  the moves still in contention. The direct fix for S1's winner's curse.
- **KataGo** (Wu 2019). 50x less compute through extra prediction heads
  (score, ownership) that only help training, global pooling, and spending
  search unevenly across positions. Predicting parts of the target helps.
- **Approximate value iteration in self-play** (2026). A value net with
  one-step greedy lookahead matches MCTS players at much lower cost. Backs our
  current shape: net re-ranks a shortlist.
- **Maven** (Sheppard 2002). Scrabble's strength comes from simulation: invent
  the hidden tiles, play candidates out, average. Our `slow`.
- **CNN static evaluator for Scrabble** (Del Solar 2025, Macondo's author).
  - 85 board planes: 26 letters, blanks, 52 cross-sets, 4 premiums, last
    play. Plus 76 scalars: rack, bag, score, leave, spread.
  - 6 residual blocks. Only the transpose is a true symmetry of the board.
  - Target: win/loss at the end of the game. A spread target over 5 turns
    "failed badly".
  - Data: softmax self-play beat injecting random weak moves.
  - 7.5M games. **51.7% over 255k games** against HastyBot (score + leave),
    while scoring fewer points (win rate and spread can disagree).
  - Next for them: the net inside Monte Carlo search.
- **Active oracle evaluation** (NeurIPS 2026, backgammon). Score each decision
  against an engine that values every move (regret), not games won.
  **8.1x fewer trials** for the same precision; rankings match head-to-head
  play (Kendall 0.93).
- **Luck adjustment** (GNU Backgammon, Montgomery 2000). Subtract the luck of
  the dice, measured by the evaluator, from each result: same answer, fewer
  games.

## What it means for us

1. **Measurement first.** Static-evaluator gains are about 2% in win rate;
   2000-game duels can only see about 2.5%. We need a decision-level
   yardstick: fixed positions, each move valued once by heavy simulation.
2. **Inputs and target.** Letters and cross-sets on the board, win as the
   target (or an extra head), softmax exploration.
3. **The net inside search, then iterate.** That is where the big gains were
   for every one of them. Sequential halving for our small budgets.
4. **Compute is our ceiling.** 1.6 s a game in Python (27k games an hour)
   against Macondo's 1000 games a second.
5. **General** means the encoding comes from the ruleset (tiles, board), not a
   hard-coded A-Z.

## Sources

- https://www.cesardelsolar.com/posts/2025-06-21-nn-scrabble/
- https://neurips.cc/virtual/2026/172941
- https://arxiv.org/abs/2609.09094
- https://arxiv.org/abs/1902.10565 (KataGo)
- https://iclr.cc/virtual/2022/poster/6418 (Gumbel)
- https://iclr.cc/virtual/2022/poster/6832 (Stochastic MuZero)
- https://www.gnu.org/software/gnubg/manual/html_node/Introduction-to-evaluation-settings.html
- https://bkgm.com/software.html (variance reduction)
