"""The player cadence evolves. Each round it starts from the current champion.

It runs in its own process and is sent plain JSON each turn, so it sees only
what a player may see. Everything outside the markers stays put.
"""


# CADENCE:BEGIN
def choose(view: dict, moves: list[dict]) -> int:
    """Return one of `moves`. `view` is everything this player may see."""
    # Standard heuristic values for keeping tiles on the rack
    VAL = {
        'A': 1.0, 'B': -2.0, 'C': -0.5, 'D': 0.5, 'E': 2.5, 'F': -1.5, 'G': -0.5,
        'H': 1.0, 'I': 0.5, 'J': -2.5, 'K': -1.5, 'L': 1.0, 'M': 1.0, 'N': 1.5,
        'O': -0.5, 'P': 0.5, 'Q': -6.0, 'R': 2.0, 'S': 8.0, 'T': 1.5, 'U': -1.5,
        'V': -3.5, 'W': -2.0, 'X': 1.5, 'Y': -0.5, 'Z': -2.0, '?': 25.0
    }
    
    # Standard Scrabble letter values for endgame penalty/bonus calculations
    TILE_VALUES = {
        'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 2, 'H': 4, 'I': 1,
        'J': 8, 'K': 5, 'L': 1, 'M': 3, 'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1,
        'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8, 'Y': 4, 'Z': 10, '?': 0
    }
    
    VOWELS = {'A', 'E', 'I', 'O', 'U'}
    
    bag_size = view.get("bag", 100)
    if hasattr(bag_size, "__len__"):
        bag_size = len(bag_size)
    
    # Scale leave value importance based on how many tiles are left in the bag
    leave_weight = max(0.0, min(1.0, bag_size / 7.0))
    grid = view.get("grid")
    TWS = {(0,0), (0,7), (0,14), (7,0), (7,14), (14,0), (14,7), (14,14)}
    
    if grid:
        open_tws_board = {pos for pos in TWS if grid[pos[0]][pos[1]] is None}
    else:
        open_tws_board = TWS.copy()
    
    # In the endgame, unseen tiles represent exactly the opponent's rack
    unseen_score = 0
    if bag_size == 0:
        unseen = view.get("unseen", {})
        if hasattr(unseen, "items"):
            for char, count in unseen.items():
                unseen_score += TILE_VALUES.get(char.upper(), 0) * count
        elif hasattr(unseen, "__iter__"):
            for char in unseen:
                unseen_score += TILE_VALUES.get(char.upper(), 0)
    
    # Smooth transition to endgame
    # If bag_size <= 8, we start factoring in the endgame rack-point penalty
    weight_endgame = max(0.0, min(1.0, (8 - bag_size) / 8.0))
    weight_midgame = 1.0 - weight_endgame

    best_move = moves[0]
    best_utility = -float('inf')
    
    for move in moves:
        score = move["score"]
        leave = [c.upper() for c in move["leave"]] if move["leave"] is not None else []
        
        # Calculate mid-game leave value
        mid_game_val = 0.0
        if leave:
            has_q = 'Q' in leave
            has_u = 'U' in leave
            for char in leave:
                val = VAL.get(char, 0.0)
                if char == 'Q' and has_u:
                    val = 2.0
                elif char == 'U' and has_q:
                    val = 1.0
                mid_game_val += val
            
            if has_q and not has_u:
                mid_game_val -= 8.0
            
            # Penalize duplicate letters
            counts = {}
            for char in leave:
                if char != '?':
                    counts[char] = counts.get(char, 0) + 1
            for char, count in counts.items():
                if count > 1:
                    mid_game_val -= (count - 1) * (1.0 if char == 'S' else 2.5)
            
            # Maintain a healthy vowel/consonant balance (target ~43% vowels)
            vowels = sum(1 for c in leave if c in VOWELS)
            consonants = sum(1 for c in leave if c not in VOWELS and c != '?')
            blanks = sum(1 for c in leave if c == '?')
            total = vowels + consonants + blanks
            if total > 1:
                ideal_v = round(total * 0.43)
                # Find the best assignment of blanks to vowels/consonants to minimize penalty
                best_diff = 99
                for v_blank in range(blanks + 1):
                    diff = abs((vowels + v_blank) - ideal_v)
                    if diff < best_diff:
                        best_diff = diff
                mid_game_val -= best_diff * 2.0

        # Calculate endgame leave value
        if not leave:
            if bag_size == 0:
                endgame_val = 2.0 * unseen_score
            else:
                endgame_val = 0.0
        else:
            endgame_val = -2.0 * sum(TILE_VALUES.get(c, 0) for c in leave)
            
        # Combine mid-game and endgame leave values
        leave_val = weight_midgame * (mid_game_val * leave_weight) + weight_endgame * endgame_val
        utility = score + leave_val
        
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
                                    tws_dists[(r, tc)] = min(tws_dists.get((r, tc), 99), dist)
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
                                    tws_dists[(tr, col)] = min(tws_dists.get((tr, col), 99), dist)
            
            for (tr, tc), dist in tws_dists.items():
                tws_penalty += (10.0 if dist == 1 else (5.0 if dist == 2 else 3.0))
        
        utility -= tws_penalty
        
        # Tie-breaker prioritizes play moves and raw score if utility is identical
        tie_breaker = (utility, score, move["kind"] == "play")
        if best_move is None or tie_breaker > (best_utility, best_move["score"], best_move["kind"] == "play"):
            best_utility = utility
            best_move = move
            
    return moves.index(best_move)
# CADENCE:END