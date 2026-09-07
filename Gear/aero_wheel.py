"""
aero_wheel.py - close-up CFD of the airflow over one wheel, done the way
wheel aerodynamics must be done: in the ROBOT's frame the air streams
past, the GROUND moves backward with it, and the WHEEL ROTATES so its rim
matches the ground at the contact patch. A naive static-wheel/static-
ground case is computed alongside to show what the simplification hides.

Moving boundaries via velocity bounce-back:
    f_i(x_b) = f_opp(x_b) + 6 w_i rho0 (c_i . u_wall)
with u_wall = freestream on the floor and omega x r on the wheel rim
(rim speed = freestream, i.e. rolling without slip).

Same honesty caveat as the whole aero series: lattice Re ~ 1e3 vs real
~2e4 at 5 m/s on the wheel chord - read the TOPOLOGY (separation points,
wake shape, the counter-rotating rim effect), not absolute forces.

    python aero_wheel.py  -> adds wheel_static / wheel_rolling images to
                             _flow_images.json
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

MM = 0.5                      # mm per cell
R_WHEEL_MM = 13.5
NY, NX = 96, 300              # 48 x 150 mm domain
U_LB = 0.04
TAU = 0.62
STEPS = 12000


def build_domain():
    obs = np.zeros((NY, NX), dtype=bool)
    obs[0:2, :] = True                       # the maze floor
    R = int(round(R_WHEEL_MM / MM))
    # contact BURIED 2 cells into the floor: a fluid cell pinched
    # between two moving walls accumulates momentum with no drain
    # and diverges (~step 490, deterministically). Real wheels touch.
    cx0, cy0 = 90, 2 + R - 2
    yy, xx = np.mgrid[0:NY, 0:NX]
    wheel = (xx - cx0)**2 + (yy - cy0)**2 <= R*R
    obs |= wheel
    return obs, wheel, (cx0, cy0, R)


def wall_velocity(obs, wheel, geom, rolling):
    """Per-cell wall velocity for the moving-boundary bounce-back."""
    cx0, cy0, R = geom
    uwx = np.zeros(obs.shape)
    uwy = np.zeros(obs.shape)
    if rolling:
        uwx[0:2, :] = U_LB                   # ground streams backwards
        yy, xx = np.mgrid[0:obs.shape[0], 0:obs.shape[1]]
        om = U_LB / R                        # rim speed = freestream
        # omega z-hat x r : counterclockwise so the contact point
        # matches the moving ground
        uwx[wheel] = -om * (yy[wheel] - cy0) * -1.0
        uwy[wheel] = (om * (xx[wheel] - cx0)) * -1.0
        # bottom of wheel must move +x like the ground: check sign
        # u = omega x r with omega = +om z: u_x = -om*(y-cy), u_y = +om*(x-cx)
        uwx[wheel] = -om * (yy[wheel] - cy0)
        uwy[wheel] = om * (xx[wheel] - cx0)
    return uwx, uwy


def lbm(obs, uwx, uwy):
    w = np.array([4/9] + [1/9]*4 + [1/36]*4)
    cx = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1])
    cy = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1])
    opp = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])

    def feq(rho, ux, uy):
        cu = 3.0*(cx[:, None, None]*ux + cy[:, None, None]*uy)
        u2 = 1.5*(ux*ux + uy*uy)
        return rho*w[:, None, None]*(1 + cu + 0.5*cu*cu - u2)

    rho = np.ones(obs.shape)
    ux = np.full(obs.shape, U_LB)
    uy = np.zeros(obs.shape)
    uy[:obs.shape[0]//2, :] += 0.003
    f = feq(rho, ux, uy)
    # moving-wall momentum correction ONLY on the boundary shell (solid
    # cells with a fluid neighbour). Applying it through the solid
    # interior injects unbalanced mass every step - that is exactly the
    # divergence the first run hit at step 489.
    fluid = ~obs
    shell = np.zeros_like(obs)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            shell |= obs & np.roll(np.roll(fluid, dy, axis=0), dx, axis=1)
    mom = [np.where(shell, 6.0*w[i]*(cx[i]*uwx + cy[i]*uwy), 0.0)
           for i in range(9)]

    for s in range(STEPS):
        rho = f.sum(axis=0)
        ux = (cx[:, None, None]*f).sum(axis=0)/rho
        uy = (cy[:, None, None]*f).sum(axis=0)/rho
        ux[obs] = 0.0
        uy[obs] = 0.0
        fq = feq(rho, ux, uy)
        f += -(1.0/TAU)*(f - fq)
        fb = f.copy()
        for i in range(9):
            f[i][obs] = fb[opp[i]][obs] + mom[i][obs]
        for i in range(9):
            f[i] = np.roll(np.roll(f[i], cy[i], axis=0), cx[i], axis=1)
        f[:, :, 0] = feq(np.ones((obs.shape[0], 1)),
                         np.full((obs.shape[0], 1), U_LB),
                         np.zeros((obs.shape[0], 1)))[:, :, 0]
        f[:, :, -1] = f[:, :, -2]
        if not np.isfinite(f).all():
            print("  DIVERGED at", s)
            return None
    rho = f.sum(axis=0)
    ux = (cx[:, None, None]*f).sum(axis=0)/rho
    uy = (cy[:, None, None]*f).sum(axis=0)/rho
    spd = np.hypot(ux, uy)/U_LB
    spd[obs] = np.nan
    nu = (TAU - 0.5)/3.0
    return spd, U_LB*2*int(R_WHEEL_MM/MM)/nu


def render(spd, obs, title, sub, path):
    fig, ax = plt.subplots(figsize=(9.2, 3.4), dpi=150)
    fig.patch.set_facecolor("#161310")
    ax.set_facecolor("#161310")
    im = ax.imshow(np.ma.masked_invalid(spd), cmap=CMAP, vmin=0, vmax=2.0,
                   origin="lower", interpolation="bilinear")
    ax.contour(np.where(np.isnan(spd), 0, spd), levels=[0.25, 0.6, 1.0],
               colors="#ffffff", linewidths=0.45, alpha=0.30)
    ax.imshow(np.where(obs, 1.0, np.nan),
              cmap=matplotlib.colors.ListedColormap(["#e8e2da"]),
              origin="lower", interpolation="nearest")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#3a322b")
    ax.set_title(title, color="#f2ede8", fontsize=10.5, loc="left", pad=20,
                 fontweight="bold")
    ax.text(0.0, 1.02, sub, transform=ax.transAxes, color="#a79c93",
            fontsize=8.0, va="bottom")
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.012)
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
    obs, wheel, geom = build_domain()
    imgs_path = os.path.join(HERE, "_flow_images.json")
    imgs = json.load(open(imgs_path)) if os.path.exists(imgs_path) else {}

    for key, rolling, title, sub in (
        ("wheel_static", False,
         "One wheel, NAIVE: static wheel, static ground",
         "what a simplified model shows - clean stagnation, big top-side "
         "separation, floor boundary layer"),
        ("wheel_rolling", True,
         "One wheel, CORRECT: rolling rim + moving ground (robot frame)",
         "rim top moves against the flow at 2x freestream; ground belt "
         "sweeps the floor boundary layer away"),
    ):
        print("running", key)
        uwx, uwy = wall_velocity(obs, wheel, geom, rolling)
        res = lbm(obs, uwx, uwy)
        if res is None:
            continue
        spd, Re = res
        png = os.path.join(HERE, "_flow_%s.png" % key)
        render(spd, obs, title,
               sub + "  |  lattice Re ~ %.0f (topology only)" % Re, png)
        imgs[key] = b64(png)
    with open(imgs_path, "w") as f:
        json.dump(imgs, f)
    print("updated _flow_images.json (%d images)" % len(imgs))


if __name__ == "__main__":
    main()
