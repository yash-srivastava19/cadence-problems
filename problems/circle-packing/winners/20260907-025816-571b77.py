"""Pack 26 circles into the unit square, as large as they will go.

Only the marked region is yours to change. The count, the constraints, and
how the score is computed live in score.py and stay put -- two runs that
scored themselves differently would not be comparable.

Return a list of (x, y, r). Nothing else is read.
"""


# CADENCE:BEGIN
import math
import os
import random


def pack(n: int) -> list[tuple[float, float, float]]:
    """Optimized circle packing into the unit square.

    Uses an exact Primal Simplex LP solver for maximum sum of radii given center positions,
    dual shadow prices for exact parameter gradients, high-speed CPython list comprehensions,
    multi-stage Adam exploration, bottleneck-targeted basin-hopping, and accelerated coordinate
    pattern search refinement.
    """
    rng = random.Random(int(os.environ.get("CADENCE_SEED", 0)))

    def solve_lp_radii(
        x: list[float], y: list[float], compute_grads: bool = True
    ) -> tuple[
        list[float],
        float,
        list[float] | None,
        list[float] | None,
    ]:
        """Solves LP max sum(r_i) s.t. r_i <= b_i, r_i + r_j <= d_ij using Simplex.

        Optimized using CPython zip-vectorization and conditional gradient evaluation.
        """
        b = [0.0] * n
        b_side = [0] * n  # 0: left, 1: right, 2: bottom, 3: top
        for i in range(n):
            xi, yi = x[i], y[i]
            val = xi
            side = 0
            if 1.0 - xi < val:
                val = 1.0 - xi
                side = 1
            if yi < val:
                val = yi
                side = 2
            if 1.0 - yi < val:
                val = 1.0 - yi
                side = 3
            b[i] = max(1e-8, val)
            b_side[i] = side

        pairs = []
        for i in range(n):
            xi, yi, bi = x[i], y[i], b[i]
            for j in range(i + 1, n):
                dist = math.hypot(xi - x[j], yi - y[j])
                if dist < bi + b[j]:
                    pairs.append((i, j, dist))

        num_b = n
        num_p = len(pairs)
        M = num_b + num_p
        N = n
        W = N + M + 1

        tableau = [[0.0] * W for _ in range(M + 1)]

        for i in range(n):
            tableau[i][i] = 1.0
            tableau[i][N + i] = 1.0
            tableau[i][-1] = b[i]

        for k, (i, j, dist) in enumerate(pairs):
            row = num_b + k
            tableau[row][i] = 1.0
            tableau[row][j] = 1.0
            tableau[row][N + row] = 1.0
            tableau[row][-1] = dist

        cost_row = tableau[M]
        for i in range(n):
            cost_row[i] = -1.0

        basis = [N + k for k in range(M)]

        max_pivots = 4 * M + 60
        for _ in range(max_pivots):
            pivot_col = -1
            min_val = -1e-9
            c_row = tableau[M]
            for j in range(N + M):
                v = c_row[j]
                if v < min_val:
                    min_val = v
                    pivot_col = j

            if pivot_col == -1:
                break

            min_ratio = 1e18
            pivot_row = -1
            for i in range(M):
                row = tableau[i]
                val = row[pivot_col]
                if val > 1e-10:
                    ratio = row[-1] / val
                    if ratio < min_ratio:
                        min_ratio = ratio
                        pivot_row = i

            if pivot_row == -1:
                break

            p_row = tableau[pivot_row]
            inv_pivot = 1.0 / p_row[pivot_col]
            p_row = [v * inv_pivot for v in p_row]
            tableau[pivot_row] = p_row

            for i in range(M + 1):
                if i != pivot_row:
                    row = tableau[i]
                    factor = row[pivot_col]
                    if factor > 1e-11 or factor < -1e-11:
                        tableau[i] = [
                            rv - factor * pv for rv, pv in zip(row, p_row)
                        ]

            basis[pivot_row] = pivot_col

        r = [0.0] * n
        for i in range(M):
            if basis[i] < N:
                r[basis[i]] = max(0.0, tableau[i][-1])

        score = sum(r)

        if not compute_grads:
            return r, score, None, None

        duals_b = [max(0.0, tableau[M][N + i]) for i in range(n)]
        duals_p = [max(0.0, tableau[M][N + num_b + k]) for k in range(num_p)]

        gx = [0.0] * n
        gy = [0.0] * n

        for i in range(n):
            w = duals_b[i]
            if w > 1e-9:
                s = b_side[i]
                if s == 0:
                    gx[i] += w
                elif s == 1:
                    gx[i] -= w
                elif s == 2:
                    gy[i] += w
                elif s == 3:
                    gy[i] -= w

        for k, (i, j, dist) in enumerate(pairs):
            w = duals_p[k]
            if w > 1e-9 and dist > 1e-8:
                dx = x[i] - x[j]
                dy = y[i] - y[j]
                fac = w / dist
                gx[i] += dx * fac
                gy[i] += dy * fac
                gx[j] -= dx * fac
                gy[j] -= dy * fac

        return r, score, gx, gy

    def optimize_config(
        x_in: list[float],
        y_in: list[float],
        steps: int = 80,
        lr_start: float = 0.018,
        lr_end: float = 0.003,
    ) -> tuple[float, list[float], list[float], list[float]]:
        x = list(x_in)
        y = list(y_in)
        mx, vx = [0.0] * n, [0.0] * n
        my, vy = [0.0] * n, [0.0] * n
        b1, b2, eps = 0.85, 0.98, 1e-8

        best_s = -1.0
        best_x = list(x)
        best_y = list(y)
        best_r = [0.0] * n

        for step in range(1, steps + 1):
            r, score, gx, gy = solve_lp_radii(x, y, compute_grads=True)
            if score > best_s:
                best_s = score
                best_x = list(x)
                best_y = list(y)
                best_r = list(r)

            progress = step / steps
            lr = lr_start * ((lr_end / lr_start) ** progress)
            b1_t = b1**step
            b2_t = b2**step

            for i in range(n):
                mx[i] = b1 * mx[i] + (1 - b1) * gx[i]
                vx[i] = b2 * vx[i] + (1 - b2) * (gx[i] * gx[i])
                m_hat_x = mx[i] / (1 - b1_t)
                v_hat_x = vx[i] / (1 - b2_t)
                x[i] += lr * m_hat_x / (math.sqrt(v_hat_x) + eps)
                x[i] = max(0.005, min(0.995, x[i]))

                my[i] = b1 * my[i] + (1 - b1) * gy[i]
                vy[i] = b2 * vy[i] + (1 - b2) * (gy[i] * gy[i])
                m_hat_y = my[i] / (1 - b1_t)
                v_hat_y = vy[i] / (1 - b2_t)
                y[i] += lr * m_hat_y / (math.sqrt(v_hat_y) + eps)
                y[i] = max(0.005, min(0.995, y[i]))

        return best_s, best_x, best_y, best_r

    # Generating initial layout configurations
    configs = []

    # 1. Hexagonal row patterns
    row_patterns = [
        [5, 6, 5, 6, 4],
        [6, 5, 6, 5, 4],
        [5, 5, 6, 5, 5],
        [4, 6, 6, 6, 4],
        [5, 6, 6, 5, 4],
        [6, 6, 5, 5, 4],
        [4, 5, 6, 6, 5],
        [5, 5, 5, 5, 6],
        [6, 5, 5, 5, 5],
        [5, 6, 5, 5, 5],
        [4, 5, 5, 6, 6],
        [4, 5, 6, 5, 6],
        [6, 5, 4, 5, 6],
        [4, 6, 5, 6, 5],
    ]
    for pattern in row_patterns:
        num_rows = len(pattern)
        x_init, y_init = [], []
        for r_idx, row_cols in enumerate(pattern):
            cy = (r_idx + 0.5) / num_rows
            shift = 0.25 / row_cols if r_idx % 2 == 1 else 0.0
            for c_idx in range(row_cols):
                if len(x_init) >= n:
                    break
                cx = (c_idx + 0.5) / row_cols + shift
                x_init.append(max(0.05, min(0.95, cx)))
                y_init.append(max(0.05, min(0.95, cy)))
        while len(x_init) < n:
            x_init.append(rng.uniform(0.1, 0.9))
            y_init.append(rng.uniform(0.1, 0.9))
        configs.append((x_init, y_init))

        xj = [
            max(0.05, min(0.95, xi + rng.uniform(-0.02, 0.02))) for xi in x_init
        ]
        yj = [
            max(0.05, min(0.95, yi + rng.uniform(-0.02, 0.02))) for yi in y_init
        ]
        configs.append((xj, yj))

    # 2. Grid configurations
    for cols, rows in [
        (5, 6),
        (6, 5),
        (5, 5),
        (4, 7),
        (7, 4),
        (3, 9),
        (9, 3),
        (4, 6),
        (6, 4),
    ]:
        x_init, y_init = [], []
        cnt = 0
        for r_idx in range(rows):
            for c_idx in range(cols):
                if cnt >= n:
                    break
                cx = (c_idx + 0.5) / cols + (rng.random() - 0.5) * 0.015
                cy = (r_idx + 0.5) / rows + (rng.random() - 0.5) * 0.015
                x_init.append(max(0.05, min(0.95, cx)))
                y_init.append(max(0.05, min(0.95, cy)))
                cnt += 1
        while len(x_init) < n:
            x_init.append(rng.uniform(0.1, 0.9))
            y_init.append(rng.uniform(0.1, 0.9))
        configs.append((x_init, y_init))

    # 3. Fibonacci Spirals
    phi = (1.0 + 5.0**0.5) / 2.0
    for scale in [0.28, 0.32, 0.36, 0.40, 0.44]:
        for phase in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            x_init, y_init = [], []
            for i in range(n):
                radius = scale * math.sqrt((i + 0.5) / n)
                angle = 2.0 * math.pi * (i + phase) / (phi**2)
                cx = 0.5 + radius * math.cos(angle)
                cy = 0.5 + radius * math.sin(angle)
                x_init.append(max(0.05, min(0.95, cx)))
                y_init.append(max(0.05, min(0.95, cy)))
            configs.append((x_init, y_init))

    # 4. Concentric Ring Structures with large inner circle(s)
    for big_r in [0.22, 0.26, 0.30]:
        x_init, y_init = [0.5], [0.5]
        r_inner = 0.09
        dist_inner = big_r + r_inner + 0.01
        for i in range(8):
            ang = 2.0 * math.pi * i / 8.0
            x_init.append(
                max(0.05, min(0.95, 0.5 + dist_inner * math.cos(ang)))
            )
            y_init.append(
                max(0.05, min(0.95, 0.5 + dist_inner * math.sin(ang)))
            )
        rem = n - len(x_init)
        dist_outer = 0.42
        for i in range(rem):
            ang = 2.0 * math.pi * i / rem + 0.2
            x_init.append(
                max(0.05, min(0.95, 0.5 + dist_outer * math.cos(ang)))
            )
            y_init.append(
                max(0.05, min(0.95, 0.5 + dist_outer * math.sin(ang)))
            )
        configs.append((x_init, y_init))

    # 5. Multi-big-circle templates
    for c2_x1, c2_x2 in [(0.33, 0.67), (0.35, 0.65)]:
        x_init, y_init = [c2_x1, c2_x2], [0.5, 0.5]
        for i in range(n - 2):
            ang = 2.0 * math.pi * i / (n - 2)
            r_dist = 0.35 if i % 2 == 0 else 0.42
            x_init.append(max(0.05, min(0.95, 0.5 + r_dist * math.cos(ang))))
            y_init.append(max(0.05, min(0.95, 0.5 + r_dist * math.sin(ang))))
        configs.append((x_init, y_init))

    # 6. Random Uniform Seeds
    for _ in range(10):
        x_init = [rng.uniform(0.08, 0.92) for _ in range(n)]
        y_init = [rng.uniform(0.08, 0.92) for _ in range(n)]
        configs.append((x_init, y_init))

    # Stage 1: Fast screening of initial layouts
    screened = []
    for x_c, y_c in configs:
        score, x_opt, y_opt, r_opt = optimize_config(
            x_c, y_c, steps=45, lr_start=0.022, lr_end=0.005
        )
        screened.append((score, x_opt, y_opt, r_opt))

    screened.sort(key=lambda item: item[0], reverse=True)

    # Stage 2: Full Adam optimization on top candidates
    candidates = []
    for cand_score, x_c, y_c, r_c in screened[:12]:
        score, x_opt, y_opt, r_opt = optimize_config(
            x_c, y_c, steps=90, lr_start=0.015, lr_end=0.002
        )
        candidates.append((score, x_opt, y_opt, r_opt))

    candidates.sort(key=lambda item: item[0], reverse=True)

    # Stage 3: Targeted Basin-Hopping on top candidates
    refined_candidates = []
    for cand_score, x_c, y_c, r_c in candidates[:6]:
        best_score = cand_score
        best_x = list(x_c)
        best_y = list(y_c)
        best_r = list(r_c)

        for _ in range(8):
            px = list(best_x)
            py = list(best_y)
            avg_r = sum(best_r) / n

            # Perturb bottleneck (small) circles with higher probability
            for i in range(n):
                if best_r[i] < 0.85 * avg_r or rng.random() < 0.25:
                    mag = 0.06 if best_r[i] < 0.85 * avg_r else 0.03
                    px[i] = max(
                        0.02, min(0.98, px[i] + rng.uniform(-mag, mag))
                    )
                    py[i] = max(
                        0.02, min(0.98, py[i] + rng.uniform(-mag, mag))
                    )

            p_score, px_opt, py_opt, pr_opt = optimize_config(
                px, py, steps=60, lr_start=0.012, lr_end=0.002
            )
            if p_score > best_score:
                best_score = p_score
                best_x = list(px_opt)
                best_y = list(py_opt)
                best_r = list(pr_opt)

        refined_candidates.append((best_score, best_x, best_y, best_r))

    refined_candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_x, best_y, best_r = refined_candidates[0]

    # Stage 4: Fine Adam polish + Accelerated Coordinate Pattern Search
    _, best_x, best_y, best_r = optimize_config(
        best_x, best_y, steps=110, lr_start=0.003, lr_end=0.0003
    )

    deltas = [0.003, 0.001, 0.0004, 0.0001, 0.00003]
    dirs = [
        (1.0, 0.0),
        (-1.0, 0.0),
        (0.0, 1.0),
        (0.0, -1.0),
        (0.7071, 0.7071),
        (-0.7071, 0.7071),
        (0.7071, -0.7071),
        (-0.7071, -0.7071),
    ]

    curr_score = best_score
    curr_x = list(best_x)
    curr_y = list(best_y)
    curr_r = list(best_r)

    for delta in deltas:
        for _ in range(2):
            improved = False
            indices = list(range(n))
            # Sort indices so small circles are adjusted first
            indices.sort(key=lambda idx: curr_r[idx])

            for i in indices:
                orig_xi, orig_yi = curr_x[i], curr_y[i]
                best_xi, best_yi = orig_xi, orig_yi
                local_best_s = curr_score
                local_best_r = curr_r

                for dx, dy in dirs:
                    nx = orig_xi + dx * delta
                    ny = orig_yi + dy * delta
                    if 0.002 <= nx <= 0.998 and 0.002 <= ny <= 0.998:
                        curr_x[i] = nx
                        curr_y[i] = ny
                        cand_r, cand_s, _, _ = solve_lp_radii(
                            curr_x, curr_y, compute_grads=False
                        )
                        if cand_s > local_best_s + 1e-9:
                            local_best_s = cand_s
                            local_best_r = cand_r
                            best_xi, best_yi = nx, ny

                            # Direction acceleration step
                            ax = orig_xi + dx * delta * 1.5
                            ay = orig_yi + dy * delta * 1.5
                            if 0.002 <= ax <= 0.998 and 0.002 <= ay <= 0.998:
                                curr_x[i] = ax
                                curr_y[i] = ay
                                acc_r, acc_s, _, _ = solve_lp_radii(
                                    curr_x, curr_y, compute_grads=False
                                )
                                if acc_s > local_best_s + 1e-9:
                                    local_best_s = acc_s
                                    local_best_r = acc_r
                                    best_xi, best_yi = ax, ay

                        curr_x[i] = orig_xi
                        curr_y[i] = orig_yi

                if local_best_s > curr_score + 1e-9:
                    curr_x[i] = best_xi
                    curr_y[i] = best_yi
                    curr_score = local_best_s
                    curr_r = local_best_r
                    improved = True

            if not improved:
                break

    # Final feasibility guarantee with 1e-9 safety margin
    final_r, _, _, _ = solve_lp_radii(curr_x, curr_y, compute_grads=False)
    result = []
    for i in range(n):
        safe_r = max(1e-7, final_r[i] - 1e-9)
        result.append((curr_x[i], curr_y[i], safe_r))

    return result
# CADENCE:END