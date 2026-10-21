"""Checks for the engine front end. From problems/games: python -m pytest scrabble/test_engine_cli.py"""

import io
from collections import Counter

import pytest

from scrabble import cgp, engine
from scrabble.fastslow import BASE, fast
from scrabble.game import Game

EMPTY = "/".join(["15"] * 15)
MID = ("3I11/3M11/2PI7R3/2AD7E3/2c4V3T3/2I4A3A3/2F4N3K3/2INFRUGAL1E3/2S5WOTS3/2T12/15/15/15/15/15"
       " AENOOTY/ 121/170 0")


@pytest.fixture(scope="module")
def rs():
    return engine.rules()


def test_a_macondo_cgp_assumes_a_full_rack_and_the_rest_in_the_bag(rs):
    pos = engine.position(rs, f"{EMPTY} AEINRST/ 0/0 0 lex NWL20;")
    assert (pos.turn, pos.held, pos.bag_size) == (0, 7, 86)
    mid = engine.position(rs, MID + " lex NWL20;")
    assert (mid.scores, mid.held, mid.bag_size) == ((121, 170), 7, 54)


def test_our_view_and_macondo_read_the_same(rs):
    ours = engine.position(rs, MID + " turn 6; held 7; bagsize 54;")
    theirs = engine.position(rs, MID)
    assert ours.grid == theirs.grid and ours.racks == theirs.racks
    assert (ours.held, ours.bag_size) == (theirs.held, theirs.bag_size)


def test_rebuild_redraws_what_the_player_cannot_see(rs):
    g = Game(rs, 3)
    for _ in range(4):
        g.apply(g.legal()[fast(g, g.legal(), BASE)])
    full = cgp.encode(g)
    w = engine.rebuild(rs, engine.position(rs, full), 99)
    p = g.to_move
    assert w.racks[p] == g.racks[p] and w.grid == g.grid and w.scores == g.scores
    assert len(w.racks[1 - p]) == len(g.racks[1 - p]) and len(w.bag) == len(g.bag)
    assert Counter(w.racks[1 - p] + w.bag) == Counter(g.racks[1 - p] + g.bag)


@pytest.mark.parametrize("bad", ["", "15/15 AB/ 0/0 0", f"{EMPTY} ABCDEFGH/ 0/0 0",
                                 f"{EMPTY} ZZZ/ 0/0 0", f"{EMPTY} AB/ x/0 0"])
def test_bad_positions_say_what_is_wrong(rs, bad):
    with pytest.raises(ValueError):
        engine.position(rs, bad)


def test_every_move_reads_back_from_its_notation(rs):
    g = engine.rebuild(rs, engine.position(rs, MID), 0)
    moves = g.legal()
    for m in moves[::7] + [m for m in moves if m.kind != "play"][:20]:
        assert engine.parse_move(engine.notation(m), moves) == m
        if m.kind == "play":
            assert engine.parse_move(f"{m.word} {m.where.lower()}", moves) == m


def test_illegal_moves_are_refused_politely(rs):
    g = engine.rebuild(rs, engine.position(rs, f"{EMPTY} ?EEGSTT/ 0/0 0"), 0)
    moves = g.legal()
    for text in ["", "8H", "8H ZZZ", "foo bar", "exchange QQ", "H4 GESTATE"]:
        with pytest.raises(ValueError):
            engine.parse_move(text, moves, rs)
    assert engine.parse_move("H4 GESTaTE", moves).score == 68
    assert engine.parse_move("pass", moves).kind == "pass"


def test_analyse_with_fast_0_picks_what_fast_0_plays(rs):
    g = engine.rebuild(rs, engine.position(rs, MID), 0)
    a = engine.analyse("fast_0", g, top=3)
    moves = g.legal()
    assert a["bestmove"] == engine.notation(moves[fast(g, moves, BASE)])
    assert len(a["moves"]) == 3 and a["moves"][0]["move"] == a["bestmove"]
    assert a["time"] >= 0 and "best" not in engine.public(a)


def test_the_uci_loop_answers_with_bestmove(rs):
    out = io.StringIO()
    engine.uci("fast_0", io.StringIO(f"uci\nisready\nposition cgp {MID}\ngo top 2\nposition cgp nope\nquit\ngo\n"), out)
    lines = out.getvalue().splitlines()
    assert lines[:4] == ["id name cadence-scrabble", "option player fast_0", "uciok", "readyok"]
    assert lines[-2] == "bestmove E2 ATONY"
    assert sum(x.startswith("info multipv") for x in lines) == 2
    assert lines[-1].startswith("info string error")


def test_unknown_players_are_named(rs):
    with pytest.raises(ValueError, match="known"):
        engine.player("s9-nonsense")
