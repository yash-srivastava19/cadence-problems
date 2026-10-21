"""Search vs recall at equal cost. See PREREG.md; this only carries it out.

    python drive.py                 # every block in PREREG order
    python drive.py --smoke MODEL   # one 1-trial run, to check the plumbing

Each arm runs in its own copy of the problem, so the arms share nothing but
the start program. Results append to results/pairs.jsonl as they finish.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "results"
SVR = Path(os.environ.get("SVR", Path.home() / "svr"))
WORK = Path(os.environ.get("WORK", Path.home() / "svr-work"))
CADENCE = ["uv", "run", "--project", str(Path.home() / "cadence"), "cadence"]
N = 4
SUFFIX = "r3"
HINT = "improve the score; changing what the code returns is allowed"
MODELS = [
    "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.5-flash",
    "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite", "gemini-2.5-flash-lite",
]

PROBLEMS = {
    "bin-packing": {"root": "bin-packing/run", "program": "heuristic.py",
                    "metric": "excess_valid", "better": -1},
    "circle-packing": {"root": "circle-packing", "program": "pack.py",
                       "metric": "sum_radii", "better": +1},
}
SUSPECT = re.compile(r"\bprint\s*\(|os\._exit|sys\.exit|atexit|sys\.modules|__import__|open\s*\(")


def manifest(problem: str, model: str, trials: int, name: str) -> str:
    """The shipped manifest with the budget, model and experiment name swapped."""
    text = (SVR / PROBLEMS[problem]["root"] / ".cadence").read_text()
    text = re.sub(r"(?m)^experiment:.*$", f"experiment: {name}", text)
    text = re.sub(r"(?m)^(\s*trials:)\s*\d+", rf"\1 {trials}", text)
    text = re.sub(r"(?m)^  gemini:\n", f"  gemini:\n    model: {model}\n", text)
    assert "\nprompt:" not in text
    return text + f"\nprompt:\n  hints:\n    - {json.dumps(HINT)}\n"


def run_arm(problem: str, model: str, trials: int, tag: str) -> dict:
    """One cadence run in a fresh copy. Returns its id, trial count and winner path."""
    src = SVR / PROBLEMS[problem]["root"]
    dst = WORK / tag
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "winners"))
    (dst / ".cadence").write_text(manifest(problem, model, trials, f"svr-{tag}"))
    run_id = f"{tag.replace('/', '-')}-{SUFFIX}"
    t0 = time.time()
    p = subprocess.run(CADENCE + ["run", "--id", run_id, "--json"], cwd=dst,
                       capture_output=True, text=True)
    secs = time.time() - t0
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    (OUT / "logs" / f"{run_id}.out").write_text(p.stdout + "\n--- stderr\n" + p.stderr)
    try:
        summary = json.loads(p.stdout)
    except json.JSONDecodeError:
        summary = {}
    measured = summary.get("scored", -1)
    if "already recorded" in p.stderr:
        raise SystemExit(f"{run_id} already exists; refusing to reuse its results")
    a = subprocess.run(CADENCE + ["apply", run_id, str(dst)], cwd=dst,
                       capture_output=True, text=True)
    return {"run_id": run_id, "exit": p.returncode, "measured": measured,
            "status": summary.get("status"), "spend": summary.get("spend"),
            "cadence_metrics": summary.get("metrics"),
            "secs": round(secs, 1), "applied": a.returncode == 0,
            "program": str(dst / PROBLEMS[problem]["program"]), "dir": str(dst)}


def count_measured(run_id: str, root: Path) -> int:
    p = subprocess.run(CADENCE + ["trials", run_id, "--json"], cwd=root,
                       capture_output=True, text=True)
    try:
        rows = json.loads(p.stdout)
    except json.JSONDecodeError:
        return -1
    rows = rows.get("trials", rows) if isinstance(rows, dict) else rows
    return sum(1 for r in rows if str(r.get("verdict", r.get("kind", ""))).lower()
               in ("measured", "improved", "regressed", "kept", "scored")
               and r.get("index", 1) != 0)


def rescore(problem: str, d: Path) -> dict:
    """Score the winner in a fresh process, outside cadence."""
    out = subprocess.run([sys.executable, "score.py"], cwd=d, capture_output=True,
                         text=True, timeout=600).stdout
    found = {}
    for l in out.splitlines():
        m = re.match(r"^\s*([A-Za-z_][\w.]*)\s*[:=]\s*([-+0-9.eE]+)\s*$", l)
        if m:
            found[m[1]] = float(m[2])
    res = {"metric": found.get(PROBLEMS[problem]["metric"])}
    if problem == "bin-packing":
        code = (
            "import sys; sys.path.insert(0, %r); sys.argv=['e', %r];"
            "import evaluate as e; p=e.load_priority(e.Path(%r));"
            "s=[e.load(e.HERE/'heldout'/f'{n}.txt') for n in e.SETS];"
            "v=[e.excess(x, lambda c,i: e.pack(c,i,p)) for x in s];"
            "import json; print(json.dumps({'heldout': sum(v)/len(v), 'sets': v}))"
        ) % (str(SVR / "bin-packing"), str(d / "heuristic.py"), str(d / "heuristic.py"))
        o = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=600, cwd=SVR / "bin-packing").stdout
        res.update(json.loads(o.strip().splitlines()[-1]))
    return res


def lines_changed(problem: str, program: Path) -> int:
    start = SVR / PROBLEMS[problem]["root"] / PROBLEMS[problem]["program"]
    p = subprocess.run(["diff", "-U0", str(start), str(program)], capture_output=True, text=True)
    return sum(1 for l in p.stdout.splitlines()
               if l[:1] in "+-" and not l.startswith(("+++", "---")))


def finish(problem: str, arm: dict) -> dict:
    d = Path(arm["dir"])
    arm["rescore"] = rescore(problem, d)
    arm["lines_changed"] = lines_changed(problem, Path(arm["program"]))
    region = Path(arm["program"]).read_text()
    arm["suspect"] = sorted(set(SUSPECT.findall(region)))
    return arm


def pair(block: int, model: str, problem: str) -> dict:
    order = ["search", "recall"] if block % 2 == 0 else ["recall", "search"]
    rec = {"block": block, "model": model, "problem": problem, "order": order}
    for arm in order:
        if arm == "search":
            rec["search"] = finish(problem, run_arm(problem, model, N, f"b{block}/{problem}/search"))
        else:
            runs = [finish(problem, run_arm(problem, model, 1, f"b{block}/{problem}/recall{k}"))
                    for k in range(N)]
            score = lambda r: (r["rescore"]["metric"] if r["rescore"]["metric"] is not None
                               else float("-inf") * PROBLEMS[problem]["better"])
            best = max(runs, key=lambda r: PROBLEMS[problem]["better"] * score(r))
            rec["recall"] = {"runs": runs, "best": best["run_id"],
                             "measured": sum(r["measured"] for r in runs), **{
                                 k: best[k] for k in ("rescore", "lines_changed", "suspect")}}
    rec["complete"] = (rec["search"]["measured"] >= N and rec["recall"]["measured"] >= N)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if args.smoke:
        arm = finish("bin-packing", run_arm("bin-packing", args.smoke, 1, "smoke/bin-packing"))
        print(json.dumps(arm, indent=1))
        return
    done = set()
    saved = OUT / "pairs.jsonl"
    if saved.exists():
        done = {(r["block"], r["problem"]) for r in map(json.loads, saved.read_text().splitlines())}
    for block, model in enumerate(MODELS):
        problems = list(PROBLEMS) if block % 2 == 0 else list(reversed(PROBLEMS))
        for problem in problems:
            if (block, problem) in done:
                continue
            rec = pair(block, model, problem)
            with saved.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"block {block} {model} {problem}: complete={rec['complete']} "
                  f"search={rec['search']['rescore']} recall={rec['recall']['rescore']}",
                  flush=True)


if __name__ == "__main__":
    main()
