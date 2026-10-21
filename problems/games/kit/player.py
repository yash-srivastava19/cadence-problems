"""Players, and the wall between a player and the game.

A player answers `choose(observation, legal) -> index`. A `Remote` player runs
in its own process and is sent only JSON, so it cannot reach the game's
memory: not the bag, not the other player's rack, not the referee.

    python -m kit.player path/to/player.py      # the child side
"""

import importlib.util
import json
import select
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path


class Forfeit(Exception):
    """The player answered, but not with an allowed action, or too late."""


class Crashed(Exception):
    """The player's code raised, or its process died."""


class Local:
    """A trusted player, run in this process. For the fixed bots only."""

    def __init__(self, choose: Callable[[dict, list[dict]], int], name: str):
        self.fn, self.name = choose, name

    def choose(self, observation: dict, legal: list[dict]) -> int:
        return _checked(self.fn(observation, legal), legal)

    def close(self) -> None:
        pass


class Remote:
    """An untrusted player, in its own process, spoken to in JSON lines."""

    def __init__(self, path: Path, name: str, seconds: float = 10.0):
        self.path, self.name, self.seconds = path, name, seconds
        self.calls, self.used = 0, 0.0  # moves answered, seconds spent on them
        self._start()

    def _start(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "kit.player", str(self.path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

    def choose(self, observation: dict, legal: list[dict]) -> int:
        assert self.proc.stdin is not None
        assert self.proc.stdout is not None
        try:
            self.proc.stdin.write(
                json.dumps({"observation": observation, "legal": legal}) + "\n"
            )
            self.proc.stdin.flush()
        except BrokenPipeError as error:
            raise Crashed(f"{self.name} has exited") from error
        started = time.monotonic()
        ready, _, _ = select.select([self.proc.stdout], [], [], self.seconds)
        if not ready:
            # Its late answer would be read as the reply to the next question.
            self._stop()
            self._start()
            raise Forfeit(f"no answer within {self.seconds}s")
        line = self.proc.stdout.readline()
        self.calls, self.used = self.calls + 1, self.used + time.monotonic() - started
        if not line:
            raise Crashed(f"{self.name} exited with {self.proc.wait()}")
        reply = json.loads(line)
        if "error" in reply:
            raise Crashed(reply["error"])
        return _checked(reply.get("choice"), legal)

    def close(self) -> None:
        self._stop()

    def _stop(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


class Record(dict):
    """A dict that can also be read with dots: move["score"] or move.score.

    Players are written by models, and models mix the two styles. One type
    that answers both removes that whole class of crash."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


def _checked(choice, legal: list[dict]) -> int:
    if type(choice) is not int or not 0 <= choice < len(legal):
        raise Forfeit(f"answered {choice!r}, not an index into {len(legal)} moves")
    return choice


def serve(path: str) -> None:
    spec = importlib.util.spec_from_file_location("candidate", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    replies, sys.stdout = sys.stdout, sys.stderr  # a stray print cannot corrupt
    spec.loader.exec_module(module)
    for line in sys.stdin:
        request = json.loads(line, object_hook=Record)
        try:
            reply = {"choice": module.choose(request["observation"], request["legal"])}
        except Exception as error:
            reply = {"error": f"{type(error).__name__}: {error}"}
        replies.write(json.dumps(reply) + "\n")
        replies.flush()


if __name__ == "__main__":
    serve(sys.argv[1])
