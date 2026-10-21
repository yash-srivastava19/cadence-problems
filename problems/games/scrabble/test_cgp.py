"""Checks for the CGP encoding. From problems/games: python -m pytest scrabble"""

import random
from collections import Counter

import pytest

from scrabble import cgp, simulate
from scrabble.game import Game
from scrabble.ruleset import load

from .test_engine import HERE


@pytest.fixture(scope="module")
def english():
    return load(HERE / "english.json")


def positions(rs, seeds=range(4)):
    """Every position of a few greedy games, start to finish."""
    for seed in seeds:
        g = Game(rs, seed)
        while not g.over:
            yield g
            g.apply(simulate.greedy(g.legal()))
        yield g


def test_the_first_position_reads_as_expected(english):
    g = Game(english, 0)
    text = cgp.encode(g)
    assert text.startswith("/".join(["15"] * 15) + " ")
    assert f"0/0 0 turn 0; bag {''.join(g.bag)};" in text


def test_a_full_state_survives_the_round_trip(english):
    for g in positions(english):
        text = cgp.encode(g)
        h = cgp.decode(english, text)
        assert (h.grid, h.racks, h.scores, h.bag, h.turn, h.scoreless) == (
            g.grid, g.racks, g.scores, g.bag, g.turn, g.scoreless
        )
        assert cgp.encode(h) == text


def test_a_view_never_shows_the_hidden_tiles(english):
    """Shuffle the other rack and the bag: the view is byte for byte the same."""
    rng = random.Random(0)
    for g in positions(english, range(2)):
        if g.over:
            continue
        p = g.to_move
        before = cgp.encode(g, viewer=p)
        hidden = g.racks[1 - p] + g.bag
        rng.shuffle(hidden)
        held = len(g.racks[1 - p])
        g.racks[1 - p], g.bag = sorted(hidden[:held]), hidden[held:]
        assert cgp.encode(g, viewer=p) == before


def test_a_view_knows_exactly_what_a_player_may_know(english):
    for g in positions(english, range(2)):
        if g.over:
            continue
        p = g.to_move
        pos = cgp.parse(cgp.encode(g, viewer=p))
        assert pos.bag is None
        assert pos.racks == (g.racks[p], [])
        assert (pos.held, pos.bag_size) == (len(g.racks[1 - p]), len(g.bag))
        assert Counter(cgp.unseen(english, pos)) == Counter(g.racks[1 - p] + g.bag)


def test_a_view_cannot_be_decoded_into_a_full_game(english):
    g = Game(english, 0)
    with pytest.raises(AssertionError, match="no bag"):
        cgp.decode(english, cgp.encode(g, viewer=0))


def test_multi_letter_tokens_are_bracketed(english):
    toy = load(HERE / "toy.json")
    g = Game(toy, 1)
    g.grid[2][2] = ("QU", False)
    text = cgp.encode(g)
    assert "[QU]" in text
    assert cgp.decode(toy, text).grid[2][2] == ("QU", False)
