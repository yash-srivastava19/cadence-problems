# Rackoon

A static site: one crossword board game position a day, find the best play in
three tries, plus a random practice set. Plain HTML, CSS and JavaScript, no build step. This README is
not deployed (`.vercelignore`).

| File | What it is |
| --- | --- |
| `index.html` | Every view: puzzle, archive, how to play, about |
| `styles.css` | Light and dark themes, board, rack, motion |
| `app.js` | Input, validation against the stored plays, teaching text, share, stats |
| `config.js` | Every tunable: name, links, tries, share marks, rollover time, practice pool, storage key, analytics flag, About copy, learn-more links |
| `favicon.svg` | The raccoon mark; lightens itself in dark mode |
| `puzzles/index.json` | `[{"n":1,"date":"2026-10-18"}, ...]` |
| `puzzles/<date>.json` | One daily puzzle (format below) |
| `puzzles/practice/index.json` | `{"count": N}` |
| `puzzles/practice/NNNN.json` | One practice puzzle: same format, `id` in place of `n` and `date` |

Routes: `#/today`, `#/archive`, `#/archive/2026-10-18`, `#/practice` (picks a
random one and moves to it), `#/practice/0012`, `#/how`, `#/about`.

## Make puzzles

From `problems/games`:

```sh
uv run --with numpy python -m scrabble.puzzles --days 14 --start 2026-10-18 --out scrabble/site/puzzles
```

The selection rules (bag range, value gap, word length, common-word cutoff,
theme thresholds, seed ranges) are `CONFIG` at the top of `puzzles.py`;
`--config rules.json` overrides any of them for a run.

Same arguments, same files. The first run downloads a pinned list of common
words (`lexica/en_50k.txt`, checked by sha256). It's used so the best play is
a word people know.

A year of puzzles on the EC2 runner (from the repo's `problems/games`,
`--jobs` set to the core count; the files don't depend on it):

`lexica/NWL23.klv2` is not in git, so copy it to the runner first:

```sh
scp scrabble/lexica/NWL23.klv2 <runner>:<repo>/problems/games/scrabble/lexica/
# on the runner, from problems/games:
uv run --with numpy python -m scrabble.puzzles --days 365 --start 2026-10-18 --out /tmp/puzzles --jobs $(nproc)
# then on the laptop:
rsync -av <runner>:/tmp/puzzles/ scrabble/site/puzzles/
```

The practice pool uses its own seeds (from 1,300,000) and skips any position
that is already a daily in `--out`. A small test pool:

```sh
uv run --with numpy python -m scrabble.puzzles --practice 20 --out scrabble/site/puzzles
```

The full pool on the runner. Start from the published files so existing ids
stay and dailies are skipped; `--practice` adds that many more:

```sh
rsync -av scrabble/site/puzzles/ <runner>:/tmp/puzzles/
# on the runner, from problems/games:
uv run --with numpy python -m scrabble.puzzles --practice 980 --out /tmp/puzzles --jobs $(nproc)
# back on the laptop:
rsync -av <runner>:/tmp/puzzles/practice/ scrabble/site/puzzles/practice/
```

A longer run picks puzzles from a larger pool, so its first days can differ
from a shorter run's. Deploy one set before launch and keep it.

### Puzzle format

```json
{
  "n": 3, "date": "2026-10-20", "seed": 1100003, "turn": 14,
  "bag": 32, "score": [182, 197], "rack": "ACGLRSX",
  "unseen": "AABDEE...", "board": ["...............", "..."],
  "last": [[7, 7], [7, 8]], "theme": "dump",
  "plays": [["13G", "XI", 34, "ACGLRS", 35.6], ...]
}
```

- `score` is [you, them]. `board` has 15 rows; `.` is empty and a lowercase
  letter is a blank.
- `last` lists the squares of the opponent's last play.
- `plays` holds every legal placement, best first:
  `[where, word, points, kept tiles, value]`.
  - `where` is `8H` (row 8, column H, across) or `H8` (down).
  - A lowercase letter in `word` is a blank. `?` in the kept tiles is a blank.
  - The tiles placed are the rack minus the kept tiles. The browser finds
    their squares by walking the word from `where` over the empty squares.
  - `value` is points plus the learned worth of the kept tiles
    (`leaves.equity`).

## Run locally

```sh
cd scrabble/site && python -m http.server 8000
# http://localhost:8000
# http://localhost:8000/?today=2026-10-31   pretend it is another day (localhost only)
```

## Deploy to Vercel

```sh
npm i -g vercel          # once
cd scrabble/site
vercel login             # once
vercel                   # preview deployment
vercel --prod            # production
vercel domains add <your-domain>   # optional
```

Set `SITE_URL` in `config.js` to the production URL first. The share text
uses it, and analytics only load on that host.

## Releasing updates

Players' progress lives in their browser, keyed by puzzle date (dailies) or
practice id. So:

- **Published puzzle files are immutable.** Never edit, renumber or delete a
  `puzzles/<date>.json` or `puzzles/practice/NNNN.json` once it is live.
  `puzzles.py` refuses to change an existing file unless you pass `--force`.
- **Add days after the last one.** The generator prints the last seed used;
  pass the next day and the next seed:
  `python -m scrabble.puzzles --days 30 --start <day after the last> --first <last seed + 1>`.
  `index.json` is rebuilt from every daily file, old and new.
- **Practice only grows.** `--practice N` appends N puzzles after the existing
  ids, from seeds after theirs, skipping any position already used.
- **Never change `STORAGE_KEY`** in `config.js`. If the saved shape must
  change, bump `SCHEMA` in `app.js` and add a step to `migrate()`; it keeps
  fields it doesn't know. Old keys listed in `LEGACY_STORAGE_KEYS` are merged
  in once and left alone.
- If a saved day's plays no longer match its file, the site still counts the
  day in stats and streak and says the puzzle was updated.

## Site statistics

With `ANALYTICS: true` in `config.js`, the page loads Vercel Web Analytics
(`/_vercel/insights/script.js`) and Speed Insights
(`/_vercel/speed-insights/script.js`), but only on `SITE_URL`'s host, never
on localhost or preview URLs. Both are cookieless and keep no personal data.
Nothing about guesses is sent: `reportResult()` in `app.js` is a no-op.

To turn them on:

1. In the Vercel dashboard, open the project, then **Analytics** and select **Enable**.
2. Open **Speed Insights** and select **Enable**.
3. Redeploy (`vercel --prod`). The two script paths exist only after enabling.

To turn them off, set `ANALYTICS: false`.
