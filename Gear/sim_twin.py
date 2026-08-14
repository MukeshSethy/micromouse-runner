"""
sim_twin.py - exact offline twin of the viewer's physics + controller.

Same maze (same LCG seed), same friction model, same wall response, same
trajectory controller. Purpose: tune gains with a fast objective loop instead
of screenshot-guessing at a 14 fps headless browser, then port numbers back to
web/viewer_template.html. Keep the two in sync BY HAND - if you change one,
change the other.
"""

import math

CELL, WALL, N = 180.0, 12.0, 16
GOAL = [(7, 7), (8, 7), (7, 8), (8, 8)]
DX, DY = [0, 1, 0, -1], [1, 0, -1, 0]

# robot, rev 6
TRACK, FRONT, REAR = 120.12, 84.0, 36.0
HALFW = TRACK / 2.0
WHEEL_R = 13.5 / 1000.0
MASS, G = 0.22, 9.81
IZZ = MASS * (0.120 ** 2 + 0.107 ** 2) / 12.0
SREF = 0.06

_seed = [0]


def rnd():
    _seed[0] = (_seed[0] * 1664525 + 1013904223) % (2 ** 32)
    return _seed[0] / 2 ** 32


def build_maze(seed=20260810):
    _seed[0] = seed
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
        if c - 1 >= 0 and not seen[c - 1][r]: nb.append((c, r - 1, 3) if False else (c - 1, r, 3))
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


def build_maze_comp(seed=20260810):
    """
    Competition-styled layout: championship mazes are hand-designed with long
    straights and diagonal staircases. Route: 14-cell straight north, 14-cell
    straight east, then a 10-cell alternating staircase into the goal - the
    section a fast mouse runs as a diagonal. The rest of the board is filled
    with DFS branches off the route so it is still a proper maze.
    """
    _seed[0] = seed
    wV = [[True] * N for _ in range(N + 1)]
    wH = [[True] * (N + 1) for _ in range(N)]

    # Championship-length route, 67 moves: full-height west straight, full
    # top straight, a 20-move diagonal cutting the whole board, an
    # S-combination of short straights, and a second opposing diagonal in.
    route = [(0, r) for r in range(16)]                  # N straight, 16 cells
    route += [(c, 15) for c in range(1, 16)]             # E straight, 15 cells
    route += [(15, r) for r in (14, 13, 12)]             # short S drop
    c, r = 15, 12
    for k in range(20):                                  # 20-move SW diagonal
        if k % 2 == 0: c -= 1
        else: r -= 1
        route.append((c, r))                             # ends at (5, 2)
    route += [(4, 2), (3, 2), (2, 2)]                    # W straight
    route += [(2, 3), (2, 4), (2, 5)]                    # N straight
    c, r = 2, 5
    for k in range(6):                                   # 6-move NE diagonal
        if k % 2 == 0: c += 1
        else: r += 1
        route.append((c, r))                             # ends at (5, 8)
    route += [(6, 8), (7, 8)]                            # into the goal

    def carve(a, b):
        (c1, r1), (c2, r2) = a, b
        if c2 == c1 + 1: wV[c2][r1] = False
        elif c2 == c1 - 1: wV[c1][r1] = False
        elif r2 == r1 + 1: wH[c1][r2] = False
        else: wH[c1][r1] = False

    for i in range(len(route) - 1):
        carve(route[i], route[i + 1])

    # fill the rest as DFS branches hanging off the route
    seen = [[False] * N for _ in range(N)]
    for c, r in route: seen[c][r] = True
    st = list(route)
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
    # loops are only punched if they DON'T shorten start->goal: the designed
    # highway must stay the shortest route, like a real championship maze.
    # (Unguarded punching let the flood route shortcut through the middle and
    # skip the straights and staircase entirely.)
    wV[8][7] = wV[8][8] = False
    wH[7][8] = wH[8][8] = False
    base = flood(wV, wH, GOAL)[0][0]
    for _ in range(40):
        c = 1 + int(rnd() * (N - 2)); r = 1 + int(rnd() * (N - 2))
        vert = rnd() < 0.5
        arr = wV if vert else wH
        if not arr[c][r]:
            continue
        arr[c][r] = False
        if flood(wV, wH, GOAL)[0][0] < base:
            arr[c][r] = True                     # would shortcut - revert

    wV[1][0] = True; wH[0][1] = False
    for r in range(N): wV[0][r] = True; wV[N][r] = True
    for c in range(N): wH[c][0] = True; wH[c][N] = True
    return wV, wH


def flood(wV, wH, T):
    f = [[9999] * N for _ in range(N)]
    q = list(T)
    for c, r in T: f[c][r] = 0
    i = 0
    while i < len(q):
        c, r = q[i]; i += 1
        for d in range(4):
            blocked = (wH[c][r+1] if d == 0 else wV[c+1][r] if d == 1
                       else wH[c][r] if d == 2 else wV[c][r])
            if blocked: continue
            nc, nr = c + DX[d], r + DY[d]
            if not (0 <= nc < N and 0 <= nr < N): continue
            if f[nc][nr] > f[c][r] + 1:
                f[nc][nr] = f[c][r] + 1; q.append((nc, nr))
    return f


def make_path(wV, wH, turn_r=90.0, diag=False):
    f = flood(wV, wH, GOAL)
    c, r = 0, 0
    cells = [(90.0, 90.0)]
    while f[c][r] > 0 and len(cells) < 400:
        best, bv = -1, 1e9
        for d in range(4):
            blocked = (wH[c][r+1] if d == 0 else wV[c+1][r] if d == 1
                       else wH[c][r] if d == 2 else wV[c][r])
            if blocked: continue
            nc, nr = c + DX[d], r + DY[d]
            if not (0 <= nc < N and 0 <= nr < N): continue
            if f[nc][nr] < bv: bv = f[nc][nr]; best = d
        if best < 0: break
        c, r = c + DX[best], r + DY[best]
        cells.append((c * CELL + 90.0, r * CELL + 90.0))

    # ---- anchors: cell centres, with alternating-turn chains collapsed to
    # 45-degree DIAGONAL segments through the wall-gap centres (which are the
    # midpoints of adjacent cell centres, and are exactly collinear). This is
    # how real mice run staircases. Gated on the robot actually fitting the
    # 110.3 mm diagonal corridor.
    anchors = list(cells)
    if diag:
        moves = [(sgn(cells[i+1][0]-cells[i][0]),
                  sgn(cells[i+1][1]-cells[i][1])) for i in range(len(cells)-1)]
        anchors, i = [cells[0]], 0
        while i < len(moves):
            j = i
            while (j + 1 < len(moves) and moves[j+1] != moves[j]
                   and (j == i or moves[j+1] == moves[j-1])):
                j += 1
            if j - i + 1 >= 4:                    # >= 4 alternating moves
                mid = lambda k: ((cells[k][0]+cells[k+1][0])/2.0,
                                 (cells[k][1]+cells[k+1][1])/2.0)
                anchors.append(mid(i))            # diagonal entry
                anchors.append(mid(j))            # diagonal exit
                i = j + 1
                anchors.append(cells[i])
            else:
                i += 1
                anchors.append(cells[i])
        if anchors[-1] != cells[-1]:
            anchors.append(cells[-1])

    # ---- cubic BEZIER turns between anchor legs (any angle).
    # Endpoints are the same tangent points the old arc fillets used, and
    # the control legs use the circle-approximation length
    # c = (4/3)*tan(dang/4)*R, so the curve matches the verified R90/R70
    # arc geometry to <0.03% - clearances and the tuned gains carry over -
    # while every turn is a genuine polynomial Bezier with tangent-
    # continuous entry/exit.
    P = [anchors[0]]
    for i in range(1, len(anchors) - 1):
        a, b, c2 = anchors[i-1], anchors[i], anchors[i+1]
        v1 = (b[0]-a[0], b[1]-a[1]); l1 = math.hypot(*v1)
        v2 = (c2[0]-b[0], c2[1]-b[1]); l2 = math.hypot(*v2)
        if l1 < 1e-9 or l2 < 1e-9: continue
        u1 = (v1[0]/l1, v1[1]/l1); u2 = (v2[0]/l2, v2[1]/l2)
        cross = u1[0]*u2[1] - u1[1]*u2[0]
        dot = max(-1.0, min(1.0, u1[0]*u2[0] + u1[1]*u2[1]))
        if abs(cross) < 1e-6 and dot > 0:
            P.append(b); continue
        dang = math.acos(dot)                     # turn magnitude
        R = turn_r if dang > 1.2 else 70.0        # 90s at 90 mm, 45s at 70
        t = R * math.tan(dang / 2.0)
        tmax = 0.45 * min(l1, l2)
        if t > tmax:
            t = tmax; R = t / math.tan(dang / 2.0)
        sp = (b[0]-u1[0]*t, b[1]-u1[1]*t)        # curve entry
        ep = (b[0]+u2[0]*t, b[1]+u2[1]*t)        # curve exit
        cl = (4.0/3.0) * math.tan(dang/4.0) * R  # control-leg length
        c1 = (sp[0]+u1[0]*cl, sp[1]+u1[1]*cl)
        c2b = (ep[0]-u2[0]*cl, ep[1]-u2[1]*cl)
        P.append(sp)
        # 8 samples per turn, EXACTLY like the arc fillets before: the
        # 34 mm resampler only splits segments, never merges, so turn
        # sample spacing is an implicit tuning parameter - denser Bezier
        # sampling (12/turn) took the fast regime from 0 to 13 wall hits
        n = 8
        for k in range(1, n + 1):
            s = k / float(n); m = 1.0 - s
            P.append((m*m*m*sp[0] + 3*m*m*s*c1[0] + 3*m*s*s*c2b[0]
                      + s*s*s*ep[0],
                      m*m*m*sp[1] + 3*m*m*s*c1[1] + 3*m*s*s*c2b[1]
                      + s*s*s*ep[1]))
    P.append(anchors[-1])

    # resample ~34 mm then smooth twice (same as the viewer)
    Q = [P[0]]
    for i in range(1, len(P)):
        a, b = Q[-1], P[i]
        d = math.hypot(b[0]-a[0], b[1]-a[1])
        while d > 34.0:
            t = 34.0/d
            a = (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)
            Q.append(a); d = math.hypot(b[0]-a[0], b[1]-a[1])
        Q.append(b)
    Q = [list(p) for p in Q]
    for _ in range(2):
        for i in range(1, len(Q)-1):
            Q[i] = [(Q[i-1][0]+2*Q[i][0]+Q[i+1][0])/4,
                    (Q[i-1][1]+2*Q[i][1]+Q[i+1][1])/4]

    R_, K_ = [], []
    for i in range(len(Q)):
        if i == 0 or i == len(Q)-1:
            R_.append(1e6); K_.append(0.0); continue
        a, b, c2 = Q[i-1], Q[i], Q[i+1]
        ab = math.hypot(b[0]-a[0], b[1]-a[1])
        bc = math.hypot(c2[0]-b[0], c2[1]-b[1])
        ca = math.hypot(a[0]-c2[0], a[1]-c2[1])
        cross = (b[0]-a[0])*(c2[1]-a[1])-(b[1]-a[1])*(c2[0]-a[0])
        ar = abs(cross)/2
        R = 1e6 if ar < 1e-6 else (ab*bc*ca)/(4*ar)/1000.0
        R_.append(R)
        K_.append(0.0 if R >= 1e5 else math.copysign(1.0/R, cross))
    return Q, R_, K_


def sgn(v):
    return (v > 0) - (v < 0)


def wall_grid(wV, wH):
    walls = []
    h = WALL/2
    for c in range(N+1):
        for r in range(N):
            if wV[c][r]: walls.append((c*CELL-h, r*CELL, c*CELL+h, (r+1)*CELL))
    for c in range(N):
        for r in range(N+1):
            if wH[c][r]: walls.append((c*CELL, r*CELL-h, (c+1)*CELL, r*CELL+h))
    for c in range(N+1):
        for r in range(N+1):
            walls.append((c*CELL-h-.5, r*CELL-h-.5, c*CELL+h+.5, r*CELL+h+.5))
    grid = {}
    for w in walls:
        for cc in range(int(w[0]//CELL), int(w[2]//CELL)+1):
            for rr in range(int(w[1]//CELL), int(w[3]//CELL)+1):
                grid.setdefault((cc, rr), []).append(w)
    return grid


FOOT = []
for i in range(7):
    t = -REAR + (FRONT+REAR)*i/6
    FOOT.append((t, HALFW)); FOOT.append((t, -HALFW))
for i in range(1, 6):
    b = -HALFW + 2*HALFW*i/6
    FOOT.append((FRONT, b)); FOOT.append((-REAR, b))


# Real N20s are never matched: a few percent between sides is typical. This is
# what the gyro loop exists to cancel - without it an open-loop diff drive
# veers and weaves.
MOTOR_TRIM_L, MOTOR_TRIM_R = 1.02, 0.985

# ---- motor + inner speed loop -------------------------------------------
# Wheel speed used to be an IDEAL velocity source: commanded = achieved,
# instantly. Real N20s cannot do that; the encoders exist so firmware can run
# a per-side speed PI that turns setpoints into PWM duty. Model per SIDE
# (both wheels on a side are locked together by the gear train):
#   T = trim*duty*T_STALL - (T_STALL/W_FREE)*w - R*F_long   on   J_EFF
# W_FREE 75 rad/s ~= 1.0 m/s top speed. T_STALL 0.12 N.m per side at the
# wheel (N20 stall through the 2.105 stage, x2 motors' gearing headroom).
# J_EFF is dominated by rotor inertia reflected through the squared ratio.
# Trim scales the torque constant, so motor mismatch now emerges physically.
# J_EFF sanity-bounded by observed micromouse accelerations: competition
# mice pull 5+ m/s^2, which needs wheel accel > 370 rad/s^2, so the reflected
# inertia cannot exceed ~2e-4 per side at this stall torque.
W_FREE, T_STALL, J_EFF = 75.0, 0.10, 2.0e-4
PI_KP, PI_KI = 0.35, 8.0          # duty per rad/s (per rad) - tuned below


class Sim:
    def __init__(self, gains, seed=20260810, gyro=True, trim=True):
        # wheel variant: mini-sumo barrel as-is (19.06 -> track 120.12) or
        # trimmed to 8 mm (track 98: fits the 110.3 diagonal corridor AND
        # stays inside the 100 mm PCB)
        narrow = bool(gains.get("narrow"))
        # motor variant: stock N20 (~1500 rpm at the gearbox, tops out at
        # 1.0 m/s at the wheel) or the high-RPM N20 (~4500 rpm class). Faster
        # winding = proportionally less stall torque; reflected inertia falls
        # with the square of the internal ratio. No PID can pass the back-EMF
        # ceiling - 3 m/s is a MOTOR choice, then a tune.
        fast = bool(gains.get("fast"))
        self.WF = 245.0 if fast else W_FREE
        self.TS = 0.031 if fast else T_STALL
        self.JE = 1.9e-5 if fast else J_EFF
        self.halfw = 49.0 if narrow else HALFW
        self.trackm = (2*self.halfw)/1000.0
        wy = (41.0 + (8.0 if narrow else 19.06)/2.0)/1000.0
        self.WH_B = [wy, -wy, wy, -wy]
        self.FOOT = []
        for i in range(7):
            t2 = -REAR + (FRONT+REAR)*i/6
            self.FOOT.append((t2, self.halfw))
            self.FOOT.append((t2, -self.halfw))
        for i in range(1, 6):
            b2 = -self.halfw + 2*self.halfw*i/6
            self.FOOT.append((FRONT, b2)); self.FOOT.append((-REAR, b2))
        self.diag_ok = (2*self.halfw) <= 106.0   # 110.3 corridor - margin
        self.gyro = gyro
        self.trimL = MOTOR_TRIM_L if trim else 1.0
        self.trimR = MOTOR_TRIM_R if trim else 1.0
        self.gn = gains
        wV, wH = (build_maze_comp(seed) if gains.get("comp")
                  else build_maze(seed))
        self.grid = wall_grid(wV, wH)
        self.P, self.PR, self.PK = make_path(
            wV, wH, turn_r=gains.get("turnr", 90.0),
            diag=self.diag_ok and bool(gains.get("diag")))
        self.x, self.y, self.th = 90.0, 90.0, math.pi/2
        # Heading ESTIMATE. Gyro ON: the IMU tracks true heading (BNO055-class
        # drift is negligible over a run). Gyro OFF: encoder odometry only -
        # (wr-wl)*R/B from real wheel speeds, which is blind to tyre slip, and
        # skid-steer scrubs in EVERY turn, so the estimate walks off arc by arc.
        self.th_est = math.pi/2
        self.u = self.v = self.r = 0.0
        self.wl = self.wr = 0.0
        self.wal = self.war = 0.0   # achieved wheel speeds
        self.iL = self.iR = 0.0     # PI integrators
        self.pathI = 0
        self.hits = 0; self.stuck = 0.0; self.recover = 0.0
        self.crash = 0.0
        self.t = 0.0; self.dist = 0.0
        self.leg_start_dist = 0.0

    def control(self):
        g = self.gn
        # closest point
        bi, bd = self.pathI, 1e18
        for i in range(self.pathI, min(len(self.P), self.pathI+45)):
            d = math.hypot(self.P[i][0]-self.x, self.P[i][1]-self.y)
            if d < bd: bd, bi = d, i
        self.pathI = bi
        # lookahead point
        acc, j = 0.0, bi
        while j < len(self.P)-1 and acc < g["look"]:
            acc += math.hypot(self.P[j+1][0]-self.P[j][0],
                              self.P[j+1][1]-self.P[j][1])
            j += 1
        tgt = self.P[j]
        i0 = min(bi, len(self.P)-2)
        p0, p1 = self.P[i0], self.P[i0+1]
        tx, ty = p1[0]-p0[0], p1[1]-p0[1]
        tl = math.hypot(tx, ty) or 1.0
        th_use = self.th if self.gyro else self.th_est
        e = (tx*(self.y-p0[1]) - ty*(self.x-p0[0]))/tl/1000.0
        he = math.atan2(ty, tx) - th_use
        while he > math.pi: he -= 2*math.pi
        while he < -math.pi: he += 2*math.pi
        dx, dy = tgt[0]-self.x, tgt[1]-self.y
        hd = math.atan2(dy, dx) - th_use
        while hd > math.pi: hd -= 2*math.pi
        while hd < -math.pi: hd += 2*math.pi

        # braking window scales with speed: from v the stop distance at
        # ~4.2 m/s^2 is v^2/8.4 - a fixed 260 mm window overruns corners
        # arriving off a long straight
        # +400 not +250: braking must FINISH ~100 mm before the arc, or the
        # leftover longitudinal slip eats the friction circle at turn-in
        need = max(g["brake_d"], (self.u*self.u)/8.4*1000.0 + 400.0)
        ud, rmin, bd2 = g["vmax"], 1e6, 0.0
        i = self.pathI
        while i < len(self.PR)-1 and bd2 < need:
            rmin = min(rmin, self.PR[i])
            bd2 += math.hypot(self.P[i+1][0]-self.P[i][0],
                              self.P[i+1][1]-self.P[i][1])
            i += 1
        ud = min(ud, math.sqrt(g["fmarg"]*g.get("mu", 1.10)*G*max(0.02, rmin)))
        # motor feasibility: the outer wheel in an arc needs v*(1+B/2R) and
        # saturates at the back-EMF ceiling when grip no longer brakes corners
        ud = min(ud, 0.92*self.WF*WHEEL_R
                 / (1.0 + (self.trackm/2.0)/max(0.02, rmin)))
        if abs(hd) > 1.1: ud = min(ud, 0.20)
        # launch slip limiter: commanding full speed from rest saturates the
        # friction circle longitudinally, leaving NO lateral grip for an arc
        # that starts at the stop - the tyres spin straight into the wall
        ud = min(ud, abs(self.u) + g.get("slew", 0.15))
        # departure creep: hold 0.30 m/s for the first 250 mm after a stop so
        # the feedback settles before speed arrives
        if self.leg_start_dist > 0 and self.dist - self.leg_start_dist < 0.25:
            ud = min(ud, 0.30)

        if self.recover > 0:
            self.wl = self.wr = -0.25/WHEEL_R
            return

        kFF, accd, i = 0.0, 0.0, i0
        while i < len(self.PK)-1 and accd < g["ff_d"]:
            if abs(self.PK[i]) > abs(kFF): kFF = self.PK[i]
            accd += math.hypot(self.P[i+1][0]-self.P[i][0],
                               self.P[i+1][1]-self.P[i][1])
            i += 1
        # diagonal discipline: on 45-degree tangents the corridor margin is
        # ~6 mm/side, so slow down and stiffen the tracking servo - exactly
        # what real mice do entering a diagonal chain
        diag_here = abs(abs(math.atan2(ty, tx)) % (math.pi/2) - math.pi/4) < 0.12
        kmul = self.gn.get("kmul", 2.2) if diag_here else 1.0
        if diag_here: ud = min(ud, g.get("vdiag", 0.55))
        # no throttle until aligned: corner-exit overshoot (~12 deg) plus hard
        # acceleration speared the wall on every 1.0 m/s exit
        if abs(he) > 0.10: ud = min(ud, 0.50)
        v = max(0.12, abs(self.u))
        # feedback authority ramps in with speed: at launch atan2(k*e, v)
        # divides by near-zero v, so millimetres of error commanded full lock -
        # that veer cost 6-8 hits departing every stop
        # authority ramps in at launch AND schedules down with speed: the
        # feedback-to-yaw path multiplies by v, so fixed gains that are stable
        # at 0.8 weave to a crash mid-straight at 1.0
        auth = min(1.0, abs(self.u)/0.25)

        kap = (kFF*g["kff"]
               + auth*(g["kp"]*hd/(max(60.0, math.hypot(dx, dy))/1000.0)
                       + g["kh"]*he*kmul
                       - math.atan2(g["ke"]*kmul*e, v)*g["ka"]))
        kap = max(-16.0, min(16.0, kap))
        # yaw-rate clamp: 14 rad/s silently caps every R90 corner at
        # 1.26 m/s (r = v/R), which is what kept the race-glue regime slow.
        # But a FIXED higher clamp destabilizes the straights: at the
        # back-EMF ceiling the motors have no differential authority left,
        # and commanding it anyway just saturates the duty and winds the
        # PIs. So the clamp follows the plant: what differential the
        # motors can actually deliver at this speed, floored at the old 14.
        rdmax = self.gn.get("rdmax", 14.0)
        if rdmax > 14.0:
            ceil_v = 0.92 * self.WF * WHEEL_R
            rdmax = min(rdmax,
                        max(14.0, 2.0 * (ceil_v - abs(self.u))
                            / max(0.02, self.trackm)))
        rd = max(-rdmax, min(rdmax, kap*ud))
        # gyro yaw-rate lead: with a lagged motor plant the commanded
        # differential must anticipate; this is the classic micromouse
        # gyro-D term. (On the old ideal-wheel plant it destabilized.)
        if self.gyro:
            rd = rd + self.gn.get("krd", 0.0)*(rd - self.r)
            rd = max(-rdmax, min(rdmax, rd))
        B = self.trackm
        self.wl = (ud - rd*B/2)/WHEEL_R
        self.wr = (ud + rd*B/2)/WHEEL_R

    def resolve_walls(self):
        c, s = math.cos(self.th), math.sin(self.th)
        xp = xn = yp = yn = 0.0
        any_ = False
        for (a, b) in self.FOOT:
            px = self.x + a*c - b*s
            py = self.y + a*s + b*c
            for w in self.grid.get((int(px//CELL), int(py//CELL)), ()):
                if px <= w[0] or px >= w[2] or py <= w[1] or py >= w[3]:
                    continue
                any_ = True
                dl, dr = px-w[0], w[2]-px
                db, dt = py-w[1], w[3]-py
                m = min(dl, dr, db, dt)
                if m == dl: xn = max(xn, dl)
                elif m == dr: xp = max(xp, dr)
                elif m == db: yn = max(yn, db)
                else: yp = max(yp, dt)
        if not any_:
            return False
        push_x = xp if xp > xn else -xn
        push_y = yp if yp > yn else -yn
        self.x += push_x; self.y += push_y
        L = math.hypot(push_x, push_y)
        if L > 1e-9:
            nx, ny = push_x/L, push_y/L
            vwx = self.u*c - self.v*s
            vwy = self.u*s + self.v*c
            dot = vwx*nx + vwy*ny
            if dot < 0:
                vwx -= dot*nx; vwy -= dot*ny
            vwx *= 0.72; vwy *= 0.72
            self.u = vwx*c + vwy*s
            self.v = -vwx*s + vwy*c
        self.r *= 0.5
        return True

    WH_A = [14.75/1000]*2 + [-14.75/1000]*2
    WH_B = [ (41.0+19.06/2)/1000, -(41.0+19.06/2)/1000]*2
    SIDE = [1, -1, 1, -1]

    def _dyn(self, dt):
        """Motors + tyres + body: shared by step() and _step_physics().
        self.wl/wr are SETPOINTS; self.wal/war are achieved wheel speeds."""
        MU = self.gn.get("mu", 1.10)
        Nf = MASS*G/4
        # tyre forces from ACHIEVED wheel speeds
        Fx = Fy = Mz = 0.0
        f_long = [0.0, 0.0]                    # per side, for reaction torque
        for i in range(4):
            om = self.wal if self.SIDE[i] > 0 else self.war
            vx = self.u - self.r*self.WH_B[i]
            vy = self.v + self.r*self.WH_A[i]
            sx, sy = vx - om*WHEEL_R, vy
            sm = math.hypot(sx, sy)
            f = MU*Nf*min(1.0, sm/SREF)
            if sm > 1e-6:
                fx, fy = -f*sx/sm, -f*sy/sm
                Fx += fx; Fy += fy
                Mz += self.WH_A[i]*fy - self.WH_B[i]*fx
                f_long[0 if self.SIDE[i] > 0 else 1] += fx
        # per-side PI speed loop -> duty -> DC motor torque -> wheel accel
        for s_, (cmd, act, integ, trim, fl) in enumerate((
                (self.wl, self.wal, self.iL, self.trimL, f_long[0]),
                (self.wr, self.war, self.iR, self.trimR, f_long[1]))):
            err = cmd - act
            integ = max(-0.6/PI_KI, min(0.6/PI_KI, integ + err*dt))
            duty = max(-1.0, min(1.0, PI_KP*err + PI_KI*integ))
            # wheel pushes floor with -f_long reaction; +fl drives the BODY,
            # so -fl*R loads the wheel
            T = trim*duty*self.TS - (self.TS/self.WF)*act + fl*WHEEL_R
            act = act + (T/self.JE)*dt
            if s_ == 0: self.wal, self.iL = act, integ
            else: self.war, self.iR = act, integ
        du = Fx/MASS + self.r*self.v
        dv = Fy/MASS - self.r*self.u
        self.u += du*dt; self.v += dv*dt; self.r += (Mz/IZZ)*dt
        self.x += (self.u*math.cos(self.th) - self.v*math.sin(self.th))*dt*1000
        self.y += (self.u*math.sin(self.th) + self.v*math.cos(self.th))*dt*1000
        self.th += self.r*dt
        # encoder-odometry heading: encoders read ACHIEVED wheel speed exactly
        # (trim and lag included) but stay blind to contact-patch slip
        self.th_est += ((self.war - self.wal)*WHEEL_R/(TRACK/1000.0))*dt
        self.dist += abs(self.u)*dt
        self.t += dt

    def step(self, dt):
        if self.recover > 0: self.recover -= dt
        self.control()
        self._dyn(dt)
        touch = self.resolve_walls()
        if touch:
            if self.crash < 0.02: self.hits += 1
            self.crash = min(1.0, self.crash + dt*6)
            if math.hypot(self.u, self.v) < 0.03:
                self.stuck += dt
            else:
                self.stuck = max(0.0, self.stuck - dt*2)
        else:
            self.crash = max(0.0, self.crash - dt*1.6)
            self.stuck = max(0.0, self.stuck - dt*2)
        if self.stuck > 0.7:
            self.stuck = 0.0; self.recover = 0.55
            self.leg_start_dist = self.dist   # creep on re-departure too

    def run(self, tmax=90.0):
        n = len(self.P)
        while self.t < tmax:
            self.step(0.002)
            if self.pathI >= n - 2:
                return {"done": True, "t": self.t, "hits": self.hits,
                        "dist": self.dist}
        return {"done": False, "t": self.t, "hits": self.hits,
                "dist": self.dist, "at": self.pathI/(n-1)}

    def run_mission(self, legs=2, tmax=120.0):
        """Brake on arrival, pause, reverse the path, run again - the same
        terminal behaviour as the viewer. Returns per-leg stats."""
        out = []
        done_legs = 0
        pause = 0.0
        braking = False
        turning = False
        while self.t < tmax and done_legs < legs:
            if braking:
                self.wl = self.wr = 0.0
                # step physics only (control skipped): coast to rest
                self._step_physics(0.002)
                if math.hypot(self.u, self.v) < 0.03:
                    pause += 0.002
                    if pause > 0.6:
                        out.append({"leg": done_legs + 1, "t": self.t,
                                    "hits": self.hits,
                                    "stopped_speed": math.hypot(self.u, self.v)})
                        self.P.reverse(); self.PR.reverse()
                        self.PK.reverse()
                        self.PK = [-k for k in self.PK]
                        self.pathI = 0
                        braking = False; pause = 0.0
                        done_legs += 1
                        turning = True
                        self.leg_start_dist = self.dist
                continue
            if turning:
                # gyro-guided about-turn to face the reversed path before
                # driving; without this the mouse scrambled through 180 deg
                # while moving and took 14 hits leaving the goal
                p0, p3 = self.P[0], self.P[min(3, len(self.P)-1)]
                tgt = math.atan2(p3[1]-p0[1], p3[0]-p0[0])
                err = tgt - self.th
                while err > math.pi: err -= 2*math.pi
                while err < -math.pi: err += 2*math.pi
                if abs(err) < 0.05:
                    turning = False
                else:
                    w = math.copysign(0.30, err)/WHEEL_R
                    self.wl, self.wr = -w, w
                    self._step_physics(0.002)
                    continue
            self.step(0.002)
            endP = self.P[-1]
            if (self.pathI >= len(self.P) - 3 and
                    math.hypot(endP[0]-self.x, endP[1]-self.y) < 45.0):
                braking = True
        return out

    def _step_physics(self, dt):
        """Dynamics without the trajectory controller - braking / turning."""
        self._dyn(dt)
        self.resolve_walls()


BASE = dict(vmax=0.80, fmarg=0.32, brake_d=260.0, ff_d=100.0,
            kff=1.0, kp=0.45, kh=1.2, ke=2.6, ka=1.8, look=115.0)

if __name__ == "__main__":
    import itertools, sys
    res = Sim(BASE).run()
    print("base gains:", res)
    if not res["done"] or res["hits"] > 0:
        print("\nsweeping...")
        best = None
        for kff, kh, ke_ka, look, fm in itertools.product(
                (0.8, 1.0, 1.2), (0.8, 1.2, 1.8), ((2.6, 1.8), (1.6, 1.2),
                (4.0, 2.4)), (90.0, 115.0, 150.0), (0.25, 0.32, 0.40)):
            g = dict(BASE, kff=kff, kh=kh, ke=ke_ka[0], ka=ke_ka[1],
                     look=look, fmarg=fm)
            r = Sim(g).run()
            score = ((0 if r["done"] else 100) + r["hits"]*10 + r["t"])
            if best is None or score < best[0]:
                best = (score, g, r)
                print(" new best", r, {k: g[k] for k in
                      ("kff", "kh", "ke", "ka", "look", "fmarg")})
        print("\nBEST:", best[2])
        print("gains:", {k: best[1][k] for k in
              ("kff", "kh", "ke", "ka", "look", "fmarg")})
