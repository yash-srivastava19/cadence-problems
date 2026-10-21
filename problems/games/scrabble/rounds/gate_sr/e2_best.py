"""The player cadence evolves. Each round it starts from the current champion.

It runs in its own process and is sent plain JSON each turn, so it sees only
what a player may see. Everything outside the markers stays put.
"""


# CADENCE:BEGIN
def choose(view: dict, moves: list[dict]) -> int:
    """Return one of `moves`. `view` is everything this player may see."""
    # Standard heuristic values for keeping tiles on the rack
    VAL = {
        "A": 1.0,
        "B": -2.0,
        "C": -0.5,
        "D": 0.5,
        "E": 2.5,
        "F": -1.5,
        "G": -0.5,
        "H": 1.0,
        "I": 0.5,
        "J": -2.5,
        "K": -1.5,
        "L": 1.0,
        "M": 1.0,
        "N": 1.5,
        "O": -0.5,
        "P": 0.5,
        "Q": -6.0,
        "R": 2.0,
        "S": 8.0,
        "T": 1.5,
        "U": -1.5,
        "V": -3.5,
        "W": -2.0,
        "X": 1.5,
        "Y": -0.5,
        "Z": -2.0,
        "?": 25.0,
    }

    # Standard Scrabble letter values for endgame penalty/bonus calculations
    TILE_VALUES = {
        "A": 1,
        "B": 3,
        "C": 3,
        "D": 2,
        "E": 1,
        "F": 4,
        "G": 2,
        "H": 4,
        "I": 1,
        "J": 8,
        "K": 5,
        "L": 1,
        "M": 3,
        "N": 1,
        "O": 1,
        "P": 3,
        "Q": 10,
        "R": 1,
        "S": 1,
        "T": 1,
        "U": 1,
        "V": 4,
        "W": 4,
        "X": 8,
        "Y": 4,
        "Z": 10,
        "?": 0,
    }

    VOWELS = {"A", "E", "I", "O", "U"}

    bag_size = view.get("bag", 100)
    if hasattr(bag_size, "__len__"):
        bag_size = len(bag_size)

    # Scale leave value importance based on how many tiles are left in the bag
    leave_weight = max(0.0, min(1.0, bag_size / 7.0))
    grid = view.get("grid")
    TWS = {(0, 0), (0, 7), (0, 14), (7, 0), (7, 14), (14, 0), (14, 7), (14, 14)}

    if grid:
        open_tws_board = {pos for pos in TWS if grid[pos[0]][pos[1]] is None}
    else:
        open_tws_board = TWS.copy()

    # In the endgame, unseen tiles represent exactly the opponent's rack
    unseen_score = 0
    unseen = view.get("unseen", {})
    if hasattr(unseen, "items"):
        for char, count in unseen.items():
            unseen_score += TILE_VALUES.get(char.upper(), 0) * count
    elif hasattr(unseen, "__iter__"):
        for char in unseen:
            unseen_score += TILE_VALUES.get(char.upper(), 0)

    move_candidates = []

    for idx, move in enumerate(moves):
        score = move["score"]
        leave = [c.upper() for c in move["leave"]] if move["leave"] is not None else []

        if bag_size == 0:
            if not leave:
                # Going out gives us the opponent's tile values, and they lose them (2x swing)
                leave_val = 2.0 * unseen_score
            else:
                # Penalize remaining tiles on our rack to mitigate opponent going out
                leave_val = -2.0 * sum(TILE_VALUES.get(c, 0) for c in leave)
            utility = score + leave_val
        else:
            leave_val = 0.0
            if leave:
                has_q = "Q" in leave
                has_u = "U" in leave
                for char in leave:
                    val = VAL.get(char, 0.0)
                    if char == "Q" and has_u:
                        val = 2.0
                    elif char == "U" and has_q:
                        val = 1.0
                    leave_val += val

                if has_q and not has_u:
                    leave_val -= 8.0

                # Penalize duplicate letters
                counts = {}
                for char in leave:
                    if char != "?":
                        counts[char] = counts.get(char, 0) + 1
                for char, count in counts.items():
                    if count > 1:
                        leave_val -= (count - 1) * (1.0 if char == "S" else 2.5)

                # Maintain a healthy vowel/consonant balance (target ~43% vowels)
                vowels = 0
                consonants = 0
                for c in leave:
                    if c in VOWELS:
                        vowels += 1
                    elif c != "?":
                        consonants += 1

                total = vowels + consonants
                if total > 1:
                    ideal_v = round(total * 0.43)
                    leave_val -= abs(vowels - ideal_v) * 2.0

            utility = score + leave_val * leave_weight

        # Defensive check: Avoid opening empty Triple Word Score squares
        tws_penalty = 0.0
        if move["kind"] == "play" and move["tiles"] and grid:
            move_coords = {(t[0], t[1]) for t in move["tiles"]}
            tws_dists = {}
            for r, col, _, _ in move["tiles"]:
                if r in (0, 7, 14):
                    for tc in (0, 7, 14):
                        if (r, tc) in open_tws_board and (r, tc) not in move_coords:
                            dist = abs(col - tc)
                            if 1 <= dist <= 3:
                                step = 1 if tc > col else -1
                                blocked = False
                                for c_mid in range(col + step, tc, step):
                                    if grid[r][c_mid] is not None:
                                        blocked = True
                                        break
                                if not blocked:
                                    tws_dists[(r, tc)] = min(
                                        tws_dists.get((r, tc), 99), dist
                                    )
                if col in (0, 7, 14):
                    for tr in (0, 7, 14):
                        if (tr, col) in open_tws_board and (tr, col) not in move_coords:
                            dist = abs(r - tr)
                            if 1 <= dist <= 3:
                                step = 1 if tr > r else -1
                                blocked = False
                                for r_mid in range(r + step, tr, step):
                                    if grid[r_mid][col] is not None:
                                        blocked = True
                                        break
                                if not blocked:
                                    tws_dists[(tr, col)] = min(
                                        tws_dists.get((tr, col), 99), dist
                                    )

            for (tr, tc), dist in tws_dists.items():
                tws_penalty += 10.0 if dist == 1 else (5.0 if dist == 2 else 3.0)

        utility -= tws_penalty
        move_candidates.append((idx, utility, leave_val))

    # Sort move candidates by heuristic utility descending
    move_candidates.sort(key=lambda x: x[1], reverse=True)

    # Count blanks to dynamically adjust search depth and avoid timeouts
    our_blanks = sum(1 for c in view.get("rack", []) if c == "?")
    unseen_blanks = 0
    if hasattr(unseen, "get"):
        unseen_blanks = unseen.get("?", 0)
    elif hasattr(unseen, "__iter__"):
        unseen_blanks = sum(1 for c in unseen if c == "?")
    total_blanks = our_blanks + unseen_blanks

    if bag_size > 0:
        if total_blanks >= 3:
            S, K = 1, 4
        elif total_blanks >= 2:
            S, K = 2, 4
        else:
            S, K = 3, 5
    else:
        # Endgame: only 1 possible world exists (no hidden tiles)
        S = 1
        if total_blanks >= 2:
            K = 8
        else:
            K = 15

    K = min(K, len(moves))

    from scrabble import tools
    import random

    rng = random.Random(view["cgp"])
    sampled_worlds = [tools.sample_world(view["cgp"], rng) for _ in range(S)]

    best_move_idx = move_candidates[0][0]
    best_tie_breaker = (-float("inf"), -float("inf"), False)

    for idx, base_ut, leave_val in move_candidates[:K]:
        spreads = []
        for world in sampled_worlds:
            after = tools.play(world, idx)
            if tools.over(after):
                spreads.append(tools.spread(after, view["me"]))
            else:
                opp_moves = tools.legal(after)
                if not opp_moves:
                    spreads.append(tools.spread(after, view["me"]))
                else:
                    if bag_size == 0:
                        # Fully play out and minimize our final spread to simulate perfect opponent play
                        min_spread = min(
                            tools.spread(tools.play(after, opp_move), view["me"])
                            for opp_move in opp_moves
                        )
                        spreads.append(min_spread)
                    else:
                        # Fast approximation of opponent's greedy response
                        opp_best_score = max(opp_move["score"] for opp_move in opp_moves)
                        spreads.append(tools.spread(after, view["me"]) - opp_best_score)

        avg_spread = sum(spreads) / len(spreads)
        final_utility = avg_spread + leave_val * leave_weight

        tie_breaker = (final_utility, moves[idx]["score"], moves[idx]["kind"] == "play")
        if tie_breaker > best_tie_breaker:
            best_tie_breaker = tie_breaker
            best_move_idx = idx

    return best_move_idx
# CADENCE:END