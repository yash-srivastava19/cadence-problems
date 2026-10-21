"""Close a self-play round: gate the run's best player, measure, promote.

    cadence run . --config scrabble/.cadence > run.json
    python -m scrabble.round run.json

1. Gate: the candidate plays the current champion on bags no run has seen.
   It must win at least GATE of those games to become the next champion.
2. Yardstick: the candidate and the champion both play the leave bot, on the
   same fixed bags every round. Nothing trains against it, so a rising line
   here is real strength, not tricks against our own pool.
3. Report: rounds/round_<k>/report.md, with the code diff beside it.
4. Promote: if it passed, it joins opponents/ and becomes the next start.
"""

import difflib
import json
import math
import sys
from pathlib import Path

from scrabble.score import HERE, evaluate

GATE, GATE_BAGS, YARD_BAGS = 0.55, 200, 100
YARDSTICK = HERE / "yardsticks" / "leave.py"
YARD_SEEDS = list(range(900_000, 900_000 + YARD_BAGS))


def margin(rate: float, games: int) -> float:
    return 1.96 * math.sqrt(rate * (1 - rate) / games)


def main(run_file: str) -> None:
    run = json.loads(Path(run_file).read_text())
    champions = sorted(
        (HERE / "opponents").glob("champion_*.py"),
        key=lambda p: int(p.stem.split("_")[1]),
    )
    champion = champions[-1]
    k = int(Path(run_file).stem.split("_")[1])  # run_<k>.json
    out = HERE / "rounds" / f"round_{k}"
    out.mkdir(parents=True, exist_ok=True)
    candidate = out / "candidate.py"
    candidate.write_text(run["program"])

    gate_seeds = list(range(500_000 + 1000 * k, 500_000 + 1000 * k + GATE_BAGS))
    gate = evaluate(candidate, [champion], gate_seeds)
    yard_new = evaluate(candidate, [YARDSTICK], YARD_SEEDS)
    yard_old = evaluate(champion, [YARDSTICK], YARD_SEEDS)
    passed = gate["win_rate"] >= GATE and gate["forfeits"] == 0

    diff = difflib.unified_diff(
        champion.read_text().splitlines(),
        run["program"].splitlines(),
        champion.name,
        "candidate.py",
        lineterm="",
    )
    (out / "change.diff").write_text("\n".join(diff) + "\n")

    games = 2 * GATE_BAGS
    lines = [
        f"# Round {k}",
        "",
        f"Run `{run.get('run_id')}`: {run.get('trials')} trials, "
        f"best scored {run['metrics']}.",
        "",
        "| | win rate | ±95% | spread | forfeits | ms per move |",
        "|---|---|---|---|---|---|",
        f"| **gate**: candidate vs {champion.stem}, {games} fresh games "
        f"| {gate['win_rate']:.3f} | {margin(gate['win_rate'], games):.3f} "
        f"| {gate['spread']:+.1f} | {gate['forfeits']:.0f} ({gate['timeouts']:.0f} timed out) "
        f"| {gate['ms_per_move']:.0f} |",
        f"| yardstick: candidate vs leave, {2 * YARD_BAGS} games "
        f"| {yard_new['win_rate']:.3f} "
        f"| {margin(yard_new['win_rate'], 2 * YARD_BAGS):.3f} "
        f"| {yard_new['spread']:+.1f} | {yard_new['forfeits']:.0f} ({yard_new['timeouts']:.0f} timed out) "
        f"| {yard_new['ms_per_move']:.0f} |",
        f"| yardstick: {champion.stem} vs leave, same games "
        f"| {yard_old['win_rate']:.3f} "
        f"| {margin(yard_old['win_rate'], 2 * YARD_BAGS):.3f} "
        f"| {yard_old['spread']:+.1f} | {yard_old['forfeits']:.0f} ({yard_old['timeouts']:.0f} timed out) "
        f"| {yard_old['ms_per_move']:.0f} |",
        "",
        f"**{'PROMOTED' if passed else 'NOT PROMOTED'}**: the gate needs "
        f"{GATE:.0%} with no forfeits. The code change is in change.diff.",
    ]
    if passed:
        nxt = HERE / "opponents" / f"champion_{len(champions) + 1}.py"
        nxt.write_text(
            f'"""Champion {len(champions) + 1}: run {run.get("run_id")}, '
            f'promoted in round {k}."""\n\n' + run["program"]
        )
        (HERE / "player.py").write_text(run["program"])
        lines.append(f"\n{nxt.name} joins the pool and is the next start.")
    report = "\n".join(lines) + "\n"
    (out / "report.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main(sys.argv[1])
