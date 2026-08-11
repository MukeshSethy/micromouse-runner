"""
turn_planner.py - can the mouse get round the maze WITHOUT moving the motors?

The naive controller pivoted wherever it stood, which fails: the nose sweeps
99.48 mm about the wheelbase midpoint against an 84 mm cell half-width. But the
footprint's half-diagonal about its GEOMETRIC centre is only 80.26 mm, so the
robot fits in a cell at any orientation. The question is whether a smooth arc,
or a pivot from a chosen parking spot, keeps it clear.

Skid steer cannot move its pivot fore/aft: with both wheels on a side locked,
the instantaneous centre always lies on the lateral line through the wheelbase
midpoint. So the only freedom is WHERE the robot parks before it turns.
"""

import math

CELL, WALL, N = 180.0, 12.0, 16
FREE_HALF = (CELL - WALL) / 2.0          # 84.00

# footprint measured from the PIVOT (wheelbase midpoint), rev 6:
# track 122.12 over the mini-sumo wheels
FRONT, REAR, HALFW = 84.0, 36.0, 60.06

SEED = [20260810]


def rnd():
    SEED[0] = (SEED[0] * 1664525 + 1013904223) % (2 ** 32)
    return SEED[0] / 2 ** 32


def build_maze():
    wV = [[True] * N for _ in range(N + 1)]
    wH = [[True] * (N + 1) for _ in range(N)]
    seen = [[False] * N for _ in range(N)]
    st = [(0, 0)]
    seen[0][0] = True
    while st:
        c, r = st[-1]
        nb = []
        if r + 1 < N and not seen[c][r + 1]: nb.append((c, r + 1, 0))
        if c + 1 < N and not seen[c + 1][r]: nb.append((c + 1, r, 1))
        if r - 1 >= 0 and not seen[c][r - 1]: nb.append((c, r - 1, 2))
        if c - 1 >= 0 and not seen[c - 1][r]: nb.append((c - 1, r, 3))
        if not nb:
            st.pop(); continue
        nc, nr, d = nb[int(rnd() * len(nb))]
        if d == 0: wH[c][r + 1] = False
        if d == 1: wV[c + 1][r] = False
        if d == 2: wH[c][r] = False
        if d == 3: wV[c][r] = False
        seen[nc][nr] = True
        st.append((nc, nr))
    for _ in range(40):
        c = 1 + int(rnd() * (N - 2)); r = 1 + int(rnd() * (N - 2))
        if rnd() < 0.5: wV[c][r] = False
        else: wH[c][r] = False
    wV[8][7] = wV[8][8] = False
    wH[7][8] = wH[8][8] = False
    wV[1][0] = True; wH[0][1] = False
    for r in range(N): wV[0][r] = True; wV[N][r] = True
    for c in range(N): wH[c][0] = True; wH[c][N] = True
    return wV, wH


def wall_rects(wV, wH):
    h = WALL / 2.0
    out = []
    for c in range(N + 1):
        for r in range(N):
            if wV[c][r]:
                out.append((c*CELL-h, r*CELL, c*CELL+h, (r+1)*CELL))
    for c in range(N):
        for r in range(N + 1):
            if wH[c][r]:
                out.append((c*CELL, r*CELL-h, (c+1)*CELL, r*CELL+h))
    for c in range(N + 1):
        for r in range(N + 1):
            out.append((c*CELL-h-.5, r*CELL-h-.5, c*CELL+h+.5, r*CELL+h+.5))
    return out


DX, DY = [0, 1, 0, -1], [1, 0, -1, 0]


def flood(wV, wH, targets):
    f = [[9999] * N for _ in range(N)]
    q = list(targets)
    for c, r in targets: f[c][r] = 0
    i = 0
    while i < len(q):
        c, r = q[i]; i += 1
        for d in range(4):
            if d == 0 and wH[c][r+1]: continue
            if d == 1 and wV[c+1][r]: continue
            if d == 2 and wH[c][r]: continue
            if d == 3 and wV[c][r]: continue
            nc, nr = c + DX[d], r + DY[d]
            if not (0 <= nc < N and 0 <= nr < N): continue
            if f[nc][nr] > f[c][r] + 1:
                f[nc][nr] = f[c][r] + 1; q.append((nc, nr))
    return f


def foot_pts(px, py, th):
    c, s = math.cos(th), math.sin(th)
    pts = []
    for i in range(9):
        t = -REAR + (FRONT + REAR) * i / 8.0
        for b in (HALFW, -HALFW):
            pts.append((px + t*c - b*s, py + t*s + b*c))
    for i in range(1, 8):
        b = -HALFW + 2*HALFW*i/8.0
        for t in (FRONT, -REAR):
            pts.append((px + t*c - b*s, py + t*s + b*c))
    return pts


def hash_rects(rects):
    """Bucket walls by cell. Testing every point against all ~1100 rects is
    ~37k comparisons per pose, which is far too slow for a pose search."""
    grid = {}
    for R in rects:
        x0, y0, x1, y1 = R
        for cc in range(int(x0 // CELL), int(x1 // CELL) + 1):
            for rr in range(int(y0 // CELL), int(y1 // CELL) + 1):
                grid.setdefault((cc, rr), []).append(R)
    return grid


def clear(px, py, th, grid):
    for (qx, qy) in foot_pts(px, py, th):
        for (x0, y0, x1, y1) in grid.get((int(qx // CELL), int(qy // CELL)), ()):
            if x0 < qx < x1 and y0 < qy < y1:
                return False
    return True


def arc_ok(cx, cy, d0, d1, R, rects, steps=26):
    """Pivot follows an arc of radius R tangent to both cell centrelines."""
    a0 = math.atan2(DY[d0], DX[d0]); a1 = math.atan2(DY[d1], DX[d1])
    da = a1 - a0
    while da > math.pi: da -= 2*math.pi
    while da < -math.pi: da += 2*math.pi
    sgn = 1.0 if da > 0 else -1.0
    nx, ny = -math.sin(a0)*sgn, math.cos(a0)*sgn
    ox, oy = cx - R*math.cos(a0) , cy - R*math.sin(a0)     # arc start
    ccx, ccy = ox + R*nx, oy + R*ny                        # arc centre
    for k in range(steps + 1):
        t = k/steps
        ang = math.atan2(oy-ccy, ox-ccx) + sgn*abs(da)*t
        px = ccx + R*math.cos(ang); py = ccy + R*math.sin(ang)
        th = a0 + da*t
        if not clear(px, py, th, rects):
            return False
    return True


def pivot_ok(cx, cy, d0, d1, rects, steps=22):
    """Search a parking offset along the incoming/outgoing axes."""
    a0 = math.atan2(DY[d0], DX[d0]); a1 = math.atan2(DY[d1], DX[d1])
    da = a1 - a0
    while da > math.pi: da -= 2*math.pi
    while da < -math.pi: da += 2*math.pi
    best = None
    for u in [x*8.0 for x in range(-11, 12)]:
        for v in [x*8.0 for x in range(-11, 12)]:
            px = cx + u*math.cos(a0) + v*math.cos(a1)
            py = cy + u*math.sin(a0) + v*math.sin(a1)
            ok = True
            for k in range(steps + 1):
                if not clear(px, py, a0 + da*k/steps, rects):
                    ok = False; break
            if ok:
                d = math.hypot(u, v)
                if best is None or d < best[0]:
                    best = (d, u, v)
    return best


def main():
    wV, wH = build_maze()
    rects = hash_rects(wall_rects(wV, wH))
    GOAL = [(7, 7), (8, 7), (7, 8), (8, 8)]
    f = flood(wV, wH, GOAL)

    # route
    c, r, path = 0, 0, [(0, 0)]
    while f[c][r] > 0 and len(path) < 400:
        best, bv = -1, 1e9
        for d in range(4):
            if d == 0 and wH[c][r+1]: continue
            if d == 1 and wV[c+1][r]: continue
            if d == 2 and wH[c][r]: continue
            if d == 3 and wV[c][r]: continue
            nc, nr = c + DX[d], r + DY[d]
            if not (0 <= nc < N and 0 <= nr < N): continue
            if f[nc][nr] < bv: bv = f[nc][nr]; best = d
        if best < 0: break
        c, r = c + DX[best], r + DY[best]
        path.append((c, r))
    print("route: %d cells, %d long" % (len(path), f[0][0]))

    hd = []
    for i in range(len(path) - 1):
        dc = path[i+1][0]-path[i][0]; dr = path[i+1][1]-path[i][1]
        hd.append(0 if dr > 0 else 2 if dr < 0 else 1 if dc > 0 else 3)

    RADII = [90.0, 80.0, 70.0, 60.0, 50.0, 40.0]
    stat = {"straight": 0, "arc": 0, "pivot": 0, "FAIL": 0}
    radhist = {}
    fails = []
    for i in range(len(hd) - 1):
        d0, d1 = hd[i], hd[i+1]
        if d0 == d1:
            stat["straight"] += 1; continue
        cc, rr = path[i+1]
        cx, cy = cc*CELL + CELL/2, rr*CELL + CELL/2
        done = False
        for R in RADII:
            if arc_ok(cx, cy, d0, d1, R, rects):
                stat["arc"] += 1; radhist[R] = radhist.get(R, 0) + 1
                done = True; break
        if done: continue
        pk = pivot_ok(cx, cy, d0, d1, rects)
        if pk:
            stat["pivot"] += 1
        else:
            stat["FAIL"] += 1; fails.append((cc, rr, d0, d1))

    print("\nturn analysis over the whole route")
    print("  straight-through : %d" % stat["straight"])
    print("  smooth arc       : %d   radii used %s"
          % (stat["arc"], {k: v for k, v in sorted(radhist.items())}))
    print("  parked pivot     : %d" % stat["pivot"])
    print("  IMPOSSIBLE       : %d" % stat["FAIL"])
    if fails:
        print("   at cells: %s" % fails[:8])

    print("\nsanity, footprint about its own centre:")
    print("  half-diagonal %.2f vs cell half %.2f"
          % (math.hypot((FRONT+REAR)/2, HALFW), FREE_HALF))
    print("  nose sweep about the PIVOT %.2f" % math.hypot(FRONT, HALFW))

    # can it U-turn anywhere?
    print("\nU-turn (180 deg) feasibility, grouped by how open the cell is:")
    bucket = {}
    for cc in range(N):
        for rr in range(N):
            opens = sum(1 for d in range(4)
                        if not (wH[cc][rr+1] if d == 0 else
                                wV[cc+1][rr] if d == 1 else
                                wH[cc][rr] if d == 2 else wV[cc][rr]))
            cx, cy = cc*CELL+CELL/2, rr*CELL+CELL/2
            ok = pivot_ok(cx, cy, 0, 2, rects) is not None
            t, o = bucket.get(opens, (0, 0))
            bucket[opens] = (t + 1, o + (1 if ok else 0))
    names = {1: "dead end", 2: "corridor/corner", 3: "T junction", 4: "crossroads"}
    for k in sorted(bucket):
        t, o = bucket[k]
        print("  %-16s (%d open) : %3d of %3d  (%.0f%%)"
              % (names.get(k, "?"), k, o, t, 100.0*o/max(t, 1)))


if __name__ == "__main__":
    main()
