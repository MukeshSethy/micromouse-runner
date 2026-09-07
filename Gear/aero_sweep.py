"""
aero_sweep.py - a 0..300 km/h flow ladder for the interactive sweep.

The flow PATTERN over a sharp bluff body is nearly self-similar in shape,
but its Reynolds number climbs from ~0 to ~8e5 across 0-300 km/h, and the
WAKE changes with it: attached and steady when slow, an unsteady shedding
wake when fast. We can't reach real Re on a lattice, but we can walk the
lattice Re up the same ladder so the qualitative transition is visible.
Each speed rung gets one late-time plan-view snapshot.

Forces are NOT computed here - they scale exactly as v^2 and the artifact
does them live from the drag equation.

    python aero_sweep.py -> _sweep.json (speed -> flow image + Re/Mach)
"""

import base64
import json
import math
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.abspath(__file__))
CMAP = LinearSegmentedColormap.from_list("wake", [
    "#161310", "#2b2118", "#5a3a1f", "#a8541f", "#e08a2a", "#f5d59a"])

A_SND = 343.0
L_BODY = 0.12
NU_AIR = 1.516e-5

# speed rungs (km/h) and the lattice Re each maps to (low->high shedding)
RUNGS = [20, 60, 110, 160, 210, 260, 300]
LAT_RE = [35, 80, 150, 260, 430, 650, 950]
U_LB = 0.05


def load_plan():
    m = np.load(os.path.join(HERE, "_m_plan.npy"))
    m = np.fliplr(m)                              # nose to the inlet
    k = 2
    ny, nx = m.shape
    return m[:(ny//k)*k, :(nx//k)*k].reshape(ny//k, k, nx//k, k).any((1, 3))


def lbm(mask, lat_re, steps=6500, pad=(64, 240, 55, 55)):
    L, R, B, T = pad
    ny, nx = mask.shape
    NY, NX = ny + B + T, nx + L + R
    obs = np.zeros((NY, NX), bool)
    obs[B:B+ny, L:L+nx] = mask

    w = np.array([4/9] + [1/9]*4 + [1/36]*4)
    cx = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1])
    cy = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1])
    opp = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])
    nu = U_LB*(nx) / lat_re
    tau = 0.5 + 3.0*nu

    def feq(rho, ux, uy):
        cu = 3.0*(cx[:, None, None]*ux + cy[:, None, None]*uy)
        u2 = 1.5*(ux*ux + uy*uy)
        return rho*w[:, None, None]*(1 + cu + 0.5*cu*cu - u2)

    rho = np.ones((NY, NX))
    ux = np.full((NY, NX), U_LB)
    uy = np.zeros((NY, NX))
    uy[:NY//2, :] += 0.003                        # break symmetry
    f = feq(rho, ux, uy)
    for s in range(steps):
        rho = f.sum(0)
        ux = (cx[:, None, None]*f).sum(0)/rho
        uy = (cy[:, None, None]*f).sum(0)/rho
        ux[obs] = 0.0; uy[obs] = 0.0
        fq = feq(rho, ux, uy)
        f += -(1.0/tau)*(f - fq)
        fb = f.copy()
        for i in range(9):
            f[i][obs] = fb[opp[i]][obs]
        for i in range(9):
            f[i] = np.roll(np.roll(f[i], cy[i], 0), cx[i], 1)
        f[:, :, 0] = feq(np.ones((NY, 1)), np.full((NY, 1), U_LB),
                         np.zeros((NY, 1)))[:, :, 0]
        f[:, :, -1] = f[:, :, -2]
        if not np.isfinite(f).all():
            return None
    rho = f.sum(0)
    ux = (cx[:, None, None]*f).sum(0)/rho
    uy = (cy[:, None, None]*f).sum(0)/rho
    spd = np.hypot(ux, uy)/U_LB
    spd[obs] = np.nan
    return spd, obs


def png(spd, obs):
    fig, ax = plt.subplots(figsize=(7.6, 3.3), dpi=125)
    fig.patch.set_facecolor("#161310"); ax.set_facecolor("#161310")
    ax.imshow(np.ma.masked_invalid(spd), cmap=CMAP, vmin=0, vmax=1.9,
              origin="lower", interpolation="bilinear")
    ax.contour(np.where(np.isnan(spd), 0, spd), levels=[0.25, 0.6, 1.0],
               colors="#ffffff", linewidths=0.4, alpha=0.28)
    ax.imshow(np.where(obs, 1.0, np.nan),
              cmap=matplotlib.colors.ListedColormap(["#e8e2da"]),
              origin="lower", interpolation="nearest")
    ax.set_xticks([]); ax.set_yticks([]); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    p = os.path.join(HERE, "_sweep_tmp.png")
    fig.savefig(p, facecolor="#161310", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return "data:image/png;base64," + \
        base64.b64encode(open(p, "rb").read()).decode()


def main():
    plan = load_plan()
    frames = []
    for kmh, lre in zip(RUNGS, LAT_RE):
        print("running", kmh, "km/h  (lattice Re", lre, ")")
        res = lbm(plan, lre)
        if res is None:
            print("  diverged"); continue
        spd, obs = res
        v = kmh/3.6
        frames.append(dict(kmh=kmh, img=png(*res),
                           re=v*L_BODY/NU_AIR, mach=v/A_SND))
    doc = {"frames": frames}
    with open(os.path.join(HERE, "_sweep.json"), "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    print("wrote _sweep.json (%d rungs, %.2f MB)"
          % (len(frames),
             os.path.getsize(os.path.join(HERE, "_sweep.json"))/1e6))


if __name__ == "__main__":
    main()
