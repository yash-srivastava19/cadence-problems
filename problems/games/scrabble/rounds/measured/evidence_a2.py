"""Leave bot with values measured in rounds/evidence_a2/values.json."""
from collections import Counter

V = {'(nothing kept)': 74.57, 'A': -0.91, 'B': -2.69, 'C': -0.68, 'D': -1.45, 'E': 0.32, 'F': -2.05, 'G': -4.8, 'H': 1.31, 'I': -2.18, 'J': -2.59, 'K': -2.16, 'L': -2.15, 'M': -0.49, 'N': -1.81, 'O': -2.18, 'P': -1.76, 'Q': 6.11, 'R': -0.8, 'S': 5.13, 'T': -1.73, 'U': -5.25, 'V': -5.88, 'W': -3.45, 'X': 2.85, 'Y': -0.76, 'Z': 1.86, '?': 19.16, 'each duplicate': -6.74, 'Q without U': -15.11}


def leave_value(leave):
    counts = Counter(leave)
    value = sum(V[t] * c for t, c in counts.items())
    value += V["each duplicate"] * sum(c - 1 for t, c in counts.items() if c > 1 and t != "?")
    if "Q" in counts and "U" not in counts:
        value += V["Q without U"]
    return value


def choose(view, moves):
    weight = 1.0 if view["bag"] >= 7 else 0.5 if view["bag"] > 0 else 0.0
    keys = [m["score"] + weight * leave_value(m["leave"]) for m in moves]
    return keys.index(max(keys))
