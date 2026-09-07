"""
thermal_study.py - motor thermal analysis for the micromouse, driven by
the same twin that runs the published simulator.

Physics: for a brushed DC motor the electromagnetic torque model the twin
already uses, T = TS*(duty - w/WF), is exactly k_t * I with
I = I_stall*(duty - w/WF). So the twin's duty/speed history gives the
true winding current at every 2 ms step, and copper loss is I^2 * R.
Iron and brush losses are neglected (small at these loads - stated on
the page). Heat flows through a single lumped node:

    C * dT/dt = P(t) - dT_amb / Rth

with per-motor thermal capacitance C and case-to-ambient resistance Rth.
No convective credit is taken from vehicle motion: the aero study showed
airflow at these speeds is feeble, so still-air Rth is the honest choice.

Assumed electrical/thermal constants (typical catalogue values for
6 V N20 windings; the page states them as assumptions):
    stock  N20:  I_stall 1.6 A, R 3.75 ohm
    high-RPM N20: I_stall 3.0 A, R 2.0 ohm
    per motor: Rth 45 K/W (still air), C 5 J/K  (tau ~ 3.75 min)

    python thermal_study.py  -> thermal_data.json + _thermal.png
"""

import json
import math
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sim_twin as ST

HERE = os.path.dirname(os.path.abspath(__file__))
DT = 0.002
RTH = 45.0        # K/W case->ambient, still air
CTH = 5.0         # J/K per motor
T_AMB = 25.0
T_LIMIT = 100.0   # enamel/magnet comfort limit for cheap N20s

INK, INK2, MUTED, GRID, SURF = ("#f2ede8", "#a79c93", "#898781",
                                "#2c2c2a", "#161310")
C1, C2, C3 = "#e08a2a", "#199e70", "#8a7bb8"

COMMON = dict(fmarg=0.32, brake_d=260.0, ff_d=20.0, kff=0.7, kp=0.45,
              ka=1.8, look=115.0, kmul=4.5, slew=0.30, comp=True)

REGIMES = {
    "stock 0.8 m/s": dict(COMMON, vmax=0.8, mu=4.0, narrow=True,
                          diag=False, kh=1.7, ke=1.2, krd=1.1, vdiag=0.72,
                          i_stall=1.6, r_wind=3.75, i_lim=1.5),
    "fast 3.0 m/s": dict(COMMON, vmax=3.0, mu=1.1, fast=True, narrow=True,
                         diag=True, kh=2.3, ke=1.8, krd=2.6, vdiag=0.72,
                         i_stall=3.0, r_wind=2.0, i_lim=2.5),
    "race glue 3.0 m/s": dict(COMMON, vmax=3.0, mu=2.3, fmarg=0.70,
                              fast=True, narrow=True, diag=True, kh=2.3,
                              ke=1.2, krd=2.8, vdiag=0.90,
                              i_stall=3.0, r_wind=2.0, i_lim=2.5),
}


class LoggingSim(ST.Sim):
    """Sim with the duty of each PI step captured. The duty is recomputed
    with the same expression _dyn uses, from the pre-update integrator -
    bitwise identical to what the plant saw."""

    def __init__(self, gains, **kw):
        super().__init__(gains, **kw)
        self.log_t = []
        self.log_dutyL = []
        self.log_dutyR = []
        self.log_wL = []
        self.log_wR = []

    def _dyn(self, dt):
        for cmd, act, integ, out in (
                (self.wl, self.wal, self.iL, self.log_dutyL),
                (self.wr, self.war, self.iR, self.log_dutyR)):
            err = cmd - act
            integ2 = max(-0.6/ST.PI_KI, min(0.6/ST.PI_KI, integ + err*dt))
            out.append(max(-1.0, min(1.0, ST.PI_KP*err + ST.PI_KI*integ2)))
        self.log_wL.append(self.wal)
        self.log_wR.append(self.war)
        self.log_t.append(self.t)
        super()._dyn(dt)


def run_regime(name, g):
    i_stall, r_wind = g.pop("i_stall"), g.pop("r_wind")
    i_lim = g.pop("i_lim")
    s = LoggingSim(dict(g))
    s.run_mission(legs=4, tmax=120.0)
    if s.t >= 119.0:
        # mission stalled (the glue regime wedges on the RETURN leg - a
        # known controller bug found by this study). A wedged robot
        # grinding at the current limit is not racing heat: fall back to
        # clean forward runs, which is what a speed-run session is.
        print("  [%s] mission stalled at t=%.0f - using forward runs"
              % (name, s.t))
        s = LoggingSim(dict(g))
        s.run()
    t = np.array(s.log_t)
    WF = s.WF
    P, Praw = {}, {}
    for side, duty, w in (("L", s.log_dutyL, s.log_wL),
                          ("R", s.log_dutyR, s.log_wR)):
        duty = np.array(duty)
        w = np.array(w)
        i = i_stall * (duty - w/WF)
        Praw[side] = i*i*r_wind
        # driver current limit: plug-braking current is clamped by the
        # H-bridge (DRV8833/TB6612 class), so real copper loss caps here
        i_c = np.clip(i, -i_lim, i_lim)
        P[side] = i_c*i_c*r_wind
    p_avg = float((P["L"].mean() + P["R"].mean()) / 2.0)   # per motor
    p_peak = float(max(P["L"].max(), P["R"].max()))
    p_avg_raw = float((Praw["L"].mean() + Praw["R"].mean()) / 2.0)
    # adiabatic single-run heating: energy of one logged session dumped
    # into the winding mass with no time to dissipate (upper bound)
    e_run = p_avg * (float(t[-1]) if len(t) else 0.0)
    return dict(t=t, PL=P["L"], PR=P["R"], p_avg=p_avg, p_peak=p_peak,
                p_avg_raw=p_avg_raw, dT_run=e_run/CTH,
                mission_t=float(t[-1]) if len(t) else 0.0)


def thermal_curve(p_avg, minutes=15.0):
    """Single-node ODE at the mission-average power (tau >> lap time, so
    the ripple integrates out)."""
    tt = np.arange(0.0, minutes*60.0, 1.0)
    dT = p_avg*RTH*(1.0 - np.exp(-tt/(RTH*CTH)))
    return tt, T_AMB + dT


def main():
    out = {"assumptions": dict(RTH_K_per_W=RTH, C_J_per_K=CTH,
                               T_amb_C=T_AMB, T_limit_C=T_LIMIT)}
    results = {}
    for name, g in REGIMES.items():
        r = run_regime(name, dict(g))
        tt, temp = thermal_curve(r["p_avg"])
        t_ss = T_AMB + r["p_avg"]*RTH
        # time to hit the limit, if ever
        t_hit = None
        if t_ss > T_LIMIT:
            frac = (T_LIMIT - T_AMB) / (r["p_avg"]*RTH)
            t_hit = -RTH*CTH*math.log(1.0 - frac)
        results[name] = dict(r=r, tt=tt, temp=temp, t_ss=t_ss, t_hit=t_hit)
        out[name] = dict(dT_one_run_K=round(r["dT_run"], 1),
                         p_avg_W=round(r["p_avg"], 3),
                         p_avg_unlimited_W=round(r["p_avg_raw"], 2),
                         p_peak_W=round(r["p_peak"], 2),
                         T_steady_C=round(t_ss, 1),
                         minutes_to_limit=(round(t_hit/60.0, 1)
                                           if t_hit else None),
                         mission_logged_s=round(r["mission_t"], 1))
        print("%-20s P_avg %.2f W (unlim %.1f)  P_peak %.1f W  "
              "T_ss %.0f C  %s"
              % (name, r["p_avg"], r["p_avg_raw"], r["p_peak"], t_ss,
                 ("limit in %.1f min" % (t_hit/60) if t_hit else
                  "never hits limit")))

    # ---- figure -----------------------------------------------------------
    fig, axs = plt.subplots(2, 1, figsize=(8.8, 7.6), dpi=150)
    fig.patch.set_facecolor(SURF)
    fig.subplots_adjust(hspace=0.42, left=0.09, right=0.97, top=0.94,
                        bottom=0.08)

    def style(ax, title, xl, yl):
        ax.set_facecolor(SURF)
        for sp in ax.spines.values():
            sp.set_color(GRID)
        ax.grid(color=GRID, linewidth=0.7)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.set_title(title, color=INK, fontsize=10.5, loc="left", pad=8,
                     fontweight="bold")
        ax.set_xlabel(xl, color=MUTED, fontsize=8.5)
        ax.set_ylabel(yl, color=MUTED, fontsize=8.5)

    ax = axs[0]
    style(ax, "Copper loss per motor during a mission (4 legs, "
              "brake/turn pauses included)", "time (s)", "power (W)")
    cols = {k: c for k, c in zip(REGIMES, (C2, C1, C3))}
    for name, res in results.items():
        r = res["r"]
        # smooth for legibility: 0.5 s moving average
        k = 250
        p = np.convolve((r["PL"]+r["PR"])/2.0,
                        np.ones(k)/k, mode="same")
        ax.plot(r["t"][:len(p)], p, color=cols[name], lw=1.4,
                label="%s (avg %.2f W)" % (name, r["p_avg"]))
    leg = ax.legend(loc="upper right", fontsize=8, framealpha=0)
    for txt in leg.get_texts():
        txt.set_color(INK2)

    ax = axs[1]
    style(ax, "Winding temperature, continuous back-to-back missions "
              "(lumped node, still air)", "time (min)", "temperature (degC)")
    for name, res in results.items():
        ax.plot(res["tt"]/60.0, res["temp"], color=cols[name], lw=2,
                label="%s -> %.0f degC steady" % (name, res["t_ss"]))
    ax.axhline(T_LIMIT, color="#d03b3b", lw=1.4, ls="--")
    ax.annotate("N20 comfort limit %.0f degC" % T_LIMIT,
                (0.35, T_LIMIT+2), color="#d03b3b", fontsize=9)
    leg = ax.legend(loc="lower right", fontsize=8, framealpha=0)
    for txt in leg.get_texts():
        txt.set_color(INK2)

    png = os.path.join(HERE, "_thermal.png")
    fig.savefig(png, facecolor=SURF, bbox_inches="tight")
    print("wrote", png)
    with open(os.path.join(HERE, "thermal_data.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
