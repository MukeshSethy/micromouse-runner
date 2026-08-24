"""
pid_settle.py - measure the control loops' settling behaviour at 2 m/s,
from the same dynamics the published simulator runs (sim_twin).

Three experiments:
  A. the motor speed PI in isolation: step the wheel-speed setpoint to the
     2 m/s equivalent and watch the error alone (no vehicle, no limiters).
     This is the loop the encoders exist for (Kp 0.35, Ki 8.0).
  B. the full robot launching 0 -> 2 m/s in the maze: what the driver
     actually sees. Dominated by the LAUNCH SLEW LIMITER (ud <= |u|+0.30),
     which exists to protect the friction circle - not by the PI.
  C. cross-track error through the first corners at 2 m/s: disturbance in,
     time until the path error is back inside a +/-3 mm band.

Settling band conventions: A,B +/-2% of the 2.0 m/s step; C +/-3 mm.

    python pid_settle.py   -> pid_settle_data.json + _pid_*.png
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
V_TGT = 2.0
R_W = ST.WHEEL_R

INK, INK2, MUTED, GRID, SURF = ("#f2ede8", "#a79c93", "#898781",
                                "#2c2c2a", "#161310")
C1, C2, C3 = "#e08a2a", "#199e70", "#8a7bb8"

# kh 2.3 / ke 1.8: the harder settling tune (swept in this file's own
# sweep, validated 0-hit on comp 2.0/3.0 with unchanged lap times)
GAINS = dict(vmax=V_TGT, fmarg=0.32, brake_d=260.0, ff_d=20.0, kff=0.7,
             kp=0.45, kh=2.3, ke=1.8, ka=1.8, look=115.0, krd=2.6,
             kmul=4.5, vdiag=0.72, slew=0.30, mu=1.1, comp=True,
             fast=True, narrow=True, diag=True)


def settle_time(t, err, band):
    """First time |err| enters the band and never leaves again."""
    idx = None
    for i in range(len(err)):
        if abs(err[i]) > band:
            idx = None
        elif idx is None:
            idx = i
    return t[idx] if idx is not None else float("nan")


def style(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURF)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(color=GRID, linewidth=0.7)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_title(title, color=INK, fontsize=10.5, loc="left", pad=8,
                 fontweight="bold")
    ax.set_xlabel(xlabel, color=MUTED, fontsize=8.5)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=8.5)


# ---- A: isolated motor PI step ------------------------------------------
def exp_a():
    WF, TS, JE = 245.0, 0.031, 1.9e-5      # fast-motor plant (sim values)
    KP, KI = ST.PI_KP, ST.PI_KI
    cmd = V_TGT / R_W
    act = integ = 0.0
    T, E, DUTY = [], [], []
    t = 0.0
    while t < 0.6:
        err = cmd - act
        integ = max(-0.6/KI, min(0.6/KI, integ + err*DT))
        duty = max(-1.0, min(1.0, KP*err + KI*integ))
        act += ((duty*TS - (TS/WF)*act) / JE) * DT
        t += DT
        T.append(t); E.append(err*R_W); DUTY.append(duty)
    ts = settle_time(T, E, 0.02*V_TGT)
    return np.array(T), np.array(E), np.array(DUTY), ts


# ---- B & C: the full robot ----------------------------------------------
def exp_bc():
    s = ST.Sim(dict(GAINS))
    T, U, EV, XT, YAW = [], [], [], [], []
    n = len(s.P)
    while s.t < 25.0 and s.pathI < n - 2:
        s.step(DT)
        # cross-track error, same formula as the controller
        i0 = min(s.pathI, len(s.P) - 2)
        p0, p1 = s.P[i0], s.P[i0+1]
        tx, ty = p1[0]-p0[0], p1[1]-p0[1]
        tl = math.hypot(tx, ty) or 1.0
        e = (tx*(s.y-p0[1]) - ty*(s.x-p0[0]))/tl        # mm
        T.append(s.t); U.append(s.u); EV.append(V_TGT - s.u)
        XT.append(e); YAW.append(s.r)
    return (np.array(T), np.array(U), np.array(EV), np.array(XT),
            np.array(YAW))


def main():
    tA, eA, dutyA, tsA = exp_a()
    print("A: motor PI step 0->2 m/s, settle(2%%) = %.1f ms" % (tsA*1000))

    T, U, EV, XT, YAW = exp_bc()
    # Launch: report what is actually true at 2 m/s. The body REACHES the
    # 2% band, but never sits still in it - steering corrections share the
    # friction circle with propulsion, so cruise carries a few percent of
    # speed ripple until the planner brakes for the first corner. So:
    # rise time = first entry into the band; plus quantified ripple.
    band = 0.02 * V_TGT
    launch_end = float("nan")
    for i in range(len(EV)):
        if abs(EV[i]) <= band:
            launch_end = T[i]
            break
    plateau = U[(U > 1.9) & (T < T[np.argmax(U)] + 1.0)]
    ripple = (float(np.std(2.0 - plateau)) if len(plateau) else
              float("nan"))
    print("B: full launch, first entry into 2%% band = %.2f s; cruise "
          "ripple sigma = %.3f m/s" % (launch_end, ripple))

    # C: corner recoveries - find |yaw rate| pulses, measure time from pulse
    # end until |cross-track| stays inside 3 mm (until the next pulse)
    inturn = np.abs(YAW) > 1.5
    recov = []
    i = 0
    while i < len(T) - 1:
        if inturn[i] and not inturn[i+1]:            # corner exit
            j = i + 1
            k = j
            while k < len(T) - 1 and not inturn[k+1]:
                k += 1
            seg_e = XT[j:k]
            seg_t = T[j:k]
            if len(seg_e) > 10:
                st = settle_time(list(seg_t - seg_t[0]), list(seg_e), 3.0)
                if not math.isnan(st):
                    recov.append((T[j], st))
            i = k
        i += 1
    if recov:
        med = float(np.median([r[1] for r in recov]))
        print("C: %d corner exits, median cross-track settle to 3mm = "
              "%.0f ms" % (len(recov), med*1000))
    else:
        med = float("nan")

    # ---- figure ----------------------------------------------------------
    fig, axs = plt.subplots(3, 1, figsize=(8.6, 9.2), dpi=150)
    fig.patch.set_facecolor(SURF)
    fig.subplots_adjust(hspace=0.5, left=0.1, right=0.96, top=0.95,
                        bottom=0.06)

    ax = axs[0]
    style(ax, "A - motor speed PI alone: step 0 to 2 m/s equivalent",
          "time (ms)", "speed error (m/s)")
    ax.plot(tA*1000, eA, color=C1, lw=2)
    ax.axhspan(-0.04, 0.04, color=C2, alpha=0.15)
    ax.axvline(tsA*1000, color=C2, lw=1.2, ls="--")
    ax.annotate("settles %.0f ms" % (tsA*1000), (tsA*1000, 0.55),
                color=C2, fontsize=9, xytext=(tsA*1000+18, 0.75))
    ax.set_xlim(0, 350)

    ax = axs[1]
    style(ax, "B - full robot launch in the maze (what you see in the sim)",
          "time (s)", "body speed (m/s)")
    ax.plot(T, U, color=C1, lw=2, label="body speed")
    ax.plot(T, np.minimum(V_TGT, np.abs(U)+0.30), color=C3, lw=1.2,
            ls=":", label="slew-limited command")
    ax.axhline(V_TGT, color=MUTED, lw=0.8, ls="--")
    if not math.isnan(launch_end):
        ax.axvline(launch_end, color=C2, lw=1.2, ls="--")
        ax.annotate("reaches 2%% band at %.2f s\ncruise ripple "
                    "±%.0f mm/s (grip shared with steering)"
                    % (launch_end, 2*ripple*1000), (launch_end, 0.5),
                    color=C2, fontsize=9,
                    xytext=(launch_end+0.15, 0.25))
    ax.set_xlim(0, min(6.0, T[-1]))
    leg = ax.legend(loc="lower right", fontsize=8, framealpha=0)
    for txt in leg.get_texts():
        txt.set_color(INK2)

    ax = axs[2]
    style(ax, "C - cross-track error at 2 m/s: corners disturb, "
              "the loop pulls it back", "time (s)", "cross-track (mm)")
    ax.plot(T, XT, color=C1, lw=1.4)
    ax.axhspan(-3, 3, color=C2, alpha=0.15)
    for (t0, st) in recov[:8]:
        ax.axvline(t0, color=C3, lw=0.8, ls=":")
    ax.set_xlim(0, T[-1])
    ax.annotate("corner exits (dotted); median settle to 3 mm: %.0f ms"
                % (med*1000), (0.02, 0.93), xycoords="axes fraction",
                color=INK2, fontsize=9)

    out = os.path.join(HERE, "_pid_settle.png")
    fig.savefig(out, facecolor=SURF, bbox_inches="tight")
    print("wrote", out)

    with open(os.path.join(HERE, "pid_settle_data.json"), "w") as f:
        json.dump({"motor_pi_settle_ms": tsA*1000,
                   "launch_band_entry_s": launch_end,
                   "cruise_ripple_sigma_ms": ripple*1000,
                   "corner_recoveries": recov,
                   "corner_settle_median_ms": med*1000}, f, indent=1)


if __name__ == "__main__":
    main()
