"""
aero_package.py - design a downforce package (front splitter, sealed
underbody + rear diffuser, rear wing) for the micromouse and MEASURE what
each element makes, via LBM with a moving ground (rolling road) and
momentum-exchange force integration on the body. Then scale the measured
lift coefficients to F1 dynamic pressure.

Honesty, up front:
 * 2D. A 2D underbody is the PERFECTLY sealed-skirt case (infinite span,
   no side leakage), so it is the optimistic bound a real 3D skirt chases
   - which is the point: it tells you the ceiling.
 * lattice Re ~ 1e3 vs real ~8e5 - forces are RELATIVE (element vs
   element) and topological, then scaled to F1 q. Not a validated CFD.
 * moving ground is essential: ground-effect downforce does not exist
   over a static floor.

    python aero_package.py -> aero_package.json + _flow_pkg_*.png
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

MM = 0.6
U_LB = 0.04
TAU = 0.62
STEPS = 9000
AVG_FROM = 7000
RIDE = 3                        # ride-height cells above the floor
RHO_AIR, A_SND = 1.204, 343.0
G = 9.81
COR = 75.0                      # F1 corner speed for scaling
MU = 2.3


def load_body():
    m = np.load(os.path.join(HERE, "_m_side.npy"))
    m = np.fliplr(m)                                  # nose to the inlet
    k = 2
    ny, nx = m.shape
    m = m[:(ny//k)*k, :(nx//k)*k].reshape(ny//k, k, nx//k, k).any((1, 3))
    return m


def place(body, elements):
    """Assemble a domain: moving floor at rows 0..1, body lifted RIDE
    cells, plus requested aero elements. Returns obs, bodymask."""
    bh, bw = body.shape
    padL, padR, padT = 40, 150, 40
    NY = 2 + RIDE + bh + padT
    NX = padL + bw + padR
    obs = np.zeros((NY, NX), bool)
    obs[0:2, :] = True                               # floor
    b0 = 2 + RIDE
    x0 = padL
    bodym = np.zeros_like(obs)
    bodym[b0:b0+bh, x0:x0+bw] = body
    # nose/tail columns and body bottom row in domain coords
    cols = np.where(body.any(0))[0]
    nose_c, tail_c = x0 + cols.min(), x0 + cols.max()
    span = tail_c - nose_c

    if "splitter" in elements:
        # flat plate at the body's base, jutting forward from the nose
        ln = int(span*0.28)
        bodym[b0:b0+2, nose_c-ln:nose_c] = True

    if "underbody" in elements:
        # seal the underbody: a flat floor plate just above the road for
        # the front 2/3, then a diffuser ramp expanding up to the tail
        flat_end = nose_c + int(span*0.62)
        t = 2
        bodym[b0-1:b0-1+t, nose_c:flat_end] = True   # flat undertray
        L = tail_c - flat_end
        rise = int((b0 + int(bh*0.5)) - (b0-1))      # ramp up into the base
        for i in range(L):
            yy = (b0-1) + int(round(rise*i/max(1, L-1)))
            bodym[yy:yy+t, flat_end+i] = True

    if "wing" in elements:
        # inverted rear wing: a plate at negative incidence on two struts,
        # above and behind the tail
        chord = int(span*0.26)
        h = int(bh*1.4)
        aoa = math.radians(-14.0)
        wx0 = tail_c - chord + int(span*0.10)
        wy0 = b0 + bh + h
        for i in range(chord):
            xx = wx0 + i
            yy = wy0 + int(round(-i*math.tan(aoa)))
            if 0 <= xx < NX:
                bodym[max(0, yy):yy+2, xx] = True
        for sx in (wx0+int(0.25*chord), wx0+int(0.8*chord)):
            yy = wy0 + int(round(-(sx-wx0)*math.tan(aoa)))
            bodym[b0+bh:yy+1, sx:sx+2] = True

    obs |= bodym
    return obs, bodym, (nose_c, tail_c)


def lbm_force(obs, bodym):
    w = np.array([4/9] + [1/9]*4 + [1/36]*4)
    cx = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1])
    cy = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1])
    opp = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])

    def feq(rho, ux, uy):
        cu = 3.0*(cx[:, None, None]*ux + cy[:, None, None]*uy)
        u2 = 1.5*(ux*ux + uy*uy)
        return rho*w[:, None, None]*(1 + cu + 0.5*cu*cu - u2)

    NY, NX = obs.shape
    # moving-ground wall velocity (belt at +x), shell only
    uwx = np.zeros(obs.shape)
    uwx[0:2, :] = U_LB
    fluid = ~obs
    shell = np.zeros_like(obs)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                shell |= obs & np.roll(np.roll(fluid, dy, 0), dx, 1)
    mom = [np.where(shell, 6.0*w[i]*(cx[i]*uwx), 0.0) for i in range(9)]

    # body boundary links for force integration
    links = []
    for i in range(9):
        nb = np.roll(np.roll(bodym, cy[i], 0), cx[i], 1)
        links.append(nb & ~obs)

    rho = np.ones(obs.shape)
    ux = np.full(obs.shape, U_LB)
    uy = np.zeros(obs.shape)
    uy[:NY//2, :] += 0.002
    f = feq(rho, ux, uy)
    Fy = 0.0
    n = 0
    for s in range(STEPS):
        rho = f.sum(0)
        ux = (cx[:, None, None]*f).sum(0)/rho
        uy = (cy[:, None, None]*f).sum(0)/rho
        ux[obs] = 0.0
        uy[obs] = 0.0
        fq = feq(rho, ux, uy)
        f += -(1.0/TAU)*(f - fq)
        if s >= AVG_FROM:
            for i in range(1, 9):
                Fy += 2.0*cy[i]*f[i][links[i]].sum()
            n += 1
        fb = f.copy()
        for i in range(9):
            f[i][obs] = fb[opp[i]][obs] + mom[i][obs]
        for i in range(9):
            f[i] = np.roll(np.roll(f[i], cy[i], 0), cx[i], 1)
        f[:, :, 0] = feq(np.ones((NY, 1)), np.full((NY, 1), U_LB),
                         np.zeros((NY, 1)))[:, :, 0]
        f[:, :, -1] = f[:, :, -2]
        if not np.isfinite(f).all():
            return None, None
    rho = f.sum(0)
    ux = (cx[:, None, None]*f).sum(0)/rho
    uy = (cy[:, None, None]*f).sum(0)/rho
    spd = np.hypot(ux, uy)/U_LB
    spd[obs] = np.nan
    # vertical force per unit depth in lattice units; +Fy up.
    # downforce = -Fy. Normalise to a coefficient on the body length.
    q = 0.5*1.0*U_LB*U_LB
    bw = np.ptp(np.where(bodym.any(0))[0])
    CLd = -(Fy/n) / (q*bw)                       # +ve = downforce
    return spd, CLd


def render(spd, obs, title, sub, path):
    fig, ax = plt.subplots(figsize=(9.4, 3.6), dpi=150)
    fig.patch.set_facecolor("#161310")
    ax.set_facecolor("#161310")
    im = ax.imshow(np.ma.masked_invalid(spd), cmap=CMAP, vmin=0, vmax=2.0,
                   origin="lower", interpolation="bilinear")
    ax.contour(np.where(np.isnan(spd), 0, spd), levels=[0.25, 0.6, 1.0],
               colors="#ffffff", linewidths=0.4, alpha=0.30)
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
    cb = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.012)
    cb.set_label("speed / freestream", color="#a79c93", fontsize=8)
    cb.ax.tick_params(colors="#a79c93", labelsize=7)
    cb.outline.set_edgecolor("#3a322b")
    fig.tight_layout()
    fig.savefig(path, facecolor="#161310", bbox_inches="tight")
    plt.close(fig)


def b64(p):
    return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()


def main():
    d = json.load(open(os.path.join(HERE, "aero_data.json")))
    A_p = d["areas"]["plan_mm2"]*1e-6
    L = d["areas"]["length_mm"]*1e-3
    W = 0.22*G
    body = load_body()

    configs = [
        ("bare", []),
        ("+ rear wing", ["wing"]),
        ("+ sealed underbody & diffuser", ["underbody"]),
        ("full package", ["splitter", "underbody", "wing"]),
    ]
    out = {"speed_mps": COR, "results": []}
    imgs = {}
    q_f1 = 0.5*RHO_AIR*COR*COR
    for name, els in configs:
        obs, bodym, geom = place(body, els)
        spd, CLd = lbm_force(obs, bodym)
        if spd is None:
            print("%-30s DIVERGED" % name); continue
        # CLd measured on body length; convert to plan-area basis by L/(plan/track)
        # simpler: report downforce = CLd * q_f1 * (L * 1 m depth) is 2D;
        # scale by the real span (track) to get a 3D estimate.
        track = 0.098
        DF = CLd * q_f1 * L * track          # N, 3D estimate from 2D coeff
        dfw = DF/W
        # corner radius enabled at COR with race-glue mu
        Rneed = COR*COR/(MU*G*(1+max(dfw, 0)))
        out["results"].append(dict(name=name, CLd=round(CLd, 3),
                                   DF_N=round(DF, 1), x_weight=round(dfw, 1),
                                   corner_R_m=round(Rneed, 1)))
        print("%-30s CLd %+.2f  downforce %6.1f N (%4.1fx W)  Rmin %.1f m"
              % (name, CLd, DF, dfw, Rneed))
        if name in ("bare", "full package"):
            key = "pkg_bare" if name == "bare" else "pkg_full"
            png = os.path.join(HERE, "_flow_%s.png" % key)
            render(spd, obs,
                   "Airflow at F1 speed (270 km/h) - %s" % name,
                   "moving ground + rolling-road ground effect; 2D = "
                   "perfectly sealed skirt (optimistic bound)", png)
            imgs[key] = b64(png)
    out["images"] = imgs
    with open(os.path.join(HERE, "aero_package.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("wrote aero_package.json")


if __name__ == "__main__":
    main()
