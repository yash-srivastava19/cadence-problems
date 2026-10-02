"""A ruleset: tiles, board and word list, read from one config file.

Nothing here knows which language it is. A tile is a token from the config,
usually one letter but not always, and every word in the word list is split
into those tokens before anything else sees it.
"""

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BLANK = "?"
END = ""  # the trie key that marks a complete word


@dataclass(frozen=True)
class Ruleset:
    name: str
    tokens: tuple[str, ...]
    counts: dict[str, int]
    values: dict[str, int]
    blanks: int
    premiums: tuple[str, ...]
    rack: int
    bingo: int
    exchange_min_bag: int
    scoreless_turns: int
    trie: dict
    words: frozenset[tuple[str, ...]]

    @property
    def size(self) -> int:
        return len(self.premiums)

    @property
    def centre(self) -> tuple[int, int]:
        for r, row in enumerate(self.premiums):
            if "*" in row:
                return r, row.index("*")
        raise ValueError("the board has no centre square '*'")

    def value(self, token: str, blank: bool = False) -> int:
        return 0 if blank or token == BLANK else self.values[token]

    def full_set(self) -> list[str]:
        """Every tile in the game, in a fixed order."""
        tiles = [t for t in self.tokens for _ in range(self.counts[t])]
        return tiles + [BLANK] * self.blanks


def tokenize(word: str, tokens: tuple[str, ...]) -> tuple[str, ...] | None:
    """Split a word into tokens, longest token first. None if it cannot be."""
    by_length = sorted(tokens, key=len, reverse=True)
    out, i = [], 0
    while i < len(word):
        for t in by_length:
            if word.startswith(t, i):
                out.append(t)
                i += len(t)
                break
        else:
            return None
    return tuple(out)


def _fetch(path: Path, url: str, sha256: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response:
        data = response.read()
    got = hashlib.sha256(data).hexdigest()
    if got != sha256:
        raise RuntimeError(f"{url} has sha256 {got}, expected {sha256}")
    path.write_bytes(data)


def load(config: str | Path) -> Ruleset:
    config = Path(config)
    spec = json.loads(config.read_text())
    lexicon = spec["lexicon"]
    path = config.parent / lexicon["file"]
    if not path.exists():
        _fetch(path, lexicon["url"], lexicon["sha256"])

    tokens = tuple(sorted(spec["tiles"]))
    trie: dict = {}
    words = set()
    for line in path.read_text().split():
        word = tokenize(line.strip().upper(), tokens)
        if word is None or len(word) < 2:
            continue
        words.add(word)
        node = trie
        for t in word:
            node = node.setdefault(t, {})
        node[END] = True

    rules = spec["rules"]
    return Ruleset(
        name=spec["name"],
        tokens=tokens,
        counts={t: c for t, (c, _) in spec["tiles"].items()},
        values={t: v for t, (_, v) in spec["tiles"].items()},
        blanks=spec["blanks"],
        premiums=tuple(spec["board"]),
        rack=rules["rack"],
        bingo=rules["bingo"],
        exchange_min_bag=rules["exchange_min_bag"],
        scoreless_turns=rules["scoreless_turns"],
        trie=trie,
        words=frozenset(words),
    )
