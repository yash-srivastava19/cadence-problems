"""B1/D1: where does klve lose against the sim opponent?

    python -m scrabble.blindspots score rounds/macondo/duel_klve_vs_sim_750000_log.jsonl
    python -m scrabble.blindspots report rounds/blindspots/scored_750000.jsonl

Every move klve made in a logged duel is put back in front of a reference
stronger than the opponent: Macondo's sim at 3 plies over the top 20 plays
plus klve's own move, every candidate on the same iterations, for a fixed
time. The loss of a move is the best candidate's equity (and win chance)
minus klve's.
"""

import argparse
import json
import os
import queue
import re
import subprocess
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from scrabble.macondo import BIN

HERE = Path(__file__).parent
OUT = HERE / "rounds" / "blindspots"
PLAYS, PLIES, SECONDS = 20, 3, 15
ROW = re.compile(r"^\s*(\(exch [^)]*\)|\S+ \S+)\s+(\S*)\s+(-?\d+)\s+([\d.]+)±[\d.]+\s+(-?[\d.]+)±")


def same_move(shown: str, ours: str) -> bool:
    """Macondo shows tiles already on the board in brackets; we write dots."""
    if shown.startswith("(exch"):
        return ours.startswith("exch") and sorted(shown[6:-1]) == sorted(ours[5:])
    coord, word = shown.split()
    return f"{coord} {re.sub(r'\(([^)]*)\)', lambda m: '.' * len(m[1]), word)}" == ours


class Reference:
    def __init__(self):
        self.p = subprocess.Popen([str(BIN)], cwd=BIN.parent, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.lines: queue.Queue[str] = queue.Queue()
        threading.Thread(target=lambda: [self.lines.put(x) for x in self.p.stdout], daemon=True).start()
        self.send("set lexicon ENABLE english")

    def send(self, line: str) -> None:
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def table(self, cgp: str, move: str) -> list[tuple[str, int, float, float]]:
        """The sim's ranking, or [] if Macondo printed none (one legal play, a bad add)."""
        while not self.lines.empty():
            self.lines.get_nowait()
        self.send(f"load cgp {cgp}")
        self.send(f"gen {PLAYS}")
        if move != "pass":
            self.send(f"add {move}")
        self.send(f"sim -plies {PLIES} -threads 1")
        time.sleep(SECONDS)
        self.send("sim stop")
        rows, started, deadline = [], False, time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                line = re.sub(r"\x1b\[[0-9;]*m", "", self.lines.get(timeout=1))
            except queue.Empty:
                continue
            if line.startswith("Play") and "Win%" in line:
                started, rows = True, []
            elif started and line.startswith("Iterations"):
                time.sleep(1)  # the sim winds down after printing; a load sent now is dropped
                return rows
            elif started and (m := ROW.match(line)):
                rows.append((m[1].strip(), int(m[3]), float(m[4]), float(m[5])))
        return []


    def pegs(self, cgp: str, seconds: int) -> dict[str, float]:
        """Win share of every play the pre-endgame solver finished, by its written form."""
        while not self.lines.empty():
            self.lines.get_nowait()
        self.send(f"load cgp {cgp}")
        self.send(f"peg -threads 1 -endgameplies 4 -maxtime {seconds}")
        rows, started, deadline = {}, False, time.monotonic() + seconds + 60
        while time.monotonic() < deadline:
            try:
                line = re.sub(r"\x1b\[[0-9;]*m", "", self.lines.get(timeout=1))
            except queue.Empty:
                continue
            if line.startswith("Play") and "%Win" in line:
                started, rows = True, {}
            elif started and "marks plays cut off" in line:
                time.sleep(1)
                return rows
            elif started and (m := PEG.match(line)) and "❌" not in line and m[3] != "NaN":
                rows[m[1].strip()] = float(m[3])
        return rows


PEG = re.compile(r"^\s*(\(exch [^)]*\)|\S+ \S+)\s+([\d.]+)\s+([\d.]+|NaN)")
_ref: Reference | None = None


def _init() -> None:
    global _ref
    _ref = Reference()


def score_one(job: dict) -> dict:
    rows = _ref.table(job["cgp"], job["move"])
    best = rows[0] if rows else None
    mine = next((r for r in rows if same_move(r[0], job["move"])), None)
    out = {k: job[k] for k in ("seed", "seat", "turn", "bag", "move", "points", "lead", "result")}
    out["best"] = best[0] if best else None
    out["found"] = mine is not None
    if mine is not None:
        out["equity_loss"] = round(max(r[3] for r in rows) - mine[3], 2)
        out["win_loss"] = round(max(r[2] for r in rows) - mine[2], 2)
    return out


def score(path: Path) -> None:
    jobs = []
    for line in path.read_text().splitlines():
        game = json.loads(line)
        for turn, h in enumerate(game["history"]):
            if h["ours"] and h["bag"] > 0:
                jobs.append({"seed": game["seed"], "seat": game["seat"], "turn": turn, "bag": h["bag"],
                             "move": h["move"], "points": h["points"], "cgp": h["cgp"],
                             "lead": h["scores"][0] - h["scores"][1], "result": game["points"]})
    OUT.mkdir(parents=True, exist_ok=True)
    saved = OUT / f"scored_{path.stem.split('_')[-2]}.jsonl"
    done = set()
    if saved.exists():
        done = {(r["seed"], r["seat"], r["turn"]) for r in map(json.loads, saved.read_text().splitlines())}
    jobs = [j for j in jobs if (j["seed"], j["seat"], j["turn"]) not in done]
    print(f"{len(jobs)} positions, about {len(jobs) * (SECONDS + 1) / os.cpu_count() / 60:.0f} min", flush=True)
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init) as pool, saved.open("a") as out:
        for r in pool.map(score_one, jobs, chunksize=4):
            out.write(json.dumps(r) + "\n")
            out.flush()


def judged(job: dict) -> dict:
    """I1: at one tile in the bag, which of klve's, the fast solver's and the sim's moves wins most?"""
    from scrabble.macondo import Shell
    shell = Shell()
    fast, simmed = shell.pegged(job["cgp"], 8 * job["bag"]), shell.simmed(job["cgp"])
    shell.p.stdin.close()
    table = _ref.pegs(job["cgp"], 60 * job["bag"])

    def share(move: str, written: bool) -> float | None:
        return next((v for k, v in table.items() if (same_move(k, move) if written else k == move)), None)

    return {"seed": job["seed"], "seat": job["seat"], "klve": job["move"], "fast": fast, "sim": simmed,
            "best": max(table.values(), default=None), "klve_win": share(job["move"], True),
            "fast_win": share(fast, False), "sim_win": share(simmed, False), "plays": len(table)}


def isolate(path: Path) -> None:
    bag = int(os.environ.get("BAG", 1))
    jobs = [{"seed": g["seed"], "seat": g["seat"], "cgp": h["cgp"], "move": h["move"], "bag": bag}
            for g in map(json.loads, path.read_text().splitlines())
            for h in g["history"] if h["ours"] and h["bag"] == bag]
    saved = OUT / f"isolate_bag{bag}.jsonl"
    print(f"{len(jobs)} positions with {bag} in the bag", flush=True)
    with ProcessPoolExecutor(int(os.environ.get("WORKERS", 3)), initializer=_init) as pool, saved.open("w") as out:
        for r in pool.map(judged, jobs):
            out.write(json.dumps(r) + "\n")
            out.flush()


def phase(bag: int) -> str:
    return "50+" if bag >= 50 else "8-49" if bag >= 8 else "1-7"


def kind(r: dict) -> str:
    if r["move"].startswith("exch"):
        return "exchange"
    if r["move"] == "pass":
        return "pass"
    return "bingo" if sum(ch != "." for ch in r["move"].split()[1]) == 7 else "play"


def report(path: Path) -> None:
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    games = len({(r["seed"], r["seat"]) for r in rows})
    found = [r for r in rows if r["found"]]
    print(f"{len(rows)} moves from {games} games; klve's move found in the table for {len(found)}")
    print(f"klve's move had the best win chance {sum(r['win_loss'] <= 0 for r in found) / len(found):.0%}")

    def line(name, group):
        if not group:
            return
        eq = sum(r["equity_loss"] for r in group)
        wl = sum(r["win_loss"] for r in group)
        print(f"  {name:<22} {len(group):>5} moves   {eq / games:6.2f} pts/game   "
              f"{wl / games:6.2f} win%/game   {eq / len(group):5.2f} pts/move")

    print("by bag:")
    for p in ("50+", "8-49", "1-7"):
        line(p, [r for r in found if phase(r["bag"]) == p])
    print("by what klve played:")
    for k in ("play", "bingo", "exchange", "pass"):
        line(k, [r for r in found if kind(r) == k])
    print("by what the reference preferred:")
    line("exchange", [r for r in found if r["best"].startswith("(exch")])
    print("by lead before the move:")
    for name, lo, hi in (("behind 40+", -999, -40), ("close", -39, 39), ("ahead 40+", 40, 999)):
        line(name, [r for r in found if lo <= r["lead"] <= hi])
    line("all", found)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["score", "report", "isolate"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    {"score": score, "report": report, "isolate": isolate}[args.what](args.path)


if __name__ == "__main__":
    main()
