"""The leave bot with measured leave values (rounds/evidence/values.json):
points on the next turn per tile kept, against drawing a fresh one.
Vowel balance term dropped (not measured)."""

from collections import Counter

TILE = {"A": -0.74, "B": -2.55, "C": -1.38, "D": -1.16, "E": -0.44, "F": -1.62, "G": -2.95, "H": 0.87, "I": -1.79, "J": -1.96, "K": 0.28, "L": -1.76, "M": -0.25, "N": -1.14, "O": -1.74, "P": -1.37, "Q": 2.47, "R": -1.13, "S": 3.22, "T": -1.16, "U": -3.62, "V": -3.96, "W": -2.84, "X": 2.13, "Y": -0.27, "Z": 2.06, "?": 15.0}
DUP, Q_NO_U = -4.56, -8.43
VOWELS = set("AEIOU")


def leave_value(leave):
    if not leave:
        return 0.0
    value = sum(TILE.get(t, 0) for t in leave)
    value += DUP * sum(n - 1 for t, n in Counter(leave).items() if n > 1 and t != "?")
    if "Q" in leave and "U" not in leave:
        value += Q_NO_U
    return value


def choose(view, moves):
    weight = 1.0 if view["bag"] >= 7 else 0.5 if view["bag"] > 0 else 0.0
    best, best_key = 0, None
    for i, m in enumerate(moves):
        k = m["score"] + weight * leave_value(tuple(m["leave"]))
        if best_key is None or k > best_key:
            best, best_key = i, k
    return best
