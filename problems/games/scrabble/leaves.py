"""Leave values learned from self-play: HastyBot's own table.

    python -m scrabble.leaves AEINST ?S UUU
    python -m scrabble.leaves winp          # fit the win chance table

A klv2 file (wolges/Macondo) is a word graph of every leave of 1 to 6 tiles,
letters sorted with the blank first, then one f32 value per leave in the
order the graph lists them. NWL23's table came from hundreds of millions of
self-play games; our crude A2 formula has six numbers.

The static player `klv` is HastyBot's rule: points plus the leave's value
while tiles remain; once the bag is empty, going out earns twice the
opponent's tiles and being stuck costs twice your own.
"""

import json
import math
import struct
import sys
from pathlib import Path

from scrabble.game import Game, Move

HERE = Path(__file__).parent
KLV = HERE / "lexica" / "NWL23.klv2"
WINP = HERE / "rounds" / "leaves" / "winp.json"
POSITIONS = HERE / "rounds" / "value" / "positions.jsonl"

_table: dict[str, float] | None = None
_winp: dict | None = None


def table(path: Path = KLV) -> dict[str, float]:
    global _table
    if _table is not None:
        return _table
    b = path.read_bytes()
    n = struct.unpack_from("<I", b, 0)[0]
    nodes = struct.unpack_from(f"<{n}I", b, 4)
    count = struct.unpack_from("<I", b, 4 + 4 * n)[0]
    values = struct.unpack_from(f"<{count}f", b, 8 + 4 * n)
    words: list[str] = []

    def walk(p: int, prefix: str) -> None:
        # Siblings in order, each one's children before the next sibling:
        # the order the values are stored in. Leaves are at most 6 deep.
        while True:
            v = nodes[p]
            tile = v >> 24
            w = prefix + ("?" if tile == 0 else chr(64 + tile))
            if v & 0x800000:
                words.append(w)
            if v & 0x3FFFFF:
                walk(v & 0x3FFFFF, w)
            if v & 0x400000:
                return
            p += 1

    walk(nodes[0] & 0x3FFFFF, "")
    assert len(words) == count, (len(words), count)
    _table = dict(zip(words, values, strict=True))
    return _table


def value(leave) -> float:
    if not leave:
        return 0.0
    return table().get("".join(sorted(leave)), 0.0)


def equity(g: Game, move: Move) -> float:
    if g.bag:
        return move.score + value(move.leave)
    if not move.leave:
        theirs = g.racks[1 - g.to_move]
        return move.score + 2 * sum(g.rs.value(t) for t in theirs)
    return move.score - 2 * sum(g.rs.value(t) for t in move.leave)


def klv(g: Game, moves) -> int:
    keys = [equity(g, m) for m in moves]
    return keys.index(max(keys))


def fit_winp() -> None:
    """How the spread moves from an afterstate to the end, by tiles in the
    bag: its mean and spread over our recorded games, smoothed over nearby
    bag sizes. BestBot's win table, from data we already have."""
    ys: dict[int, list[float]] = {}
    with POSITIONS.open() as f:
        for line in f:
            for r in json.loads(line)["rows"]:
                ys.setdefault(r["bag"], []).append(r["y"])
    top = max(ys)
    mean, sd = [], []
    for b in range(top + 1):
        # An empty bag is its own regime (no draws left): never pooled.
        near = ys[0] if b == 0 else [y for k in range(max(1, b - 3), b + 4) for y in ys.get(k, [])]
        m = sum(near) / len(near)
        mean.append(round(m, 2))
        sd.append(round(math.sqrt(sum((y - m) ** 2 for y in near) / len(near)), 2))
    WINP.parent.mkdir(parents=True, exist_ok=True)
    WINP.write_text(json.dumps({"mean": mean, "sd": sd}))
    for b in range(0, top + 1, 10):
        print(f"bag {b}: drift {mean[b]:+.1f}, sd {sd[b]:.1f}")


def winp(points: float, bag: int) -> float:
    """Win chance for the side that just moved, `points` ahead counting leaves."""
    global _winp
    if _winp is None:
        _winp = json.loads(WINP.read_text())
    b = min(bag, len(_winp["mean"]) - 1)
    z = (points + _winp["mean"][b]) / _winp["sd"][b]
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


if __name__ == "__main__":
    if sys.argv[1:] == ["winp"]:
        fit_winp()
        sys.exit()
    for leave in sys.argv[1:]:
        print(leave, round(value(leave), 2))
