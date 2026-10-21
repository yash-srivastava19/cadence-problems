"""The player cadence evolves. Each round it starts from the current champion.

It runs in its own process and is sent plain JSON each turn, so it sees only
what a player may see. Everything outside the markers stays put.
"""


# CADENCE:BEGIN
# CADENCE:BEGIN
def choose(view: dict, moves: list[dict]) -> int:
    """Return one of `moves`. `view` is everything this player may see."""
    import random
    from scrabble import tools

    if len(moves) == 1:
        return 0

    # Standard heuristic values for keeping tiles on the rack
    VAL = {
        "A": 1.0,
        "B": -2.0,
        "C": 0.5,
        "D": 0.5,
        "E": 2.5,
        "F": -1.5,
        "G": -1.0,
        "H": 0.5,
        "I": -0.5,
        "J": -3.0,
        "K": -2.0,
        "L": 1.0,
        "M": 0.5,
        "N": 2.0,
        "O": -1.0,
        "P": -0.5,
        "Q": -6.5,
        "R": 2.5,
        "S": 7.5,
        "T": 2.0,
        "U": -2.5,
        "V": -4.0,
        "W": -2.5,
        "X": 1.0,
        "Y": -1.0,
        "Z": -1.5,
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

    def get_leave_val(leave, b_size, u_score=0):
        if b_size == 0:
            if not leave:
                return 2.0 * u_score
            else:
                return -2.0 * sum(TILE_VALUES.get(c, 0) for c in leave)
                
        if not leave:
            return 0.0
            
        leave_val = 0.0
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
            leave_val -= 12.0

        # Penalize duplicate letters
        counts = {}
        for char in leave:
            if char != "?":
                counts[char] = counts.get(char, 0) + 1
        for char, count in counts.items():
            if count > 1:
                if char in ("E", "S", "T", "R", "L", "N", "A"):
                    penalty = 1.0
                elif char in ("O", "I", "U", "V", "W", "Y", "B", "C", "D", "F", "G", "P", "H", "M"):
                    penalty = 2.5
                else:
                    penalty = 3.5
                leave_val -= (count - 1) * penalty

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
            ideal_v = total * 0.43
            leave_val -= abs(vowels - ideal_v) * 2.0
            if vowels == 0 and total >= 2:
                leave_val -= 2.0
            if consonants == 0 and total >= 2:
                leave_val -= 2.0
            
        return leave_val

    # Fast evaluation of all moves using the champion's heuristic
    fast_candidates = []
    for idx, move in enumerate(moves):
        score = move["score"]
        leave = [c.upper() for c in move["leave"]] if move["leave"] is not None else []

        if bag_size == 0:
            leave_val = get_leave_val(leave, 0, unseen_score)
            fast_utility = score + leave_val
        else:
            leave_val = get_leave_val(leave, bag_size)
            fast_utility = score + leave_val * leave_weight

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

        fast_utility -= tws_penalty
        fast_candidates.append((fast_utility, score, move["kind"] == "play", idx, move))

    fast_candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)

    # Determine simulation resources dynamically based on state to fit the time budget
    num_blanks_unseen = 0
    if hasattr(unseen, "get"):
        num_blanks_unseen = unseen.get("?", 0)
    elif hasattr(unseen, "__iter__"):
        num_blanks_unseen = sum(1 for c in unseen if c == "?")

    if bag_size == 0:
        if num_blanks_unseen > 0:
            num_candidates = 8
        else:
            num_candidates = 16
        num_worlds = 1
    elif bag_size < 12:
        if num_blanks_unseen > 0:
            num_candidates = 4
            num_worlds = 3
        else:
            num_candidates = 6
            num_worlds = 4
    else:
        if num_blanks_unseen > 0:
            num_candidates = 3
            num_worlds = 3
        else:
            num_candidates = 5
            num_worlds = 4

    if num_blanks_unseen >= 2:
        if bag_size == 0:
            num_candidates = 4
        else:
            num_candidates = 2
            num_worlds = 2

    # Filter candidates to only those within 20 points of the best fast utility
    best_fast_util = fast_candidates[0][0]
    candidates = [c for c in fast_candidates[:num_candidates] if best_fast_util - c[0] < 20.0]
    if not candidates:
        candidates = fast_candidates[:1]

    if len(candidates) == 1:
        return candidates[0][3]

    # Seed the RNG to guarantee identical decisions for identical views
    rng = random.Random(view["cgp"])
    worlds = [tools.sample_world(view["cgp"], rng) for _ in range(num_worlds)]

    best_idx = fast_candidates[0][3]
    best_sim_utility = -float("inf")

    for fast_util, score, is_play, idx, move in candidates:
        leave = [c.upper() for c in move["leave"]] if move["leave"] is not None else []
        our_rack_val_after_move = sum(TILE_VALUES.get(c, 0) for c in leave)
        total_utility = 0.0
        for w in worlds:
            after = tools.play(w, idx)
            if tools.over(after):
                utility = tools.spread(after, view["me"])
            else:
                opp_moves = tools.legal(after)
                if not opp_moves:
                    our_leave_val = get_leave_val(leave, bag_size, unseen_score)
                    our_leave_contrib = our_leave_val if bag_size == 0 else our_leave_val * leave_weight
                    utility = tools.spread(after, view["me"]) + our_leave_contrib
                else:
                    opp_bag_size = max(0, bag_size - (7 - len(leave)))
                    opp_leave_weight = max(0.0, min(1.0, opp_bag_size / 7.0))
                    
                    best_opp_val = -float('inf')
                    for om in opp_moves:
                        om_leave = [c.upper() for c in om["leave"]] if om["leave"] is not None else []
                        om_leave_val = get_leave_val(om_leave, opp_bag_size, our_rack_val_after_move)
                        if opp_bag_size == 0:
                            om_val = om["score"] + om_leave_val
                        else:
                            om_val = om["score"] + om_leave_val * opp_leave_weight
                        if om_val > best_opp_val:
                            best_opp_val = om_val
                            
                    our_leave_val = get_leave_val(leave, bag_size, unseen_score)
                    our_leave_contrib = our_leave_val if bag_size == 0 else our_leave_val * leave_weight
                    
                    utility = tools.spread(after, view["me"]) - best_opp_val + our_leave_contrib
            total_utility += utility
            
        avg_utility = total_utility / num_worlds
        tie_breaker = (avg_utility, score, is_play)
        if tie_breaker > (best_sim_utility, moves[best_idx]["score"], moves[best_idx]["kind"] == "play"):
            best_sim_utility = avg_utility
            best_idx = idx

    return best_idx
# CADENCE:END
# CADENCE:END