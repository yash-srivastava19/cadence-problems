"""Quackle's players as opponents.

    python -m scrabble.macondo duel --who klve+peg+sim --vs quackle-sim

Quackle (github.com/quackle/quackle) runs as qserve, one per worker. Each turn
it gets the game so far as a GCG, its own rack, the unseen tiles and the
opponent's rack size; never our rack. Our moves appear in the GCG with only
the tiles they put down, and our exchanges as a count, as in a real game.

Every disagreement stops the game with a Mismatch, so a run with no errors is
a run where both engines agreed on every move, score and total.
"""

import os
import subprocess
from pathlib import Path

from scrabble.game import Game

HOME = Path(os.environ.get("QUACKLE", Path.home() / "quackle" / "qserve"))
PLAYERS = {"quackle-static": "Static Player", "quackle-sim": "Championship Player"}  # as shipped


class Mismatch(ValueError):
    """Quackle and our engine disagree; the game is void."""


class Server:
    def __init__(self, vs: str):
        self.p = subprocess.Popen([str(HOME / "qserve"), PLAYERS[vs], "0", "0"], cwd=HOME,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        ready = self.p.stdout.readline()
        if not ready.startswith("READY") or "=0" in ready:  # every strategy file must load
            raise RuntimeError(f"qserve did not start cleanly: {ready!r}")

    def move(self, g: Game, played: list, seed: int) -> tuple[str, int, int]:
        """Quackle's move as Macondo would write it, its score, and how many illegal
        exchanges Quackle ranked above it."""
        me = g.to_move
        unseen = "".join(t * n for t, n in g.view()["unseen"].items())
        request = gcg(played, me) + [f"SEED {seed * 1000 + g.turn}", f"ME {me}", f"RACK {''.join(g.racks[me])}",
                                     f"UNSEEN {unseen}", f"OPP {len(g.racks[1 - me])}", "END"]
        self.p.stdin.write("\n".join(request) + "\n")
        self.p.stdin.flush()
        reply = self.p.stdout.readline().split()
        if not reply:
            raise RuntimeError("qserve exited")
        if reply[0] != "MOVE":
            raise Mismatch(" ".join(reply))
        kind, where, tiles, score, mine, theirs, rescored, skipped = reply[1:]
        if int(rescored):
            raise Mismatch(f"Quackle rescored {rescored} earlier moves")
        if [int(mine), int(theirs)] != [g.scores[me], g.scores[1 - me]]:
            raise Mismatch(f"totals {mine}/{theirs}, ours {g.scores[me]}/{g.scores[1 - me]}")
        if kind == "exch":
            return f"exch {tiles}", 0, int(skipped)
        if kind == "pass":
            return "pass", 0, int(skipped)
        return f"{where} {tiles}", int(score), int(skipped)


def gcg(played: list, me: int) -> list[str]:
    """The game so far; our racks hold only what we put down."""
    from scrabble.macondo import written

    lines, totals = ["#player1 p0 p0", "#player2 p1 p1"], [0, 0]
    for mover, rack, m in played:
        totals[mover] += m.score
        if m.kind == "play":
            shown = "".join(rack) if mover == me else "".join("?" if b else t for _, _, t, b in m.tiles)
            lines.append(f">p{mover}: {shown} {written(m)} +{m.score} {totals[mover]}")
        elif m.kind == "exchange" and mover == me:
            lines.append(f">p{mover}: {''.join(rack)} -{''.join(m.returned)} +0 {totals[mover]}")
        elif m.kind == "exchange":
            lines.append(f">p{mover}: {'?' * len(m.returned)} -{len(m.returned)} +0 {totals[mover]}")
        else:
            lines.append(f">p{mover}: {''.join(rack) if mover == me else '?'} - +0 {totals[mover]}")
    return lines
