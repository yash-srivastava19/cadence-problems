"""The board: every legal play on it, and what a play scores.

Move generation is Appel and Jacobson's (1988). Plays are found one row at a
time; columns are found by running the same code on the transposed board.

- An **anchor** is an empty square next to a tile. Every play covers one.
- A **cross set** says which tokens may go on an empty square without making
  an invalid word in the other direction.
- From each anchor, build every **left part** that fits in the empty squares
  before it, then **extend right** through the anchor, following the word
  trie, so only prefixes of real words are ever tried.
"""

from collections import Counter
from dataclasses import dataclass

from scrabble.ruleset import BLANK, END, Ruleset

Tile = tuple[str, bool]  # token, and whether it is a blank standing in for it
Grid = list[list[Tile | None]]
Placement = tuple[int, int, str, bool]  # row, col, token, blank

LETTER = {"d": 2, "t": 3}
WORD = {"D": 2, "T": 3, "*": 2}


@dataclass(frozen=True)
class Play:
    tiles: tuple[Placement, ...]
    score: int
    word: str
    where: str


def empty(rs: Ruleset) -> Grid:
    return [[None] * rs.size for _ in range(rs.size)]


def is_empty(grid: Grid) -> bool:
    return all(cell is None for row in grid for cell in row)


def _cross_sets(rs: Ruleset, grid: Grid, r: int) -> list[frozenset[str] | None]:
    """For each square in row r: the tokens allowed there. None means any."""
    n = rs.size
    out: list[frozenset[str] | None] = []
    for c in range(n):
        if grid[r][c] is not None:
            out.append(frozenset())
            continue
        up, i = [], r - 1
        while i >= 0 and (cell := grid[i][c]) is not None:
            up.append(cell[0])
            i -= 1
        up.reverse()
        down, i = [], r + 1
        while i < n and (cell := grid[i][c]) is not None:
            down.append(cell[0])
            i += 1
        if not up and not down:
            out.append(None)
            continue
        node = rs.trie
        for t in up:
            node = node.get(t)
            if node is None:
                break
        allowed = set()
        if node is not None:
            for t, child in node.items():
                if t == END:
                    continue
                end = child
                for d in down:
                    end = end.get(d)
                    if end is None:
                        break
                if end is not None and END in end:
                    allowed.add(t)
        out.append(frozenset(allowed))
    return out


def _anchors(grid: Grid, r: int, first: tuple[int, int] | None) -> list[int]:
    n = len(grid)
    if first is not None:
        return [first[1]] if first[0] == r else []
    out = []
    for c in range(n):
        if grid[r][c] is not None:
            continue
        near = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
        if any(0 <= i < n and 0 <= j < n and grid[i][j] for i, j in near):
            out.append(c)
    return out


def _along(rs: Ruleset, grid: Grid, rack: Counter, first) -> list[list[Placement]]:
    """Every play along the rows of this grid, as lists of placements."""
    n = rs.size
    found: list[list[Placement]] = []

    for r in range(n):
        row = grid[r]
        cross = _cross_sets(rs, grid, r)
        anchors = _anchors(grid, r, first)
        anchor_set = set(anchors)

        def extend(node, c, anchor, left, right, row=row, cross=cross, r=r):
            if c >= n or row[c] is None:
                if c > anchor and END in node:
                    start = anchor - len(left)
                    placed = [(r, start + i, t, b) for i, (t, b) in enumerate(left)]
                    found.append(placed + [(r, cc, t, b) for cc, t, b in right])
                if c >= n:
                    return
                allowed = cross[c]
                for t, child in node.items():
                    if t == END or (allowed is not None and t not in allowed):
                        continue
                    for blank, key in ((False, t), (True, BLANK)):
                        if rack[key] > 0:
                            rack[key] -= 1
                            right.append((c, t, blank))
                            extend(child, c + 1, anchor, left, right)
                            right.pop()
                            rack[key] += 1
            else:
                child = node.get(row[c][0])
                if child is not None:
                    extend(child, c + 1, anchor, left, right)

        def left_parts(node, left, limit, anchor):
            extend(node, anchor, anchor, left, [])
            if limit == 0:
                return
            for t, child in node.items():
                if t == END:
                    continue
                for blank, key in ((False, t), (True, BLANK)):
                    if rack[key] > 0:
                        rack[key] -= 1
                        left.append((t, blank))
                        left_parts(child, left, limit - 1, anchor)
                        left.pop()
                        rack[key] += 1

        for a in anchors:
            if a > 0 and row[a - 1] is not None:
                start = a
                while start > 0 and row[start - 1] is not None:
                    start -= 1
                node = rs.trie
                for c in range(start, a):
                    node = node.get(row[c][0]) if node is not None else None
                if node is not None:
                    extend(node, a, a, [], [])
            else:
                limit, c = 0, a - 1
                while c >= 0 and row[c] is None and c not in anchor_set:
                    limit += 1
                    c -= 1
                left_parts(rs.trie, [], limit, a)
    return found


def _word_at(grid, new, r, c, dr, dc):
    """The word through (r, c) in direction (dr, dc), as (row, col) squares."""
    n = len(grid)

    def filled(i, j):
        return 0 <= i < n and 0 <= j < n and (grid[i][j] or (i, j) in new)

    while filled(r - dr, c - dc):
        r, c = r - dr, c - dc
    squares = []
    while filled(r, c):
        squares.append((r, c))
        r, c = r + dr, c + dc
    return squares


def score(rs: Ruleset, grid: Grid, tiles: tuple[Placement, ...]) -> int:
    new = {(r, c): (t, b) for r, c, t, b in tiles}
    rows = {r for r, _, _, _ in tiles}
    across = len(tiles) > 1 and len(rows) == 1
    down = len(tiles) > 1 and not across
    directions = [(0, 1)] if across else [(1, 0)] if down else [(0, 1), (1, 0)]

    words = []
    r0, c0 = tiles[0][0], tiles[0][1]
    for dr, dc in directions:
        words.append(_word_at(grid, new, r0, c0, dr, dc))
    if len(tiles) > 1:
        cdr, cdc = (1, 0) if across else (0, 1)
        for r, c, _, _ in tiles:
            words.append(_word_at(grid, new, r, c, cdr, cdc))

    total = 0
    for squares in words:
        if len(squares) < 2:
            continue
        points, multiplier = 0, 1
        for r, c in squares:
            if (r, c) in new:
                t, b = new[(r, c)]
                premium = rs.premiums[r][c]
                points += rs.value(t, b) * LETTER.get(premium, 1)
                multiplier *= WORD.get(premium, 1)
            else:
                t, b = grid[r][c]
                points += rs.value(t, b)
        total += points * multiplier
    if len(tiles) == rs.rack:
        total += rs.bingo
    return total


def describe(rs: Ruleset, grid: Grid, tiles: tuple[Placement, ...]) -> tuple[str, str]:
    """The main word and where it starts, in the usual notation (8F, F8)."""
    new = {(r, c): (t, b) for r, c, t, b in tiles}
    rows = {r for r, _, _, _ in tiles}
    r0, c0 = tiles[0][0], tiles[0][1]
    candidates = [(0, 1), (1, 0)] if len(tiles) == 1 else None
    if candidates is None:
        candidates = [(0, 1)] if len(rows) == 1 else [(1, 0)]
    for dr, dc in candidates:
        squares = _word_at(grid, new, r0, c0, dr, dc)
        if len(squares) >= 2:
            break
    word = ""
    for r, c in squares:
        t, b = new.get((r, c)) or grid[r][c]
        word += t.lower() if b else t
    r, c = squares[0]
    col = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[c]
    return word, (f"{r + 1}{col}" if (dr, dc) == (0, 1) else f"{col}{r + 1}")


def plays(rs: Ruleset, grid: Grid, rack: list[str]) -> list[Play]:
    """Every legal play, in a fixed order that does not depend on hashing."""
    counts = Counter(rack)
    first = rs.centre if is_empty(grid) else None
    across = _along(rs, grid, counts, first)
    transposed = [list(col) for col in zip(*grid, strict=True)]
    first_t = (first[1], first[0]) if first else None
    down = [
        [(c, r, t, b) for r, c, t, b in placed]
        for placed in _along(rs, transposed, counts, first_t)
    ]
    unique = {tuple(sorted(p)) for p in across + down}
    out = []
    for tiles in sorted(unique):
        word, where = describe(rs, grid, tiles)
        out.append(Play(tiles, score(rs, grid, tiles), word, where))
    return out
