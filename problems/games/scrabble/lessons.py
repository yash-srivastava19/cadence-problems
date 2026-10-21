"""Lessons: where the champion went wrong, according to the teacher.

    python -m scrabble.lessons --round 2 --bags 12      # from problems/games

The champion plays the pool on bags no run scores on. On each of its turns
the teacher simulates its choice beside the best alternatives, in the same
invented worlds. A lesson is a turn where another move did clearly better:
the gap is larger than twice its error.

Writes rounds/round_<k>/lessons.json and the "Lessons" section of IMPROVE.md,
which the next run sends to the model. It changes between runs, never during.
"""

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from kit.player import Remote
from scrabble import simulate
from scrabble.env import as_dict
from scrabble.game import Game, Move
from scrabble.ruleset import Ruleset, load

HERE = Path(__file__).parent
FIRST = 300_000  # bags no training run, gate, check or yardstick uses
SHOWN = 12
MARK = "## Lessons from the teacher"

_rs: Ruleset | None = None


def _init() -> None:
    global _rs
    _rs = load(HERE / "english.json")


def phase(g: Game) -> str:
    if g.turn < 4:
        return "opening"
    if not g.bag:
        return "endgame"
    return "pre-endgame" if len(g.bag) <= 7 else "middlegame"


def picture(g: Game) -> str:
    cols = "ABCDEFGHIJKLMNO"[: g.rs.size]
    rows = ["    " + " ".join(cols)]
    for r, row in enumerate(g.grid):
        cells = ["." if c is None else (c[0].lower() if c[1] else c[0]) for c in row]
        rows.append(f"{r + 1:>3} " + " ".join(cells))
    return "\n".join(rows)


def describe(m: Move) -> dict:
    return {"move": m.label(), "points": m.score, "keeps": "".join(m.leave)}


def play(champion: Path, opponent: Path, seed: int, seat: int) -> tuple[list, int]:
    assert _rs is not None
    g = Game(_rs, seed)
    me, them = Remote(champion, "champion"), Remote(opponent, opponent.stem)
    found: list[dict] = []
    turns = 0
    try:
        while not g.over:
            moves = g.legal()
            offered = [as_dict(m) for m in moves]
            if g.to_move != seat:
                g.apply(moves[them.choose(g.view(), offered)])
                continue
            chosen = me.choose(g.view(), offered)
            turns += 1
            if len(moves) > 1:
                samples = simulate.SAMPLES if g.bag else 1
                picks = simulate.shortlist(g, moves, also=(chosen,))
                out = simulate.simulate(g, moves, picks, seed * 1000 + g.turn, samples)
                best = max(out, key=lambda i: (simulate.mean(out[i]), -i))
                gain, err = simulate.gap(out[best], out[chosen])
                if best != chosen and gain >= 3 and gain > 2 * err:
                    found.append(
                        {
                            "seed": seed,
                            "turn": g.turn,
                            "phase": phase(g),
                            "against": opponent.stem,
                            "rack": "".join(g.racks[seat]),
                            "bag": len(g.bag),
                            "score": [g.scores[seat], g.scores[1 - seat]],
                            "board": picture(g),
                            "played": describe(moves[chosen]),
                            "better": describe(moves[best]),
                            "gain": round(gain, 1),
                            "error": round(err, 1),
                            "kind": moves[best].kind,
                        }
                    )
            g.apply(moves[chosen])
    finally:
        me.close()
        them.close()
    return found, turns


def section(k: int, lessons: list[dict], turns: int) -> str:
    top = sorted(lessons, key=lambda x: -x["gain"])[:SHOWN]
    by_phase = Counter(x["phase"] for x in lessons)
    lost = sum(x["gain"] for x in lessons)
    fewer = sum(x["better"]["points"] < x["played"]["points"] for x in lessons)
    lines = [
        f"{MARK} (round {k})",
        "",
        "A simulation looked at the champion's turns on games you are not scored "
        "on. For each turn it played the champion's move and the best "
        "alternatives into the same invented futures (random draws, the "
        "opponent replying), and compared how they came out. These are the turns "
        "where another move did clearly better.",
        "",
        f"- {len(lessons)} clear mistakes in {turns} turns, "
        f"about {lost / max(1, len(lessons)):.0f} points each.",
        f"- By phase: {', '.join(f'{p} {n}' for p, n in by_phase.most_common())}.",
        f"- In {fewer} of them the better move scored fewer points now: "
        "the gain came from what it kept or what it left the opponent.",
        "",
        "The biggest ones:",
    ]
    for x in top:
        lines += [
            "",
            f"**{x['phase']}, bag {x['bag']}, score {x['score'][0]}-"
            f"{x['score'][1]}, rack {x['rack']}**: played "
            f"`{x['played']['move']}` ({x['played']['points']} pts, kept "
            f"{x['played']['keeps'] or '-'}); better `{x['better']['move']}` "
            f"({x['better']['points']} pts, kept {x['better']['keeps'] or '-'}), "
            f"by {x['gain']} ± {x['error']}.",
            "",
            "```",
            x["board"],
            "```",
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--bags", type=int, default=12)
    args = parser.parse_args()

    champions = sorted(
        (HERE / "opponents").glob("champion_*.py"),
        key=lambda p: int(p.stem.split("_")[1]),
    )
    champion = champions[-1]
    pool = sorted((HERE / "opponents").glob("*.py"))
    jobs = [
        (champion, o, FIRST + 100 * args.round + b, seat)
        for o in pool
        for b in range(args.bags)
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init) as workers:
        results = list(workers.map(play, *zip(*jobs, strict=True)))
    found = [x for lessons, _ in results for x in lessons]
    turns = sum(n for _, n in results)

    out = HERE / "rounds" / f"round_{args.round}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "lessons.json").write_text(json.dumps(found, indent=1))
    text = section(args.round, found, turns)
    (out / "lessons.md").write_text(text)

    brief = HERE / "IMPROVE.md"
    current = brief.read_text()
    current = current.split(MARK)[0].rstrip() + "\n\n"
    brief.write_text(current + text)
    print(text)


if __name__ == "__main__":
    main()
