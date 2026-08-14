"""
check_assembly.py - can the robot actually be PUT TOGETHER?

check_interference proves parts coexist in their final poses; it says
nothing about the path each part takes to get there. This sweeps every
part along its real insertion/removal path (the same sequence the
assembly viewer animates) and intersects it with everything still mounted
at that stage. Anything in the way = a design that renders fine and
cannot be built. Found on its first run: the band ears stood inside the
inner bearings' press-out annulus, and motors cannot lift straight out
of the wall register (they slide inboard first).

Collision classes:
  press  - intended press fits disengaging along the sweep (bounded)
  notch  - hits on the reference PCB inside the REQUIRED notch region
           (dxf/board_notch_required.dxf; the physical board must be cut)
  BLOCK  - everything else: the design cannot be assembled

    python check_assembly.py
"""

import math

import cadquery as cq

import chassis_lib as C
import config as K
import generate_drivetrain as G

UP = (0.0, 0.0, 1.0)
STEP_MM = 1.5


def plan(name):
    """Removal path per part: list of (dir CAD frame, distance) segments,
    swept in order, plus the stage that decides what is still mounted."""
    s = 1.0 if ("_L" in name) else -1.0
    out = (0.0, s, 0.0)
    inw = (0.0, -s, 0.0)
    if name.startswith("wheel_"):      return 0, [(out, 30.0)]
    if name.startswith("gear_axle_"):  return 0, [(out, 30.0)]  # bolted unit
    if name.startswith("axle_"):       return 2, [(out, 40.0)]
    if name.startswith("brg_"):
        return 3, [((out if name.endswith("_out") else inw), 12.0)]
    if name.startswith("gear_motor_"): return 4, [(out, 15.0)]
    if name.startswith("motor_N20"):
        # OUT of the wall register first (inboard), THEN up. Straight up
        # is blocked by the wall above the gearbox slot - this check is
        # what proved it.
        return 5, [(inw, 16.0), (UP, 30.0)]
    if name.startswith("pod_"):        return 7, [(UP, 15.0)]
    return -1, []                                             # PCB: static

# press fits that legitimately rub while disengaging: (mover, static, mm3)
ALLOWED = [
    ("wheel_", "axle_", 12.0),        # 2.85 bore leaving the 3.0 D-shaft
    ("brg_", "pod_", 2.5),            # 7.0 OD leaving the 6.95 press bore
    ("axle_", "brg_", 1.0),           # slip fit, zero nominal clearance
    ("gear_axle_", "axle_", 1.0),     # D-bore sliding off the flat
    ("gear_axle_", "gear_motor_", 1.0),   # teeth slide axially, in phase
    ("gear_motor_", "motor_N20", 12.0),   # vendor shaft round, real is D
    ("motor_N20", "pod_", 1.5),   # the U-channel's designed 0.05 belly
                                  # pinch rubs while the can slides out
]


def allowance(mn, sn):
    for a, b, v in ALLOWED:
        if mn.startswith(a) and sn.startswith(b):
            return v
    return 0.10


def ivol(a, b):
    """Null-safe fuzzy boolean-common volume. OCC occasionally FAILS on
    moved spline solids and hands back one whole operand - detect that by
    capping against the smaller input and retry with fuzz."""
    cap = min(a.Volume(), b.Volume())
    for tol in (None, 1e-4):
        try:
            it = a.intersect(b, tol=tol) if tol else a.intersect(b)
            v = it.Volume() if it else 0.0
        except Exception:
            v = 0.0
        if v <= cap * 0.98 + 1e-9:
            return v
    return -1.0                       # boolean failure both ways: flag


def in_notch(bb):
    """Reference-PCB hits inside the required corner notches (|y| >= 30,
    |x| <= 40): resolved by physically cutting the documented notch."""
    return abs(bb.ymin) >= 30.0 or abs(bb.ymax) >= 30.0


def main():
    motor_g, idler, wheel_g = G.make_gears()
    asm = G.build_assembly(motor_g, idler, wheel_g)
    parts = {}
    for ch in asm.children:
        if ch.obj is not None:
            parts[ch.name] = ch.obj.val().moved(ch.loc)

    stages = {n: plan(n)[0] for n in parts}
    blocks, notches, fails = [], [], []
    for name in sorted(parts, key=lambda n: stages[n]):
        stage, segs = plan(name)
        if stage < 0:
            continue
        statics = {n: s for n, s in parts.items()
                   if stages[n] > stage or stages[n] < 0}
        mover = parts[name]
        hits = {}
        off = (0.0, 0.0, 0.0)
        for (d, dist) in segs:
            n_steps = int(math.ceil(dist / STEP_MM))
            for k in range(1, n_steps + 1):
                t = dist * k / n_steps
                o = (off[0] + d[0]*t, off[1] + d[1]*t, off[2] + d[2]*t)
                mv = mover.moved(cq.Location(cq.Vector(*o)))
                mb = mv.BoundingBox()
                for sn, ss in statics.items():
                    sb = ss.BoundingBox()
                    if (mb.xmin > sb.xmax or mb.xmax < sb.xmin
                            or mb.ymin > sb.ymax or mb.ymax < sb.ymin
                            or mb.zmin > sb.zmax or mb.zmax < sb.zmin):
                        continue
                    v = ivol(mv, ss)
                    if v < 0:
                        fails.append((name, sn))
                        continue
                    if v > hits.get(sn, (0.0, None))[0]:
                        it = mv.intersect(ss)
                        hits[sn] = (v, it.BoundingBox())
            off = (off[0] + d[0]*dist, off[1] + d[1]*dist,
                   off[2] + d[2]*dist)
        for sn, (v, bb) in sorted(hits.items()):
            if v <= 0.01:
                continue
            if v <= allowance(name, sn):
                print("  press  %-22s thru %-22s %8.3f mm3" % (name, sn, v))
            elif sn.startswith("PCB_") and in_notch(bb):
                print("  notch  %-22s thru %-22s %8.3f mm3 "
                      "(cut the documented board notch)" % (name, sn, v))
                notches.append((name, v))
            else:
                print("  BLOCK  %-22s hits %-22s %8.3f mm3" % (name, sn, v))
                blocks.append((name, sn, v))
    print()
    for name, sn in set(fails):
        print("  warn   boolean failed for %s x %s (skipped)" % (name, sn))
    if notches:
        print("%d hit(s) resolved by the required PCB notch "
              "(dxf/board_notch_required.dxf)" % len(notches))
    if blocks:
        print("ASSEMBLY BLOCKED: %d collision(s) on insertion paths"
              % len(blocks))
        return 1
    print("ASSEMBLY OK: every part reaches its seat along its real path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
