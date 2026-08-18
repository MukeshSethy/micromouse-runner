"""
aero_study.py - aerodynamic drag on the micromouse, straights and corners.

No CFD package here, so the honest split is:
  * FORCES from the real projected areas (rasterised from the tessellated
    CAD, not a bbox guess) x the drag equation, with a Cd band from the
    bluff-body literature rather than a single invented number;
  * SLIP ANGLES in corners taken from sim_twin (the same twin that tunes
    the controller), so the yawed case is the robot's real attitude;
  * FLOW PICTURES from a small 2D lattice-Boltzmann solver over the real
    plan-view silhouette - qualitative wake structure, not a validated
    Cd. Anything it produces is labelled as such.

    python aero_study.py     -> aero_data.json for the artifact
"""

import base64
import json
import math
import os
import struct

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RHO = 1.204          # air, 20 C
NU = 1.516e-5        # kinematic viscosity, m2/s
MASS = 0.22          # kg, from the sim


# ---------------------------------------------------------------- geometry
def load_tris():
    d = json.load(open(os.path.join(HERE, "web", "robot_mesh.json")))
    tris = []
    inst = d.get("instances", [])
    byname = {g["name"]: g for g in d["groups"]}
    for g in d["groups"]:
        if g["name"] == "wheelN":       # trimmed variant, not fitted here
            continue
        vb = base64.b64decode(g["v"])
        iv = np.frombuffer(vb, dtype="<i2").astype(float) / 100.0
        P = iv.reshape(-1, 3)
        if g["kind"] == "static":
            tris.append(P)
    # spin meshes are stored centred on their own axle: place instances
    for it in inst:
        g = byname.get(it["m"])
        if g is None or g["name"] == "wheelN":
            continue
        vb = base64.b64decode(g["v"])
        iv = np.frombuffer(vb, dtype="<i2").astype(float) / 100.0
        P = iv.reshape(-1, 3) + np.array([it["x"], it["y"], it["z"]])
        tris.append(P)
    return np.vstack(tris)


def raster_area(P, drop, px=0.5):
    """Silhouette area (mm2) + the occupancy mask, projecting out axis
    `drop` by rasterising every triangle. Barycentric fill on a px grid."""
    keep = [i for i in range(3) if i != drop]
    Q = P[:, keep]
    lo = Q.min(axis=0)
    hi = Q.max(axis=0)
    nx = int(math.ceil((hi[0] - lo[0]) / px)) + 2
    ny = int(math.ceil((hi[1] - lo[1]) / px)) + 2
    mask = np.zeros((ny, nx), dtype=bool)
    T = Q.reshape(-1, 3, 2)
    for t in T:
        (x0, y0), (x1, y1), (x2, y2) = t
        i0 = max(0, int((min(x0, x1, x2) - lo[0]) / px))
        i1 = min(nx - 1, int((max(x0, x1, x2) - lo[0]) / px) + 1)
        j0 = max(0, int((min(y0, y1, y2) - lo[1]) / px))
        j1 = min(ny - 1, int((max(y0, y1, y2) - lo[1]) / px) + 1)
        if i1 < i0 or j1 < j0:
            continue
        xs = lo[0] + (np.arange(i0, i1 + 1) + 0.5) * px
        ys = lo[1] + (np.arange(j0, j1 + 1) + 0.5) * px
        X, Y = np.meshgrid(xs, ys)
        d = (y1 - y2)*(x0 - x2) + (x2 - x1)*(y0 - y2)
        if abs(d) < 1e-12:
            continue
        a = ((y1 - y2)*(X - x2) + (x2 - x1)*(Y - y2)) / d
        b = ((y2 - y0)*(X - x2) + (x0 - x2)*(Y - y2)) / d
        c = 1.0 - a - b
        hit = (a >= -1e-9) & (b >= -1e-9) & (c >= -1e-9)
        mask[j0:j1+1, i0:i1+1] |= hit
    return mask.sum() * px * px, mask, lo, px


# ------------------------------------------------------------------ forces
def drag(v, area_mm2, cd):
    return 0.5 * RHO * cd * (area_mm2 * 1e-6) * v * v


def reynolds(v, L_mm):
    return v * (L_mm * 1e-3) / NU


# ------------------------------------------------- 2D lattice Boltzmann (D2Q9)
def lbm(mask, u_lb=0.08, tau=0.53, steps=5200, pad=(60, 190, 55, 55)):
    """Flow past the silhouette. Returns speed field + the obstacle.
    NOT a validated Cd - it is a picture of the wake. tau near 0.5 keeps
    the lattice viscosity small (high Re) but is only marginally stable,
    so the sim is monitored and reported if it diverges."""
    L, R, B, T = pad
    ny, nx = mask.shape
    NY, NX = ny + B + T, nx + L + R
    obs = np.zeros((NY, NX), dtype=bool)
    obs[B:B+ny, L:L+nx] = mask
    obs[0, :] = obs[-1, :] = True                     # channel walls

    w = np.array([4/9] + [1/9]*4 + [1/36]*4)
    cx = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1])
    cy = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1])
    opp = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])

    def feq(rho, ux, uy):
        cu = 3.0*(cx[:, None, None]*ux + cy[:, None, None]*uy)
        u2 = 1.5*(ux*ux + uy*uy)
        return rho * w[:, None, None] * (1 + cu + 0.5*cu*cu - u2)

    rho = np.ones((NY, NX))
    ux = np.full((NY, NX), u_lb)
    uy = np.zeros((NY, NX))
    f = feq(rho, ux, uy)
    for s in range(steps):
        # collide
        rho = f.sum(axis=0)
        ux = (cx[:, None, None]*f).sum(axis=0) / rho
        uy = (cy[:, None, None]*f).sum(axis=0) / rho
        ux[obs] = 0.0; uy[obs] = 0.0
        fq = feq(rho, ux, uy)
        f += -(1.0/tau) * (f - fq)
        # bounce-back on the body
        for i in range(9):
            f[i][obs] = fq[i][obs]          # placeholder, replaced below
        fb = f.copy()
        for i in range(9):
            f[i][obs] = fb[opp[i]][obs]
        # stream
        for i in range(9):
            f[i] = np.roll(np.roll(f[i], cy[i], axis=0), cx[i], axis=1)
        # inlet / outlet
        f[:, :, 0] = feq(np.ones((NY, 1)), np.full((NY, 1), u_lb),
                         np.zeros((NY, 1)))[:, :, 0]
        f[:, :, -1] = f[:, :, -2]
        if not np.isfinite(rho).all():
            return None, obs, s
    rho = f.sum(axis=0)
    ux = (cx[:, None, None]*f).sum(axis=0) / rho
    uy = (cy[:, None, None]*f).sum(axis=0) / rho
    spd = np.sqrt(ux*ux + uy*uy) / u_lb
    spd[obs] = np.nan
    return spd, obs, steps


def rot_mask(mask, deg, px=0.5):
    """Rotate a plan-view silhouette by a yaw angle (nearest-neighbour)."""
    a = math.radians(deg)
    ny, nx = mask.shape
    cy, cx = ny/2.0, nx/2.0
    R = int(math.hypot(ny, nx)/2) + 2
    NY, NX = 2*R, 2*R
    out = np.zeros((NY, NX), dtype=bool)
    yy, xx = np.mgrid[0:NY, 0:NX]
    dy = yy - R; dx = xx - R
    sy = (dx*math.sin(-a) + dy*math.cos(-a) + cy).astype(int)
    sx = (dx*math.cos(-a) - dy*math.sin(-a) + cx).astype(int)
    ok = (sy >= 0) & (sy < ny) & (sx >= 0) & (sx < nx)
    out[ok] = mask[sy[ok], sx[ok]]
    # trim empty border
    rows = np.where(out.any(axis=1))[0]
    cols = np.where(out.any(axis=0))[0]
    return out[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]


def main():
    P = load_tris()
    A_front, m_front, _, _ = raster_area(P, drop=0)   # looking along +X
    A_side,  m_side,  _, _ = raster_area(P, drop=1)
    A_plan,  m_plan,  _, _ = raster_area(P, drop=2)
    print("frontal %.1f mm2   side %.1f mm2   plan %.1f mm2"
          % (A_front, A_side, A_plan))
    bb = P.min(axis=0), P.max(axis=0)
    L = bb[1][0] - bb[0][0]
    print("length %.1f mm" % L)
    out = {"areas": {"front_mm2": A_front, "side_mm2": A_side,
                     "plan_mm2": A_plan, "length_mm": L},
           "rho": RHO, "nu": NU, "mass": MASS}

    # slip angles measured in the twin, corner-by-corner
    import sim_twin as ST
    T = dict(vmax=0.8, fmarg=0.32, brake_d=260.0, ff_d=20.0, kff=0.7,
             kp=0.45, kh=1.3, ke=1.2, ka=1.8, look=115.0, krd=0.5,
             kmul=4.5, vdiag=0.72, slew=0.30, mu=4.0, comp=True)
    slips = {}
    for label, g in (("stock 0.8", dict(T)),
                     ("fast 3.0", dict(T, vmax=3.0, fast=True, narrow=True,
                                       diag=True, kh=1.9, krd=2.2, mu=1.1))):
        s = ST.Sim(dict(g))
        beta_corner, beta_all = [], []
        n = len(s.P)
        while s.t < 60.0 and s.pathI < n - 2:
            s.step(0.002)
            if abs(s.u) > 0.15:
                b = math.degrees(math.atan2(s.v, abs(s.u)))
                beta_all.append(abs(b))
                if abs(s.r) > 1.5:            # in a turn
                    beta_corner.append(abs(b))
        slips[label] = {
            "beta_corner_mean": float(np.mean(beta_corner or [0])),
            "beta_corner_p95": float(np.percentile(beta_corner or [0], 95)),
            "beta_corner_max": float(np.max(beta_corner or [0])),
            "beta_all_mean": float(np.mean(beta_all or [0])),
            "n": len(beta_corner)}
        print(label, slips[label])
    out["slip"] = slips
    with open(os.path.join(HERE, "aero_data.json"), "w") as f:
        json.dump(out, f, indent=1)
    np.save(os.path.join(HERE, "_m_plan.npy"), m_plan)
    np.save(os.path.join(HERE, "_m_front.npy"), m_front)
    np.save(os.path.join(HERE, "_m_side.npy"), m_side)
    print("wrote aero_data.json")


if __name__ == "__main__":
    main()
