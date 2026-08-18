"""
aero_flow.py - 2D lattice-Boltzmann pictures of the flow past the real
micromouse silhouette, straight and yawed (cornering attitude).

HONESTY NOTE, repeated in the output: a D2Q9 LBM on a ~300x200 lattice
runs at a lattice Reynolds number of order 1e2, while the real robot at
5 m/s is at Re ~ 4e4. So these fields show WHERE the flow separates and
how big the wake is - the topology - not a validated drag coefficient
and not the real turbulent structure. The force numbers in the report
come from the drag equation with a literature Cd band, never from this.

    python aero_flow.py    -> _flow_*.png (embedded into the artifact)
"""

import base64
import io
import json
import math
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.abspath(__file__))

# ink-on-dark ramp, single hue family + a warm accent for fast flow
CMAP = LinearSegmentedColormap.from_list("wake", [
    "#161310", "#2b2118", "#5a3a1f", "#a8541f", "#e08a2a", "#f5d59a"])


def downsample(mask, target_w):
    ny, nx = mask.shape
    k = max(1, int(round(nx / target_w)))
    ny2, nx2 = ny // k, nx // k
    m = mask[:ny2*k, :nx2*k].reshape(ny2, k, nx2, k)
    return m.any(axis=(1, 3))


def rot_mask(mask, deg):
    a = math.radians(deg)
    ny, nx = mask.shape
    R = int(math.hypot(ny, nx) / 2) + 2
    out = np.zeros((2*R, 2*R), dtype=bool)
    yy, xx = np.mgrid[0:2*R, 0:2*R]
    dy, dx = yy - R, xx - R
    sy = (dx*math.sin(-a) + dy*math.cos(-a) + ny/2).astype(int)
    sx = (dx*math.cos(-a) - dy*math.sin(-a) + nx/2).astype(int)
    ok = (sy >= 0) & (sy < ny) & (sx >= 0) & (sx < nx)
    out[ok] = mask[sy[ok], sx[ok]]
    rows = np.where(out.any(axis=1))[0]
    cols = np.where(out.any(axis=0))[0]
    return out[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]


def lbm(mask, u_lb=0.075, tau=0.53, steps=6000, pad=(70, 260, 60, 60),
        floor=False):
    """floor=True puts a no-slip wall right under the body (the maze
    floor) and only there - a top wall as well squeezed the side-view
    channel until the scheme blew up at step 731."""
    L, R, B, T = pad
    ny, nx = mask.shape
    if floor:
        B = 6                              # ride height, in lattice cells
    NY, NX = ny + B + T, nx + L + R
    obs = np.zeros((NY, NX), dtype=bool)
    obs[B:B+ny, L:L+nx] = mask
    if floor:
        obs[0:2, :] = True

    w = np.array([4/9] + [1/9]*4 + [1/36]*4)
    cx = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1])
    cy = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1])
    opp = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])

    def feq(rho, ux, uy):
        cu = 3.0*(cx[:, None, None]*ux + cy[:, None, None]*uy)
        u2 = 1.5*(ux*ux + uy*uy)
        return rho*w[:, None, None]*(1 + cu + 0.5*cu*cu - u2)

    rho = np.ones((NY, NX))
    ux = np.full((NY, NX), u_lb)
    uy = np.zeros((NY, NX))
    f = feq(rho, ux, uy)

    for s in range(steps):
        rho = f.sum(axis=0)
        ux = (cx[:, None, None]*f).sum(axis=0)/rho
        uy = (cy[:, None, None]*f).sum(axis=0)/rho
        ux[obs] = 0.0
        uy[obs] = 0.0
        fq = feq(rho, ux, uy)
        f += -(1.0/tau)*(f - fq)
        fb = f.copy()                       # half-way bounce-back
        for i in range(9):
            f[i][obs] = fb[opp[i]][obs]
        for i in range(9):
            f[i] = np.roll(np.roll(f[i], cy[i], axis=0), cx[i], axis=1)
        f[:, :, 0] = feq(np.ones((NY, 1)), np.full((NY, 1), u_lb),
                         np.zeros((NY, 1)))[:, :, 0]
        f[:, :, -1] = f[:, :, -2]
        if not np.isfinite(f).all():
            print("   DIVERGED at step", s)
            return None, obs
    rho = f.sum(axis=0)
    ux = (cx[:, None, None]*f).sum(axis=0)/rho
    uy = (cy[:, None, None]*f).sum(axis=0)/rho
    spd = np.hypot(ux, uy)/u_lb
    spd[obs] = np.nan
    nu_lb = (tau - 0.5)/3.0
    Re = u_lb*mask.shape[1]/nu_lb
    return (spd, obs, Re)


def render(spd, obs, title, sub, path):
    fig, ax = plt.subplots(figsize=(9.2, 4.0), dpi=150)
    fig.patch.set_facecolor("#161310")
    ax.set_facecolor("#161310")
    v = np.ma.masked_invalid(spd)
    im = ax.imshow(v, cmap=CMAP, vmin=0, vmax=1.75, origin="lower",
                   interpolation="bilinear")
    ax.contour(np.where(np.isnan(spd), 0, spd), levels=[0.25, 0.6, 1.0],
               colors="#ffffff", linewidths=0.45, alpha=0.30)
    ax.imshow(np.where(obs, 1.0, np.nan), cmap=matplotlib.colors.ListedColormap(
        ["#e8e2da"]), origin="lower", interpolation="nearest")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#3a322b")
    ax.set_title(title, color="#f2ede8", fontsize=11, loc="left", pad=22,
                 fontweight="bold")
    ax.text(0.0, 1.012, sub, transform=ax.transAxes, color="#a79c93",
            fontsize=8.0, va="bottom")
    cb = fig.colorbar(im, ax=ax, fraction=0.022, pad=0.012)
    cb.set_label("speed / freestream", color="#a79c93", fontsize=8)
    cb.ax.tick_params(colors="#a79c93", labelsize=7)
    cb.outline.set_edgecolor("#3a322b")
    fig.tight_layout()
    fig.savefig(path, facecolor="#161310", bbox_inches="tight")
    plt.close(fig)
    print("  wrote", os.path.basename(path))


def b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def main():
    m_plan = np.load(os.path.join(HERE, "_m_plan.npy"))
    m_side = np.load(os.path.join(HERE, "_m_side.npy"))
    print("plan mask", m_plan.shape, " side mask", m_side.shape)

    # NO rot90: raster_area keeps (rows, cols) = (lateral, longitudinal)
    # for the plan view and (height, longitudinal) for the side view, and
    # the LBM inlet blows along +columns. Rotating simulated CROSSFLOW.
    cases = []
    p0 = downsample(m_plan, 110)
    cases.append(("straight", p0,
                  "Plan view - straight running (yaw 0)",
                  "flow left to right; white = robot, wheels included"))
    p5 = downsample(rot_mask(m_plan, 6.7), 110)
    cases.append(("corner", p5,
                  "Plan view - cornering attitude (yaw 6.7 deg)",
                  "6.7 deg = the 95th-percentile body slip angle measured "
                  "in sim_twin corners at 3 m/s"))
    # side view: the bottom wall IS the maze floor, so keep it
    s0 = downsample(m_side, 150)
    cases.append(("side", s0,
                  "Side view - straight running (floor modelled)",
                  "the 5 mm underbody gap and the wake off the square tail"))

    out = {}
    for key, mask, title, sub in cases:
        print("running LBM:", key, mask.shape)
        res = lbm(mask, floor=(key == "side"))
        if res[0] is None:
            print("  skipped (diverged)")
            continue
        spd, obs, Re = res
        np.savez_compressed(os.path.join(HERE, "_flow_%s.npz" % key),
                            spd=spd, obs=obs, Re=Re)   # re-render for free
        path = os.path.join(HERE, "_flow_%s.png" % key)
        render(spd, obs, title,
               sub + "  |  lattice Re ~ %.0f (topology only, not the real "
               "Re ~ 4e4)" % Re, path)
        out[key] = b64(path)
    with open(os.path.join(HERE, "_flow_images.json"), "w") as f:
        json.dump(out, f)
    print("wrote _flow_images.json (%d images)" % len(out))


if __name__ == "__main__":
    main()
