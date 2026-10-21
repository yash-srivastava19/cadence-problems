"""Checks for the engine. From examples/games: python -m pytest scrabble

The validator below is written separately from board.py on purpose: move
generation is checked against a second, simpler reading of RULES.md.
"""

import os
import subprocess
import sys
from collections import Counter
from itertools import combinations, permutations
from pathlib import Path

import pytest

from scrabble import board, bots
from scrabble.env import as_dict
from scrabble.game import Game
from scrabble.ruleset import BLANK, load

HERE = Path(__file__).parent
LM = {"d": 2, "t": 3}
WM = {"D": 2, "T": 3, "*": 2}


@pytest.fixture(scope="module")
def english():
    return load(HERE / "english.json")


@pytest.fixture(scope="module")
def toy():
    return load(HERE / "toy.json")


def place(grid, tiles):
    for r, c, t, b in tiles:
        grid[r][c] = (t, b)


def across(r, c, word):
    return tuple((r, c + i, t, False) for i, t in enumerate(word))


def down(r, c, word):
    return tuple((r + i, c, t, False) for i, t in enumerate(word))


# -- an independent reading of the rules ------------------------------------


def runs(grid, new, n):
    """Every maximal line of two or more tiles that contains a new tile."""
    filled = {(r, c) for r in range(n) for c in range(n) if grid[r][c]} | set(new)
    out = []
    for dr, dc in ((0, 1), (1, 0)):
        for r, c in new:
            while (r - dr, c - dc) in filled:
                r, c = r - dr, c - dc
            line = []
            while (r, c) in filled:
                line.append((r, c))
                r, c = r + dr, c + dc
            if len(line) > 1 and line not in out:
                out.append(line)
    return out


def check(rs, grid, tiles):
    """None if the play is legal, else why not. Also returns its score."""
    n = rs.size
    new = {(r, c): (t, b) for r, c, t, b in tiles}
    if len(new) != len(tiles) or any(grid[r][c] for r, c in new):
        return "square taken", 0
    rows, cols = {r for r, c in new}, {c for r, c in new}
    if len(rows) > 1 and len(cols) > 1:
        return "not in one line", 0
    line = sorted(new)
    (r0, c0), (r1, c1) = line[0], line[-1]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if (r, c) not in new and not grid[r][c]:
                return "gap", 0
    if all(cell is None for row in grid for cell in row):
        if rs.centre not in new or len(new) < 2:
            return "first play must cover the centre with two tiles", 0
    else:
        steps = ((1, 0), (-1, 0), (0, 1), (0, -1))
        near = [(r + a, c + b) for r, c in new for a, b in steps]
        if not any(0 <= i < n and 0 <= j < n and grid[i][j] for i, j in near):
            return "not connected", 0
    words = runs(grid, new, n)
    if not words:
        return "no word", 0
    total = 0
    for squares in words:
        word, pts, mult = [], 0, 1
        for r, c in squares:
            t, b = new.get((r, c)) or grid[r][c]
            word.append(t)
            v = 0 if b else rs.values[t]
            if (r, c) in new:
                pts += v * LM.get(rs.premiums[r][c], 1)
                mult *= WM.get(rs.premiums[r][c], 1)
            else:
                pts += v
        if tuple(word) not in rs.words:
            return f"not a word: {''.join(word)}", 0
        total += pts * mult
    return None, total + (rs.bingo if len(tiles) == rs.rack else 0)


# -- hand-computed scores ----------------------------------------------------


def test_hand_scored_plays(english):
    g = board.empty(english)
    quiet = across(7, 5, "QUIET")
    assert board.score(english, g, quiet) == 28  # centre doubles
    place(g, quiet)
    hex_ = ((6, 8, "H", False), (8, 8, "X", False))
    assert board.score(english, g, hex_) == 25  # both on double letters
    place(g, hex_)
    aqua = ((6, 5, "A", False), (8, 5, "U", False), (9, 5, "A", False))
    assert board.score(english, g, aqua) == 15  # triple letter under the last A


def test_premium_under_an_old_tile_does_not_count(english):
    g = board.empty(english)
    place(g, across(7, 5, "QUIET"))  # the I sits on the centre square
    bit = ((6, 7, "B", False), (8, 7, "T", False))
    assert board.score(english, g, bit) == 5  # not doubled


def test_bingo_and_blank(english):
    g = board.empty(english)
    assert board.score(english, g, across(7, 7, "RETAINS")) == 66
    blank_r = ((7, 7, "R", True), *across(7, 8, "ETAINS"))
    assert board.score(english, g, blank_r) == 64


# -- move generation is complete and sound (toy ruleset) ---------------------


def brute_force(rs, grid, rack):
    """Every legal play, by trying every placement of every rack subset."""
    n, found = rs.size, set()
    lines = [[(r, c) for c in range(n)] for r in range(n)]
    lines += [[(r, c) for r in range(n)] for c in range(n)]
    for line in lines:
        empty = [sq for sq in line if not grid[sq[0]][sq[1]]]
        for k in range(1, len(rack) + 1):
            for squares in combinations(empty, k):
                for tiles in set(permutations(rack, k)):
                    options = [
                        [(t, False)] if t != BLANK else [(x, True) for x in rs.tokens]
                        for t in tiles
                    ]
                    stack = [[]]
                    for opt in options:
                        stack = [[*s, o] for s in stack for o in opt]
                    for assign in stack:
                        play = tuple(
                            sorted(
                                (r, c, t, b)
                                for (r, c), (t, b) in zip(squares, assign, strict=True)
                            )
                        )
                        if check(rs, grid, play)[0] is None:
                            found.add(play)
    return found


@pytest.mark.parametrize("seed", range(6))
def test_generation_matches_brute_force(toy, seed):
    g = Game(toy, seed)
    for _ in range(3):
        if g.over:
            break
        rack = g.racks[g.to_move]
        generated = {p.tiles for p in board.plays(toy, g.grid, rack)}
        assert generated == brute_force(toy, g.grid, rack)
        plays = [m for m in g.legal() if m.kind == "play"]
        g.apply(max(plays, key=lambda m: m.score) if plays else g.legal()[-1])


def test_multi_letter_token(toy):
    g = board.empty(toy)
    aqua = ((2, 1, "A", False), (2, 2, "QU", False), (2, 3, "A", False))
    assert check(toy, g, aqua) == (None, board.score(toy, g, aqua))
    assert board.describe(toy, g, aqua)[0] == "AQUA"


# -- real games --------------------------------------------------------------


def test_playouts_keep_every_tile_and_every_play_is_legal(english):
    for seed in range(2):
        g = Game(english, seed)
        pick = bots.make_random(seed)
        while not g.over:
            moves = g.legal()
            for m in moves[:: max(1, len(moves) // 150)]:
                if m.kind == "play":
                    why, pts = check(english, g.grid, m.tiles)
                    assert why is None, (m.label(), why)
                    assert pts == m.score, m.label()
            g.apply(moves[pick(g.view(), [as_dict(m) for m in moves])])
            on_board = sum(cell is not None for row in g.grid for cell in row)
            total = on_board + len(g.bag) + sum(map(len, g.racks))
            assert total == len(english.full_set())
            assert Counter(g.bag) + Counter(g.racks[0]) + Counter(
                g.racks[1]
            ) <= Counter(english.full_set())


GAME = """
import sys; sys.path.insert(0, {here!r})
from scrabble.ruleset import load; from scrabble.game import Game
from scrabble import bots; from scrabble.env import as_dict
rs = load({config!r}); g = Game(rs, 7); pick = bots.make_random(7)
while not g.over:
    ms = g.legal(); m = ms[pick(g.view(), [as_dict(x) for x in ms])]
    print(m.label()); g.apply(m)
print(g.scores)
"""


def test_same_seed_same_game_under_any_hash_seed():
    code = GAME.format(here=str(HERE.parent), config=str(HERE / "english.json"))
    outs = []
    for hash_seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        outs.append(
            subprocess.run(
                [sys.executable, "-c", code],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
    assert outs[0] == outs[1]


# -- the end of a game --------------------------------------------------------


def test_going_out_gains_twice_the_other_rack(english):
    g = Game(english, 0)
    g.bag, g.racks = [], [["A", "A"], ["Q", "Z"]]
    aa = next(m for m in g.legal() if m.kind == "play" and m.word == "AA")
    g.apply(aa)
    assert g.over
    assert g.scores == [aa.score + 2 * 20, 0]


def test_six_scoreless_turns_cost_each_player_their_rack(english):
    g = Game(english, 0)
    racks = [g.rack_value(0), g.rack_value(1)]
    for _ in range(6):
        assert not g.over
        g.apply(g.legal()[-1])  # pass
    assert g.over
    assert g.scores == [-racks[0], -racks[1]]


def test_no_exchange_with_fewer_than_seven_in_the_bag(english):
    g = Game(english, 0)
    g.bag = g.bag[:6]
    assert all(m.kind != "exchange" for m in g.legal())
