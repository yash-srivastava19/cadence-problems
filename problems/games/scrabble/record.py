"""Run a command and keep a record of it: what ran, where, and what it wrote.

    python -m scrabble.record <name> <outdir> -- <command...>

Writes rounds/runs/<start>-<name>.json with the code's fingerprint, the
machine, start and end times, the exit code, and a sha256 of every file under
<outdir> afterwards. The record is written at the start too, so a run that
dies still leaves one.
"""

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
RUNS = HERE / "rounds" / "runs"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def code() -> str:
    """One hash over every .py and .json file of the package, by path."""
    h = hashlib.sha256()
    for p in sorted(HERE.glob("*.py")) + sorted(HERE.glob("*.json")):
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def models() -> dict:
    """The learned and fitted files a player may read: networks and weights."""
    found = sorted(HERE.glob("rounds/**/*.pt")) + sorted(HERE.glob("rounds/**/weights.json")) \
        + sorted(HERE.glob("rounds/**/linear.json"))
    return {str(p.relative_to(HERE)): sha(p) for p in found}


def machine() -> dict:
    out = {"host": socket.gethostname(), "cpus": os.cpu_count(), "python": platform.python_version()}
    try:  # on EC2, the instance type
        token = subprocess.run(
            ["curl", "-s", "-m", "2", "-X", "PUT", "http://169.254.169.254/latest/api/token",
             "-H", "X-aws-ec2-metadata-token-ttl-seconds: 60"], capture_output=True, text=True).stdout
        kind = subprocess.run(
            ["curl", "-s", "-m", "2", "-H", f"X-aws-ec2-metadata-token: {token}",
             "http://169.254.169.254/latest/meta-data/instance-type"], capture_output=True, text=True).stdout
        if kind and "<" not in kind:
            out["instance"] = kind
    except OSError:
        pass
    return out


def main() -> None:
    name, outdir, rest = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
    command = rest[1:] if rest and rest[0] == "--" else rest
    RUNS.mkdir(parents=True, exist_ok=True)
    start = time.strftime("%Y%m%dT%H%M%S")
    path = RUNS / f"{start}-{name}.json"
    record = {"name": name, "command": command, "code_sha256": code(),
              "source": os.environ.get("SOURCE", ""), "models": models(), "machine": machine(),
              "start": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "end": None, "exit": None}
    path.write_text(json.dumps(record, indent=1) + "\n")
    exit_code = subprocess.call(command)
    record["end"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    record["exit"] = exit_code
    record["outputs"] = {str(p.relative_to(outdir)): sha(p) for p in sorted(outdir.rglob("*")) if p.is_file()}
    path.write_text(json.dumps(record, indent=1) + "\n")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
