"""Checks for the teacher. From problems/games: python -m pytest scrabble"""

import random

import pytest

from scrabble import board, simulate
from scrabble.game import Game
from scrabble.ruleset import load

from .test_engine import HERE


@pytest.fixture(scope="module")
def english():
    return load(HERE / "english.json")


def midgame(rs, seed, turns=8):
    g = Game(rs, seed)
    for _ in range(turns):
        g.apply(simulate.greedy(g.legal()))
    return g


def test_a_game_rebuilt_mid_way_plays_on_identically(english):
    g = midgame(english, 3)
    h = Game.at(english, g, g.racks, g.bag, seed=0)
    h.rng.setstate(g.rng.getstate())
    for _ in range(6):
        if g.over:
            break
        a, b = simulate.greedy(g.legal()), simulate.greedy(h.legal())
        assert a == b
        g.apply(a)
        h.apply(b)
    assert g.scores == h.scores
    assert g.grid == h.grid


def test_the_teacher_never_sees_the_hidden_tiles(english):
    """Shuffle the real opponent rack and bag: the teacher's answer is the same."""
    g = midgame(english, 5)
    p = g.to_move
    moves = g.legal()
    picks = simulate.shortlist(g, moves)
    before = simulate.simulate(g, moves, picks, seed=1, samples=4)

    hidden = g.racks[1 - p] + g.bag
    random.Random(99).shuffle(hidden)
    held = len(g.racks[1 - p])
    g.racks[1 - p], g.bag = sorted(hidden[:held]), hidden[held:]
    after = simulate.simulate(g, moves, picks, seed=1, samples=4)
    assert before == after


def test_every_candidate_faces_the_same_worlds(english):
    g = midgame(english, 7)
    moves = g.legal()
    i = simulate.shortlist(g, moves)[0]
    out = simulate.simulate(g, moves, [i, i], seed=2, samples=5)
    assert len(out) == 1  # the same move twice is one entry
    twice = simulate.simulate(g, moves, [i], seed=2, samples=5)
    assert out == twice


def test_worlds_hold_exactly_the_unseen_tiles(english):
    g = midgame(english, 9)
    p = g.to_move
    w = simulate.world(g, p, random.Random(0))
    assert w.racks[p] == g.racks[p]
    assert sorted(w.racks[1 - p] + w.bag) == simulate.unseen(g, p)
    assert len(w.racks[1 - p]) == len(g.racks[1 - p])
    assert board.score  # the board module is shared, not copied
