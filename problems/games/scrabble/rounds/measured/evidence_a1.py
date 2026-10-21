"""Leave bot with values measured in rounds/evidence_a1/values.json."""
from collections import Counter

V = {'(nothing kept)': 38.93, 'A': -0.67, 'B': -2.16, 'C': -0.46, 'D': -1.16, 'E': 0.38, 'F': -1.74, 'G': -3.15, 'H': 0.88, 'I': -1.48, 'J': -1.91, 'K': -1.76, 'L': -1.51, 'M': -0.38, 'N': -1.11, 'O': -1.97, 'P': -1.0, 'Q': 4.43, 'R': -0.45, 'S': 3.73, 'T': -1.22, 'U': -4.02, 'V': -4.35, 'W': -2.68, 'X': 1.94, 'Y': -0.35, 'Z': 1.71, '?': 13.9, 'each duplicate': -5.72, 'Q without U': -10.57}


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
