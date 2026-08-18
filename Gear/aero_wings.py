"""
aero_wings.py - actually simulate wings and diffusers instead of assuming
a lift coefficient.

Earlier I costed downforce from literature CL values. Fair challenge: that
is an assumption, not a test. This builds real geometry onto the robot's
side-view silhouette - a rear wing at incidence, an upswept underbody
diffuser, and both - and MEASURES the force on the body by momentum
exchange across the bounce-back links, which is the standard LBM way to
get forces.

Caveats stated up front, because they cut in the design's favour and it
still loses:
  * 2D. No tip vortices, no finite-span downwash, so 2D lift is
    OPTIMISTIC versus a real wing of this aspect ratio - typically by
    2-4x. If 2D says the force is negligible, 3D is worse.
  * lattice Re ~ 1e3 against the real 4e4 at 5 m/s. Separation behaviour
    is only indicative.
  * CL is reported against the robot's plan area so it drops straight
    into the downforce sums used elsewhere in the report.

    python aero_wings.py   -> aero_wings.json
"""

import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PX = 0.5                    # mm per mask cell, before downsampling
RHO = 1.204
W_ROBOT = 0.22 * 9.81
A_PLAN = 0.0129             # m2
V_CORNER = 1.19


def downsample(mask, k):
    ny, nx = mask.shape
    ny2, nx2 = ny // k, nx // k
    return mask[:ny2*k, :nx2*k].reshape(ny2, k, nx2, k).any(axis=(1, 3))


def add_wing(mask, mm_per_cell, chord_mm=26.0, aoa_deg=-12.0,
             height_mm=20.0, x_from_tail_mm=6.0, t_mm=1.6):
    """Rear wing: an inclined plate above the tail on two struts. Negative
    incidence = pushing DOWN (the sign an inverted wing runs at)."""
    m = mask.copy()
    ny, nx = m.shape
    c = chord_mm / mm_per_cell
    t = max(1, int(round(t_mm / mm_per_cell)))
    h = int(round(height_mm / mm_per_cell))
    # body top row at the tail end
    cols = np.where(m.any(axis=0))[0]
    tail = cols[-1]
    top = np.where(m[:, tail-3:tail].any(axis=1))[0].max()
    x0 = int(tail - x_from_tail_mm/mm_per_cell - c)
    a = math.radians(aoa_deg)
    for s in range(int(c)):
        xx = x0 + s
        yy = top + h + int(round(-s*math.tan(a)))
        if 0 <= xx < nx:
            for d in range(t):
                if 0 <= yy+d < ny:
                    m[yy+d, xx] = True
    # two struts
    for sx in (x0 + int(0.25*c), x0 + int(0.8*c)):
        yy = top + h + int(round(-(sx-x0)*math.tan(a)))
        if 0 <= sx < nx:
            m[top:min(ny, yy+1), sx:min(nx, sx+2)] = True
    return m


def add_diffuser(mask, mm_per_cell, ramp_mm=42.0, exit_rise_mm=9.0,
                 t_mm=1.4):
    """Underbody diffuser: a plate under the tail sweeping up from the
    ride-height plane to an exit, i.e. an expanding channel."""
    m = mask.copy()
    ny, nx = m.shape
    cols = np.where(m.any(axis=0))[0]
    tail = cols[-1]
    bot = np.where(m[:, tail-3:tail].any(axis=1))[0].min()
    L = int(ramp_mm / mm_per_cell)
    rise = int(exit_rise_mm / mm_per_cell)
    t = max(1, int(round(t_mm / mm_per_cell)))
    for s in range(L):
        xx = tail - L + s
        yy = bot - 2 + int(round(rise * s / max(1, L-1)))
        if 0 <= xx < nx:
            for d in range(t):
                if 0 <= yy-d < ny:
                    m[yy-d, xx] = True
    return m


def run(mask, u_lb=0.075, tau=0.53, steps=4200, avg_from=3200,
        pad=(60, 210, 8, 90)):
    """Returns (Fx, Fy) in lattice units, time-averaged, plus lattice Re.
    Bottom pad is small: the floor is right under the body (ground effect
    only exists if the ground is there)."""
    L, R, B, T = pad
    ny, nx = mask.shape
    NY, NX = ny + B + T, nx + L + R
    obs = np.zeros((NY, NX), dtype=bool)
    obs[B:B+ny, L:L+nx] = mask
    obs[0:2, :] = True                       # maze floor

    w = np.array([4/9] + [1/9]*4 + [1/36]*4)
    cx = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1])
    cy = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1])
    opp = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])

    body = np.zeros_like(obs)
    body[B:B+ny, L:L+nx] = mask             # force on the ROBOT, not floor

    # links from fluid node -> body node, per direction
    links = []
    for i in range(9):
        if i == 0:
            links.append(None)
            continue
        nb = np.roll(np.roll(body, cy[i], axis=0), cx[i], axis=1)
        links.append(nb & ~obs)             # fluid nodes facing the body

    def feq(rho, ux, uy):
        cu = 3.0*(cx[:, None, None]*ux + cy[:, None, None]*uy)
        u2 = 1.5*(ux*ux + uy*uy)
        return rho*w[:, None, None]*(1 + cu + 0.5*cu*cu - u2)

    rho = np.ones((NY, NX))
    ux = np.full((NY, NX), u_lb)
    uy = np.zeros((NY, NX))
    uy[:NY//2, :] += 0.003
    f = feq(rho, ux, uy)

    Fx = Fy = 0.0
    n = 0
    for s in range(steps):
        rho = f.sum(axis=0)
        ux = (cx[:, None, None]*f).sum(axis=0)/rho
        uy = (cy[:, None, None]*f).sum(axis=0)/rho
        ux[obs] = 0.0
        uy[obs] = 0.0
        fq = feq(rho, ux, uy)
        f += -(1.0/tau)*(f - fq)
        if s >= avg_from:
            # momentum exchange: 2 c_i f_i^post summed over crossing links
            for i in range(1, 9):
                s_i = f[i][links[i]].sum()
                Fx += 2.0*cx[i]*s_i
                Fy += 2.0*cy[i]*s_i
            n += 1
        fb = f.copy()
        for i in range(9):
            f[i][obs] = fb[opp[i]][obs]
        for i in range(9):
            f[i] = np.roll(np.roll(f[i], cy[i], axis=0), cx[i], axis=1)
        f[:, :, 0] = feq(np.ones((NY, 1)), np.full((NY, 1), u_lb),
                         np.zeros((NY, 1)))[:, :, 0]
        f[:, :, -1] = f[:, :, -2]
        if not np.isfinite(f).all():
            return None
    nu = (tau - 0.5)/3.0
    return (Fx/n, Fy/n, u_lb*nx/nu, nx)


def main():
    m_side = np.load(os.path.join(HERE, "_m_side.npy"))
    k = 2
    base = downsample(m_side, k)
    mmc = PX * k                             # mm per cell after downsample
    print("side silhouette", base.shape, "at %.1f mm/cell" % mmc)

    cases = {
        "baseline": base,
        "rear wing": add_wing(base, mmc),
        "diffuser": add_diffuser(base, mmc),
        "wing + diffuser": add_diffuser(add_wing(base, mmc), mmc),
    }
    out = {}
    for name, mask in cases.items():
        r = run(mask)
        if r is None:
            print(name, "DIVERGED")
            continue
        Fx, Fy, Re, nxc = r
        # non-dimensionalise on the robot's own length (per unit depth)
        q = 0.5 * 1.0 * 0.075**2
        Lref = base.shape[1]
        CD = Fx / (q * Lref)
        CL = Fy / (q * Lref)
        # downforce at the real corner speed, CL referenced to plan area
        DF = -CL * 0.5 * RHO * A_PLAN * V_CORNER**2
        out[name] = {"CD": CD, "CL": CL, "Re": Re,
                     "downforce_mN_at_corner": DF*1000,
                     "pct_of_weight": 100*DF/W_ROBOT}
        print("%-16s CD %+7.3f  CL %+7.3f  -> %+7.2f mN at %.2f m/s "
              "(%+.2f%% of weight)"
              % (name, CD, CL, DF*1000, V_CORNER, 100*DF/W_ROBOT))
    with open(os.path.join(HERE, "aero_wings.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("wrote aero_wings.json")


if __name__ == "__main__":
    main()
