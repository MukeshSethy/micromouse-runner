"""
mold_tyre.py v2 - TWO-part pour-through-the-wheel tyre mould.

v1 (three parts, lid pour holes) had a defect the user's question exposed:
the pour holes landed on the wheel's top flange - solid plastic - so the
cavity could never be filled. Interference and printability were verified;
FILL PATH was not. v2 verifies it explicitly.

v2 concept: the hollow printed wheel is its own runner system.
    - CUP  = base + ring merged: recess seats the bottom flange, bore defines
      the tyre OD, an internal step rings the top flange (0.10 radial gap =
      the vent). Three ejector holes in the floor push the finished
      wheel+tyre out.
    - PLUG = lid with a central boss that fills the wheel's hollow interior,
      leaving a 1.5 mm plenum above the hub floor and a central pour funnel.
Silicone: funnel -> plenum -> three dia-3 feed gates (the lower keying row)
-> cavity -> rises -> vents at the flange gap ring. The cured sprue and
plenum puck pull out with the plug and are snipped at the gates.

    python mold_tyre.py    -> step/mold_cup_x1.step, step/mold_plug_x1.step,
                              step/wheel_printable_keyed_x4.step + report
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
TYRE_OD = K.WHEEL_DIA                     # 27.0 - what every simulation used
SHRINK_COMP = 0.15
MOLD_BORE = TYRE_OD + SHRINK_COMP

FL_D, CH_D = K.WHEEL_FLANGE_D, K.WHEEL_CHAN_D       # 26.52 / 23.31
W, FL_W = K.WHEEL_W, K.WHEEL_FLANGE_W               # 19.06 / 1.5
CH_W = W - 2 * FL_W
INNER_D = CH_D - 3.0                                # 20.31 hollow interior
HUB_T = 4.5                                         # hub floor thickness

FLOOR_T = 3.0
RECESS_D = FL_W + 0.05
RECESS_CLR = 0.10
STEP_CLR = 0.10                # radial gap ring at the top flange = THE VENT
CUP_OD = 40.0
# rim 0.06 UNDER the wheel top: the plug plate lands on the WHEEL first -
# that preload seals the flanges; the hairline rim gap is the overflow
CUP_H = FLOOR_T + W - 0.06
PIN_D, PIN_H = K.WHEEL_BORE - 0.05, 3.5
EJECT_D, EJECT_R = 4.0, 8.5    # ejector holes under the hub disc
BOLT_BC, BOLT_N = 34.0, 3      # M3, bosses outside the cup wall
PLUG_CLR = 0.15
PLENUM_H = 2.6                 # plug boss stops this far above the hub floor
                               # (2.6 not 1.5: the dia-3 feed gates sit at
                               # z 6.85 in the wheel frame and the plenum roof
                               # must clear them - v2's own fill check caught
                               # the 1.5 version covering the gates)
FUNNEL_D = 6.0
PLATE_T = 4.0


def _cyl(d, h, z=0.0):
    return cq.Workplane("XY").circle(d / 2).extrude(h).translate((0, 0, z))


def _bolt_bosses(solid, z0, h, d):
    for k in range(BOLT_N):
        a = math.radians(120 * k + 60)
        x, y = BOLT_BC / 2 * math.cos(a), BOLT_BC / 2 * math.sin(a)
        solid = solid.union(_cyl(7.0, h, z0).translate((x, y, 0)))
        solid = solid.cut(_cyl(d, h + 2, z0 - 1).translate((x, y, 0)))
    return solid


def mold_cup():
    """Base + ring in one print. The wheel drops in through the top: the
    flange (26.52) passes the step ID (26.72) and the bore (27.15), then
    seats in the recess (26.72)."""
    # wheel bottom sits ON the recess floor at z = FLOOR_T; every bore
    # segment is measured from there (the first stack double-counted the
    # flange and left a 517 mm3 ceiling inside the mould)
    zw = FLOOR_T
    c = _cyl(CUP_OD, CUP_H)
    c = c.cut(_cyl(FL_D + 2 * RECESS_CLR, FL_W + 0.05, zw))
    c = c.cut(_cyl(MOLD_BORE, CH_W + 0.05, zw + FL_W - 0.05))
    lip = (MOLD_BORE - FL_D - 2 * STEP_CLR) / 2
    # step bore starts one lip-height above the cavity; the 45-deg cone sits
    # IN that band so the step's inner edge tapers instead of overhanging the
    # wider bore below (carving the cone below the seam fixed nothing - the
    # cantilevered ring lives in the material ABOVE it)
    c = c.cut(_cyl(FL_D + 2 * STEP_CLR, FL_W + 1.0, zw + FL_W + CH_W + lip))
    cone = cq.Solid.makeCone(MOLD_BORE / 2, (FL_D + 2 * STEP_CLR) / 2, lip)
    c = c.cut(cq.Workplane("XY").newObject([cone]).translate(
        (0, 0, zw + FL_W + CH_W)))
    # 45-deg transition at the recess->bore widening (prints upright clean)
    cone2 = cq.Solid.makeCone((FL_D + 2 * RECESS_CLR) / 2, MOLD_BORE / 2,
                              (MOLD_BORE - FL_D - 2 * RECESS_CLR) / 2)
    c = c.cut(cq.Workplane("XY").newObject([cone2]).translate(
        (0, 0, zw + FL_W - 0.05)))
    c = c.union(_cyl(PIN_D, PIN_H, zw))
    for k in range(3):
        a = math.radians(120 * k)
        c = c.cut(_cyl(EJECT_D, FLOOR_T + RECESS_D + 2, -1).translate(
            (EJECT_R * math.cos(a), EJECT_R * math.sin(a), 0)))
    c = _bolt_bosses(c, 0.0, CUP_H, 2.90)
    return c


def mold_plug():
    """Lid + interior plug: the boss fills the wheel hollow leaving a plenum
    over the hub floor; the funnel feeds it; the shoulder clamps the wheel."""
    p = _cyl(CUP_OD, PLATE_T)
    boss_h = (W - HUB_T) - PLENUM_H
    p = p.union(_cyl(INNER_D - 2 * PLUG_CLR, boss_h, -boss_h))
    # no shoulder disc: the plate underside itself lands on the wheel top
    # (a shoulder overlapped the flange it was meant to press on)
    p = p.cut(_cyl(FUNNEL_D, PLATE_T + boss_h + 2, -boss_h - 1))
    fc = cq.Solid.makeCone(7.5, FUNNEL_D / 2, 3.0)
    p = p.cut(cq.Workplane("XY").newObject([fc]).translate((0, 0, PLATE_T - 3)))
    p = _bolt_bosses(p, 0.0, PLATE_T, 3.30)
    return p


def verify():
    print("== pour-through-the-wheel mould, v2 ==")
    z_wheel = FLOOR_T
    cav = math.pi / 4 * (MOLD_BORE ** 2 - CH_D ** 2) * CH_W
    print("cavity %.1f ml; plenum + sprue waste ~%.1f ml"
          % (cav / 1000.0,
             (math.pi / 4 * INNER_D ** 2 * PLENUM_H
              + math.pi / 4 * FUNNEL_D ** 2 * 15) / 1000.0))

    # ---- FILL PATH: the check v1 never had -------------------------------
    gate_z_local = FL_W + CH_W / 3.0                 # lower keying row (wheel frame)
    plenum_roof_local = HUB_T + PLENUM_H
    print("wheel frame: plenum z %.2f..%.2f, feed gates z %.2f"
          % (HUB_T, plenum_roof_local, gate_z_local))
    assert FL_W < gate_z_local < FL_W + CH_W, "gates must open into the cavity"
    assert gate_z_local < plenum_roof_local,         "plug boss covers the feed gates - unfillable"
    print("gate area %.1f mm2 (3x dia 3), vent ring %.1f mm2"
          % (3 * math.pi / 4 * 9.0, math.pi * FL_D * STEP_CLR))

    # ---- interference -----------------------------------------------------
    wheel = (C.wheel_placeholder(bare=True, keyed=True).val()
             .moved(cq.Location(cq.Vector(0, 0, z_wheel))))
    cup = mold_cup().val()
    plug = (mold_plug().val()
            .moved(cq.Location(cq.Vector(0, 0, z_wheel + W))))
    ok = True
    for n, p in (("cup ", cup), ("plug", plug)):
        inter = wheel.intersect(p)
        v = inter.Volume() if inter else 0.0
        print("wheel x %s %8.3f mm3  %s" % (n, v, "ok" if v < 0.8 else "CLASH"))
        ok = ok and v < 0.8
    inter = cup.intersect(plug)
    v = inter.Volume() if inter else 0.0
    print("cup   x plug %8.3f mm3  %s" % (v, "ok" if v < 0.8 else "CLASH"))
    ok = ok and v < 0.8
    return ok


def main():
    os.makedirs(STEP, exist_ok=True)
    ok = verify()
    for name, wp in (("wheel_printable_keyed_x4",
                      C.wheel_placeholder(bare=True, keyed=True)),
                     ("mold_cup_x1", mold_cup()),
                     ("mold_plug_x1", mold_plug())):
        path = os.path.join(STEP, name + ".step")
        exporters.export(wp, path)
        print("  %-30s %7.1f kB" % (name + ".step",
                                    os.path.getsize(path) / 1024.0))
    for stale in ("mold_tyre_base_x1", "mold_tyre_ring_x1", "mold_tyre_lid_x1"):
        p = os.path.join(STEP, stale + ".step")
        if os.path.exists(p):
            os.remove(p)
            print("  removed defective v1 part: %s.step" % stale)
    print("verification:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
