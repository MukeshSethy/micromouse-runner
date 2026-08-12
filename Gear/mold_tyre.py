"""
mold_tyre.py - 3-part printed mould for casting silicone tyres in place on
the mini-sumo wheel (19.06 wide, flanges dia 26.52, channel dia 23.31).

Concept: the WHEEL IS THE CORE. It clamps between base and lid; the ring's
stepped bore defines the tyre OD and radially seals the top flange, the base
recess seals the bottom flange. Silicone is poured through the lid into the
annulus over the channel, cures in place, and the tyre stays on the wheel -
no demoulding of the tyre itself, only of the printed parts.

Stack arithmetic (Z up, base deck = 0):
    recess floor      -RECESS_D
    wheel bottom      -RECESS_D            (flange 1 seated)
    channel           -RECESS_D + FL_W ... + FL_W + CH_W
    wheel top         -RECESS_D + 19.06 = 17.51
    ring top          17.45  (0.06 UNDER the wheel: clamp lands on the WHEEL,
                              sealing the flanges; the hairline lid-ring gap
                              is the overflow path)

    python mold_tyre.py     -> step/mold_*.step + verification report
"""

import math
import os

import cadquery as cq
from cadquery import exporters

import chassis_lib as C
import config as K

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.join(HERE, "step")

# ---- parameters ----------------------------------------------------------
TYRE_OD = K.WHEEL_DIA          # 27.0 - what every simulation ran on
SHRINK_COMP = 0.15             # tin-cure silicone shrinks ~0.2-0.4%; platinum ~0
MOLD_BORE = TYRE_OD + SHRINK_COMP

FL_D, CH_D = K.WHEEL_FLANGE_D, K.WHEEL_CHAN_D      # 26.52 / 23.31
W, FL_W = K.WHEEL_W, K.WHEEL_FLANGE_W              # 19.06 / 1.5
CH_W = W - 2 * FL_W                                # 16.06 cavity height

RECESS_D = FL_W + 0.05         # bottom flange seat depth
RECESS_CLR = 0.10              # radial, flange into recess
RING_OD = 33.0
RING_H = (W - RECESS_D) - 0.06 # 0.06 under wheel top: clamp lands on wheel
STEP_H = FL_W + 0.10           # stepped bore: seals the TOP flange radially
BASE_D, PLATE_T = 46.0, 4.0
UPSTAND_H = 3.0
PIN_D, PIN_H = K.WHEEL_BORE - 0.05, 4.0            # 2.80, enters the hub bore
BOLT_BC, BOLT_N = 39.0, 3
POUR_D, VENT_D = 4.5, 1.8
POUR_R = (CH_D / 2 + MOLD_BORE / 2) / 2            # mid-annulus


def _cyl(d, h, z=0.0):
    return cq.Workplane("XY").circle(d / 2).extrude(h).translate((0, 0, z))


def _bolts(solid, d, h, z0):
    for k in range(BOLT_N):
        a = math.radians(120 * k + 60)
        solid = solid.cut(_cyl(d, h, z0).translate(
            (BOLT_BC / 2 * math.cos(a), BOLT_BC / 2 * math.sin(a), 0)))
    return solid


def mold_base():
    b = _cyl(BASE_D, PLATE_T, -PLATE_T)
    # upstand ring that registers the mould ring's OD
    b = b.union(_cyl(RING_OD + 6.0, UPSTAND_H).cut(_cyl(RING_OD + 0.10,
                                                        UPSTAND_H + 1)))
    # flange seat recess + centre pin (belt and braces on concentricity)
    b = b.cut(_cyl(FL_D + 2 * RECESS_CLR, RECESS_D + 1.0, -RECESS_D))
    b = b.union(_cyl(PIN_D, PIN_H, -RECESS_D))
    b = _bolts(b, 2.90, PLATE_T + 2, -PLATE_T - 1)     # M3 tap in the base
    return b


def mold_ring():
    r = _cyl(RING_OD, RING_H)
    r = r.cut(_cyl(MOLD_BORE, RING_H + 2, -1))
    # stepped bore over the top flange: seals it radially so silicone spans
    # ONLY the channel - no flash ring bonded over the flange edge
    step = (_cyl(MOLD_BORE + 2, STEP_H, RING_H - STEP_H)
            .cut(_cyl(FL_D + 2 * RECESS_CLR, STEP_H + 2, RING_H - STEP_H - 1)))
    r = r.union(step.intersect(_cyl(RING_OD, STEP_H, RING_H - STEP_H)))
    # 45-degree transition under the step so the ring prints bore-down
    cone = cq.Solid.makeCone((MOLD_BORE) / 2, (FL_D + 2 * RECESS_CLR) / 2,
                             (MOLD_BORE - FL_D - 2 * RECESS_CLR) / 2)
    r = r.cut(cq.Workplane("XY").newObject([cone]).translate(
        (0, 0, RING_H - STEP_H - (MOLD_BORE - FL_D - 2 * RECESS_CLR) / 2)))
    return r


def mold_lid():
    l = _cyl(BASE_D, PLATE_T)
    # shallow register capturing the ring top
    l = l.union(_cyl(RING_OD + 6.0, 2.5, -2.5).cut(
        _cyl(RING_OD + 0.10, 3.5, -3.0)))
    for a_deg, d in ((0, POUR_D), (180, POUR_D), (90, VENT_D), (270, VENT_D)):
        a = math.radians(a_deg)
        l = l.cut(_cyl(d, PLATE_T + 6, -3.0).translate(
            (POUR_R * math.cos(a), POUR_R * math.sin(a), 0)))
    l = _bolts(l, 3.30, PLATE_T + 6, -3.0)             # M3 clearance
    return l


def verify():
    print("== tyre mould verification ==")
    cav_v = math.pi / 4 * (MOLD_BORE ** 2 - CH_D ** 2) * CH_W
    print("cavity: bore %.2f  channel %.2f  height %.2f  -> silicone %.1f ml"
          % (MOLD_BORE, CH_D, CH_W, cav_v / 1000.0))
    print("stack : wheel top above deck %.2f, ring top %.2f (%.2f preload gap)"
          % (W - RECESS_D, RING_H, (W - RECESS_D) - RING_H))
    assert (W - RECESS_D) - RING_H > 0.02, "clamp must land on the wheel"

    # wheel (BARE - no silicone) placed as the core, deck at z=0
    wheel = (C.wheel_placeholder(bare=True).val()
             .moved(cq.Location(cq.Vector(0, 0, -RECESS_D))))
    parts = {"base": mold_base().val(), "ring": mold_ring().val(),
             # the lid clamps ON THE WHEEL (its top face, 0.06 above the
             # ring) - that preload is what seals the flanges
             "lid": mold_lid().val()
                    .moved(cq.Location(cq.Vector(0, 0, W - RECESS_D)))}
    ok = True
    for n, p in parts.items():
        try:
            inter = wheel.intersect(p)
            v = inter.Volume() if inter else 0.0
        except Exception:
            v = 0.0
        flag = "ok" if v < 0.8 else "CLASH"
        if v >= 0.8:
            ok = False
        print("wheel x %-5s intersection %7.3f mm3  %s" % (n, v, flag))
    for a, b in (("base", "ring"), ("ring", "lid")):
        inter = parts[a].intersect(parts[b])
        v = inter.Volume() if inter else 0.0
        print("%s x %s intersection %7.3f mm3  %s"
              % (a, b, v, "ok" if v < 0.8 else "CLASH"))
        ok = ok and v < 0.8
    return ok


def main():
    os.makedirs(STEP, exist_ok=True)
    ok = verify()
    for name, wp in (("mold_tyre_base_x1", mold_base()),
                     ("mold_tyre_ring_x1", mold_ring()),
                     ("mold_tyre_lid_x1", mold_lid())):
        path = os.path.join(STEP, name + ".step")
        exporters.export(wp, path)
        print("  %-28s %7.1f kB" % (name + ".step",
                                    os.path.getsize(path) / 1024.0))
    print("verification:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
