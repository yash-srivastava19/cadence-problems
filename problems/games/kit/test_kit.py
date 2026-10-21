"""Checks for the kit, on a tiny made-up game. From examples/games:

python -m pytest kit
"""

from pathlib import Path

import pytest

from kit.play import duplicate, play
from kit.player import Crashed, Local, Remote


class Hidden:
    """A two-player game with a secret only the referee holds."""

    name, players = "hidden", 2

    def reset(self, seed):
        return {"secret": f"SECRET-{seed}", "turn": 0, "picks": [0, 0]}

    def to_move(self, s):
        return s["turn"] % 2

    def observe(self, s, player):
        return {"turn": s["turn"]}

    def legal(self, s):
        return [{"label": "low"}, {"label": "high"}]

    def step(self, s, choice):
        s["picks"][s["turn"] % 2] += choice
        s["turn"] += 1
        return s

    def done(self, s):
        return s["turn"] == 4

    def returns(self, s):
        return [float(p) for p in s["picks"]]


def high(observation, legal):
    return 1


def low(observation, legal):
    return 0


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "player.py"
    path.write_text(f"def choose(observation, legal):\n{body}\n")
    return path


def test_play_records_every_choice_and_replays():
    record = play(Hidden(), [Local(high, "high"), Local(low, "low")], seed=3)
    assert record["actions"] == [1, 0, 1, 0]
    assert record["returns"] == [2.0, 0.0]
    assert record == play(Hidden(), [Local(high, "high"), Local(low, "low")], 3)


def test_duplicate_swaps_the_seats():
    games = duplicate(Hidden(), Local(high, "a"), Local(low, "b"), [1])
    assert [seat for _, seat in games] == [0, 1]
    assert all(r["returns"][seat] == 2.0 for r, seat in games)


def test_a_remote_player_plays(tmp_path):
    me = Remote(write(tmp_path, "    return 1"), "remote")
    try:
        record = play(Hidden(), [me, Local(low, "low")], seed=0)
    finally:
        me.close()
    assert record["returns"] == [2.0, 0.0]


def test_an_answer_out_of_range_forfeits(tmp_path):
    me = Remote(write(tmp_path, "    return 7"), "remote")
    try:
        record = play(Hidden(), [me, Local(low, "low")], seed=0)
    finally:
        me.close()
    assert record["forfeit"]["player"] == 0
    assert record["returns"] is None


def test_a_crash_is_not_a_forfeit(tmp_path):
    me = Remote(write(tmp_path, "    raise ValueError('broken')"), "remote")
    try:
        with pytest.raises(Crashed, match="broken"):
            play(Hidden(), [me, Local(low, "low")], seed=0)
    finally:
        me.close()


CANARY = """\
    import gc
    for thing in gc.get_objects():
        found = isinstance(thing, dict) and str(thing.get("secret", ""))
        if found and found.startswith("SECRET"):
            return 1  # found the referee's state
    return 0"""


def test_the_canary_cannot_find_the_referees_state(tmp_path):
    me = Remote(write(tmp_path, CANARY), "canary")
    try:
        record = play(Hidden(), [me, Local(low, "low")], seed=5)
    finally:
        me.close()
    assert record["actions"][0::2] == [0, 0], "the player reached the game's memory"


def test_the_same_canary_in_process_does_find_it():
    """Proves the canary works: without the wall, it sees the secret."""
    namespace: dict = {}
    exec(f"def choose(observation, legal):\n{CANARY}\n", namespace)
    record = play(
        Hidden(), [Local(namespace["choose"], "in-process"), Local(low, "low")], 5
    )
    assert record["actions"][0::2] == [1, 1]


def test_a_slow_player_forfeits_and_the_next_game_is_clean(tmp_path):
    """A late answer must never be read as the reply to the next question."""
    path = write(tmp_path, "    import time\n    time.sleep(1.5)\n    return 1")
    me = Remote(path, "slow", seconds=0.5)
    try:
        first = play(Hidden(), [me, Local(low, "low")], seed=0)
        second = play(Hidden(), [me, Local(low, "low")], seed=1)
    finally:
        me.close()
    assert first["forfeit"]["player"] == 0
    assert second["forfeit"]["player"] == 0  # forfeits again; never a stale 1


def test_a_remote_player_reads_moves_with_brackets_or_dots(tmp_path):
    body = "    assert legal[1].label == legal[1]['label']\n    return 1"
    me = Remote(write(tmp_path, body), "remote")
    try:
        record = play(Hidden(), [me, Local(low, "low")], seed=0)
    finally:
        me.close()
    assert record["returns"] == [2.0, 0.0]
