"""Checks for the player's toolbox. From problems/games: python -m pytest scrabble"""

import random
from collections import Counter

from scrabble import cgp, simulate, tools
from scrabble.env import as_dict
from scrabble.game import Game


def midgame(seed: int, turns: int = 10) -> Game:
    g = Game(tools.ruleset(), seed)
    for _ in range(turns):
        g.apply(simulate.greedy(g.legal()))
    return g


def test_a_sampled_world_keeps_what_the_player_knows():
    g = midgame(1)
    p = g.to_move
    w = tools.sample_world(cgp.encode(g, viewer=p), random.Random(0))
    assert (w.grid, w.scores, w.turn, w.scoreless) == (
        g.grid, g.scores, g.turn, g.scoreless
    )
    assert w.racks[p] == g.racks[p]
    assert len(w.racks[1 - p]) == len(g.racks[1 - p]) and len(w.bag) == len(g.bag)
    assert Counter(w.racks[1 - p] + w.bag) == Counter(g.racks[1 - p] + g.bag)


def test_imagined_moves_come_in_the_order_the_player_was_sent():
    for seed in range(3):
        g = midgame(seed)
        sent = [as_dict(m) for m in g.legal()]
        w = tools.sample_world(cgp.encode(g, viewer=g.to_move), random.Random(seed))
        assert tools.legal(w) == sent


def test_play_leaves_the_world_it_was_given_alone():
    g = midgame(2)
    w = tools.sample_world(cgp.encode(g, viewer=g.to_move), random.Random(1))
    before = cgp.encode(w)
    move = simulate.greedy(tools.legal(w))
    after = tools.play(w, move)
    assert cgp.encode(w) == before
    assert after.turn == w.turn + 1
    assert tools.spread(after, w.to_move) == tools.spread(w, w.to_move) + move.score


def test_once_the_bag_is_empty_the_world_is_exact():
    g = Game(tools.ruleset(), 4)
    while g.bag and not g.over:
        g.apply(simulate.greedy(g.legal()))
    p = g.to_move
    w = tools.sample_world(cgp.encode(g, viewer=p), random.Random(7))
    assert w.racks[1 - p] == g.racks[1 - p]


def test_a_move_reads_with_brackets_or_dots_and_plays_in_any_form():
    g = midgame(3)
    w = tools.sample_world(cgp.encode(g, viewer=g.to_move), random.Random(2))
    moves = tools.legal(w)
    best = max(range(len(moves)), key=lambda i: moves[i].score)
    assert moves[best].score == moves[best]["score"]
    by_index = cgp.encode(tools.play(w, best))
    by_dict = cgp.encode(tools.play(w, dict(moves[best])))
    by_object = cgp.encode(tools.play(w, w.legal()[best]))
    assert by_index == by_dict == by_object
