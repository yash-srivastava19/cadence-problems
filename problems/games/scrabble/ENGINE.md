# The engine front end

`engine.py` lets you use the players the way you use Stockfish: analyse a
position, play a game against one, or drive one from another program.
Run everything from `problems/games`.

```sh
T() { uv run --with numpy --with torch --index https://download.pytorch.org/whl/cpu python -m "$@"; }
F() { uv run --with numpy python -m "$@"; }   # enough for steady and fast_0, no torch
```

The `--index` flag keeps uv on the CPU build of torch. Without it, uv may
download the much larger CUDA build.

## Players

| name              | what it is                                              | time per move      |
|-------------------|---------------------------------------------------------|--------------------|
| `fast_0`          | points plus leave, the original rule                   | ~0.01–0.1 s        |
| `steady`          | the distilled fast rule (`rounds/fastslow/weights.json`) | ~0.01–0.4 s       |
| `v1-spread`       | the value2 net judging steady's top ten                 | ~0.1 s             |
| `s2-v1-spread-64` | S2: the net proposes, 64 simulations decide             | ~13 s at the opening, more mid-game (`s2-v1-spread-16` is about 4x faster) |

Every name that `oracle.py` knows by prefix works here too: `v2-win`,
`flat-v1-spread-64`, `s2-v2-win-32`. To add a player, add one line to
`PLAYERS` in `engine.py` that maps its name or prefix to a class with
`rank(g, moves, seed, seconds)`.

## Analyse a position

```sh
T scrabble.engine analyse "<CGP>" [--player s2-v1-spread-64] [--top 5] [--time 2.0] [--json]
F scrabble.engine analyse "15/15/15/15/15/15/15/15/15/15/15/15/15/15/15 AEINRST/ 0/0 0 lex NWL20;" --player steady
```

Both CGP forms work:

- Ours, from `cgp.py`: `... turn 6; held 7; bagsize 54;`
- Macondo's: `<rows> RACK/ 121/170 0 lex NWL20;`. With no `held`, the other
  player is assumed to hold a full rack while the bag lasts.

The engine reads only what the player to move can see. It draws the hidden
tiles at random from the unseen ones. If you write the other rack into the
CGP, the engine ignores it.

The output lists the top moves with their score, their leave and the
player's own value for each move, then a `time` line and a `bestmove` line.
What the value means depends on the player:

- `steady` and `fast_0`: equity.
- `v1-spread`: the expected final spread.
- S2: the net's prior. S2 keeps its own simulation averages inside
  `search.choose`, so the list shows the prior and `bestmove` is S2's choice.

`--time` sets how many simulations S2 runs. The engine times one simulation
and fits as many as the budget allows. For the other players, `--time` has
no effect, and every answer still reports the time the move took.

## Play a game in the terminal

```sh
F scrabble.engine play --player steady --seed 7 --you-first
```

You can type any of these:

- `8H WORD` for a play across, or `H8 WORD` for a play down. Write a blank
  in lowercase (`H4 GESTaTE`). For a letter already on the board, type the
  letter or `.`.
- `exchange ABC`, with `?` for a blank.
- `pass`
- `hint`, to see the bot's top moves for your rack.
- `quit`

The engine checks every move you type against its list of legal moves and
tells you what is wrong with one it can't accept.

## Play in the browser

```sh
F scrabble.engine serve --port 8765 --player steady
# open http://127.0.0.1:8765/
```

To place tiles, click a square and type a word. Click the square again to
type downwards. You can also click a rack tile and then a square. Enter
plays the word, Backspace takes back the last tile, and Esc recalls all of
them. The page shows the bot's reply and its top moves. The leaves of those moves would give away the bot's rack, so they appear only once the game is over. It follows the
system's light or dark mode, and the ◐ button switches between them. The
server answers only on 127.0.0.1 and runs one game at a time.

The page uses this API:

```sh
curl -s -X POST localhost:8765/api/analyse -d '{"cgp": "<CGP>", "top": 3}'
curl -s -X POST localhost:8765/api/new     -d '{"seed": 7, "you_first": true}'
curl -s -X POST localhost:8765/api/move    -d '{"move": "H4 GESTaTE"}'
curl -s -X POST localhost:8765/api/hint    -d '{}'
curl -s localhost:8765/api/state
```

## Drive the engine from another program

```sh
F scrabble.engine uci --player steady
```

The engine reads one command per line on stdin and answers on stdout:

```
uci                       -> id name cadence-scrabble / option player NAME / uciok
isready                   -> readyok        (loads the word list and the player)
player NAME               switch players
position cgp <CGP>        either CGP form
position startpos [seed N]
go [time S] [top N]       -> info multipv K move M score P value V ... / info time T / bestmove M
d                         print the board and the rack
quit
```

When a command fails, the engine prints `info string error ...` and keeps
reading.

## Tests

```sh
uv run --with numpy --with pytest python -m pytest scrabble/test_engine_cli.py
```
