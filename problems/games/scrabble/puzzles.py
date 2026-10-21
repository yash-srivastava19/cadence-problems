"""Puzzles for the website: one real mid-game position a day, plus a practice pool.

    python -m scrabble.puzzles --days 14 --start 2026-10-18 --out scrabble/site/puzzles
    python -m scrabble.puzzles --practice 20 --out scrabble/site/puzzles   # appends

Published files are immutable (saved progress points at them by date or
practice id): a run that would change one stops unless --force is given.

Games are klv against klv from fresh seeds. A position becomes a puzzle when
the highest-scoring play is not the best one: points plus the value of the
tiles kept (leaves.equity) says something else, by a margin worth learning.
Each file holds every legal placement, so the browser can check a play
without a word list. Same arguments, same files.

The selection rules are CONFIG below; --config FILE.json overrides any of them.
"""

import argparse
import datetime
import json
import multiprocessing
from pathlib import Path

from scrabble import leaves, ruleset
from scrabble.game import Game
from scrabble.ruleset import BLANK

HERE = Path(__file__).parent

CONFIG = {
    "first_seed": 1_100_000,           # daily games start here (bags nothing else uses)
    "practice_first_seed": 1_300_000,  # practice games start here, apart from the dailies
    "bag_min": 20,                     # mid-game only: tiles in the bag
    "bag_max": 70,
    "bag_preferred": 45,               # among a game's candidates, prefer this bag size
    "max_blanks": 1,                   # racks with more blanks make files too big
    "min_gap": 5.0,                    # value the top scorer gives up against the best play
    "gap_cap": 20.0,                   # bigger gaps are no more instructive than this
    "min_clear": 1.0,                  # the best play beats the runner-up by at least this
    "min_value": 12.0,                 # the best play is worth at least this
    "max_plays": 4000,                 # skip positions with more legal plays (file size)
    "max_word_len": 8,                 # the best play's main word is at most this long
    "common_top": 50_000,              # ... and among this many most frequent words
    "keep_min_leave": 6.0,             # theme "keep": the best play keeps tiles worth this
    "dump_min_loss": 4.0,              # theme "dump": the top scorer keeps tiles worth -this or less
    "pool_factor": 2.5,                # daily candidates per day, to vary themes
}

# The most frequent words in film subtitles (OpenSubtitles 2018), pinned by
# hash: a word on it is one a player could plausibly know.
COMMON = HERE / "lexica" / "en_50k.txt"
COMMON_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_50k.txt"
COMMON_SHA = "5351ff405b1126ef555791dd4d9798a48e3e9a501a9fc481a9da957752cfb458"
_common: frozenset[str] | None = None


def _rack(tiles) -> str:
    return "".join(sorted(tiles, key=lambda t: (t != BLANK, t)))


def _theme(best, top, best_leave: float, top_leave: float) -> str:
    """What the lesson is about, by whichever side of the trade is bigger."""
    if len(best.tiles) == 7:
        return "bingo"
    gain, loss = best_leave - max(top_leave, 0), -min(top_leave, 0)
    if loss >= CONFIG["dump_min_loss"] and loss >= gain:
        return "dump"
    if best_leave >= CONFIG["keep_min_leave"]:
        return "keep"
    return "balance"


def _familiar(m) -> bool:
    """A stand-in for 'a player could find it': the main word is a common
    one and not long. Cross words are not checked."""
    global _common
    if _common is None:
        if not COMMON.exists():
            ruleset._fetch(COMMON, COMMON_URL, COMMON_SHA)
        lines = [line for line in COMMON.read_text().splitlines() if line][: CONFIG["common_top"]]
        _common = frozenset(line.split()[0].upper() for line in lines)
    return m.word.upper() in _common and len(m.word) <= CONFIG["max_word_len"]


def candidate(g: Game, moves):
    """The position as a puzzle, or None if it does not teach anything."""
    if not CONFIG["bag_min"] <= len(g.bag) <= CONFIG["bag_max"]:
        return None
    rack = g.racks[g.to_move]
    if rack.count(BLANK) > CONFIG["max_blanks"]:
        return None
    eq = [leaves.equity(g, m) for m in moves]
    order = sorted(range(len(moves)), key=lambda i: (-eq[i], -moves[i].score, moves[i].where, moves[i].word))
    best = moves[order[0]]
    if best.kind != "play":
        return None  # an exchange is right; the site only takes placements
    plays = [i for i in order if moves[i].kind == "play"]
    if (len(plays) > CONFIG["max_plays"] or eq[plays[0]] < CONFIG["min_value"]
            or eq[plays[0]] - eq[plays[1]] < CONFIG["min_clear"]):
        return None
    top_i = max(plays, key=lambda i: (moves[i].score, eq[i]))
    top = moves[top_i]
    bingo = len(best.tiles) == 7
    if not bingo and (top.score <= best.score or eq[plays[0]] - eq[top_i] < CONFIG["min_gap"]):
        return None
    if not _familiar(best):
        return None
    best_leave, top_leave = leaves.value(best.leave), leaves.value(top.leave)
    return {
        "theme": _theme(best, top, best_leave, top_leave),
        "gap": eq[plays[0]] - eq[top_i],
        "plays": [(moves[i], eq[i]) for i in plays],
    }


def _grid(g: Game) -> list[str]:
    return ["".join("." if c is None else (c[0].lower() if c[1] else c[0]) for c in row) for row in g.grid]


def _unseen(g: Game) -> str:
    view = g.view()
    return _rack(t for t, k in view["unseen"].items() for _ in range(k))


def puzzle(g: Game, found: dict, last, seed: int) -> dict:
    p = g.to_move
    return {
        "seed": seed,
        "turn": g.turn,
        "bag": len(g.bag),
        "score": [g.scores[p], g.scores[1 - p]],
        "rack": _rack(g.racks[p]),
        "unseen": _unseen(g),
        "board": _grid(g),
        "last": [[r, c] for r, c, _, _ in last.tiles] if last and last.kind == "play" else [],
        "theme": found["theme"],
        "plays": [[m.where, m.word, m.score, _rack(m.leave), round(v, 1)] for m, v in found["plays"]],
    }


def from_game(rs, seed: int):
    """The most instructive puzzle in one klv self-play game, or None."""
    g = Game(rs, seed)
    last, picks = None, []
    while not g.over:
        moves = g.legal()
        found = candidate(g, moves)
        if found:
            picks.append((found["gap"], -abs(len(g.bag) - CONFIG["bag_preferred"]), puzzle(g, found, last, seed)))
        last = moves[leaves.klv(g, moves)]
        g.apply(last)
    if not picks:
        return None
    # A moderate gap reads best: big enough to matter, small enough to be subtle.
    picks.sort(key=lambda x: (-min(x[0], CONFIG["gap_cap"]), -x[1]))
    return picks[0][2]


def pick(pool: list[dict], days: int) -> list[dict]:
    """Vary the themes: no theme two days running, at most one bingo a week."""
    out, left = [], list(pool)
    for _ in range(days):
        prev = out[-1]["theme"] if out else None
        week = [x["theme"] for x in out[-6:]] if out else ["bingo"]  # open with a plain one

        def ok(x, prev=prev, week=week):
            return x["theme"] != prev and not (x["theme"] == "bingo" and "bingo" in week)

        choice = next((x for x in left if ok(x)), None) or next(
            (x for x in left if x["theme"] != "bingo" or "bingo" not in week), left[0])
        left.remove(choice)
        out.append(choice)
    return out


_rs = None


def _init(config: dict) -> None:
    CONFIG.update(config)


def _one(seed: int):
    global _rs
    if _rs is None:
        _rs = ruleset.load(HERE / "english.json")
        leaves.table()
    return from_game(_rs, seed)


def _games(first: int, jobs: int):
    """Puzzles from seeds first, first + 1, ... in seed order, on `jobs` processes."""
    if jobs <= 1:
        seed = first
        while True:
            yield seed, _one(seed)
            seed += 1
    with multiprocessing.Pool(jobs, initializer=_init, initargs=(dict(CONFIG),)) as workers:
        seed = first
        while True:
            batch = list(range(seed, seed + 4 * jobs))
            yield from zip(batch, workers.map(_one, batch))
            seed += len(batch)


def _collect(first: int, want: int, jobs: int, skip=frozenset()) -> list[dict]:
    pool = []
    for seed, found in _games(first, jobs):
        if len(pool) >= want:
            break
        if found and (tuple(found["board"]), found["rack"]) not in skip:
            pool.append(found)
            print(f"seed {seed}: {found['theme']}, bag {found['bag']}, {len(found['plays'])} plays", flush=True)
    return pool


def _dump(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, separators=(",", ":")) + "\n")


def _existing(out: Path, pattern: str) -> dict[str, dict]:
    return {f.name: json.loads(f.read_text()) for f in sorted(out.glob(pattern))}


def _key(doc: dict) -> tuple:
    return tuple(doc["board"]), doc["rack"]


def _publish(files: dict[Path, dict], force: bool) -> None:
    """Published puzzle files are immutable: players' saved progress points at
    them. Writing the same content again is fine; changing one needs --force."""
    clash = [p for p, doc in files.items()
             if p.exists() and p.read_text() != json.dumps(doc, separators=(",", ":")) + "\n"]
    if clash and not force:
        names = ", ".join(p.name for p in clash[:5]) + (" ..." if len(clash) > 5 else "")
        raise SystemExit(f"refusing to change {len(clash)} published file(s): {names}. "
                         "Use another --start/--first, or --force if you really mean it.")
    for p, doc in files.items():
        _dump(p, doc)


def write(days: int, start: datetime.date, out: Path, jobs: int = 1, force: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    old = _existing(out, "????-??-??.json")
    if old:
        top = max(d["seed"] for d in old.values())
        print(f"{len(old)} dailies exist (seeds up to {top}); to add days after them use "
              f"--start <next date> --first {top + 1}", flush=True)
    span = {(start + datetime.timedelta(days=k)).isoformat() for k in range(days)}
    skip = frozenset(_key(d) for d in old.values() if d["date"] not in span)  # rerunning a range is a no-op
    pool = _collect(CONFIG["first_seed"], max(days + 2, int(days * CONFIG["pool_factor"])), jobs, skip)
    dates = {(start + datetime.timedelta(days=k)).isoformat(): x for k, x in enumerate(pick(pool, days))}
    every = sorted(set(dates) | {d["date"] for d in old.values()})
    first = datetime.date.fromisoformat(every[0])
    number = {d: (datetime.date.fromisoformat(d) - first).days + 1 for d in every}
    files = {out / f"{d}.json": {"n": number[d], "date": d, **x} for d, x in dates.items()}
    _publish(files, force)
    for path, doc in files.items():
        print(f"#{doc['n']} {doc['date']} {doc['theme']:8} {doc['plays'][0][1]:>9} {path.stat().st_size // 1024} KB")
    _dump(out / "index.json", [{"n": number[d], "date": d} for d in every])


def write_practice(count: int, out: Path, jobs: int = 1, force: bool = False) -> None:
    """Add `count` puzzles to the practice pool. Existing ids never change:
    new ones are numbered after them, from seeds after theirs, and no
    position repeats a daily or an existing practice puzzle."""
    where = out / "practice"
    where.mkdir(parents=True, exist_ok=True)
    old = _existing(where, "[0-9][0-9][0-9][0-9].json")
    dailies = _existing(out, "????-??-??.json")
    skip = frozenset(_key(d) for d in [*old.values(), *dailies.values()])
    first = max([CONFIG["practice_first_seed"]] + [d["seed"] + 1 for d in old.values()])
    pool = _collect(first, count, jobs, skip)
    n = len(old)
    files = {where / f"{n + k:04d}.json": {"id": n + k, **x} for k, x in enumerate(pool, 1)}
    _publish(files, force)
    _dump(where / "index.json", {"count": n + len(pool)})
    print(f"added {len(pool)} practice puzzles to {where}: now {n + len(pool)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=14, help="daily puzzles to write (0 for none)")
    ap.add_argument("--start", default="2026-10-18", help="date of puzzle #1, YYYY-MM-DD")
    ap.add_argument("--practice", type=int, default=0, help="add this many practice puzzles (appended) instead of dailies")
    ap.add_argument("--out", type=Path, default=HERE / "site" / "puzzles")
    ap.add_argument("--config", type=Path, help="JSON file overriding CONFIG keys")
    ap.add_argument("--first", type=int, help="first game seed (overrides the config for this run)")
    ap.add_argument("--jobs", type=int, default=1, help="processes; the files do not depend on it")
    ap.add_argument("--force", action="store_true", help="allow changing already published puzzle files")
    a = ap.parse_args()
    if a.config:
        extra = json.loads(a.config.read_text())
        unknown = set(extra) - set(CONFIG)
        if unknown:
            ap.error(f"unknown config keys: {', '.join(sorted(unknown))}")
        CONFIG.update(extra)
    if a.practice:
        if a.first is not None:
            CONFIG["practice_first_seed"] = a.first
        write_practice(a.practice, a.out, a.jobs, a.force)
    else:
        if a.first is not None:
            CONFIG["first_seed"] = a.first
        write(a.days, datetime.date.fromisoformat(a.start), a.out, a.jobs, a.force)


if __name__ == "__main__":
    main()
