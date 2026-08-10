"""
check_printability.py - support-free audit of every printed part.

For each part, in its intended print orientation, every face is tested for the
angle its surface makes with the build plate. A face is self-supporting if that
angle is >= 45 deg. Downward-facing faces shallower than that need support --
UNLESS they sit on the bed, or they are a short bridge between two walls.

Reported per part:
    BED       area resting on the build plate (good)
    OVERHANG  downward-facing area below the 45 deg rule, above the bed
    BRIDGE    of that, the part spanning <= BRIDGE_MAX across a hole

Run:  python check_printability.py
"""

import math

import cadquery as cq

import chassis_lib as C
import config as K

ANGLE_MIN = 45.0        # deg from the build plate
BRIDGE_MAX = 15.0       # mm, span a normal printer bridges unaided
EPS = 0.05


def _orient(wp, flip=False):
    """Return the solid with the bed at z = 0, optionally flipped first."""
    s = wp.val()
    if flip:
        s = s.rotate((0, 0, 0), (1, 0, 0), 180)
    bb = s.BoundingBox()
    return s.moved(cq.Location(cq.Vector(0, 0, -bb.zmin)))


def audit(name, wp, flip=False, note=""):
    s = _orient(wp, flip)
    bed_area = over_area = bridge_area = 0.0
    worst = []
    for f in s.Faces():
        try:
            u0, u1, v0, v1 = f._uvBounds()
            n = f.normalAt(cq.Vector((u0 + u1) / 2, (v0 + v1) / 2))
        except Exception:
            n = f.normalAt()
        nz = n.z
        if nz >= -1e-6:
            continue                       # not downward facing
        a = f.Area()
        bb = f.BoundingBox()
        if bb.zmax <= EPS:
            bed_area += a
            continue
        # surface angle from the build plate
        ang = math.degrees(math.asin(min(1.0, abs(nz))))
        ang = 90.0 - ang                   # 90 => vertical wall, 0 => flat roof
        if ang >= ANGLE_MIN - 1e-6:
            continue
        span = min(bb.xlen, bb.ylen)
        if span <= BRIDGE_MAX:
            bridge_area += a
        else:
            over_area += a
            worst.append((a, span, bb.zmin))
    worst.sort(reverse=True)
    verdict = "OK" if over_area < 1.0 else "NEEDS SUPPORT"
    print("%-26s bed %7.1f  bridge %6.1f  overhang %6.1f mm2   %s"
          % (name, bed_area, bridge_area, over_area, verdict))
    if note:
        print("%-26s   %s" % ("", note))
    for (a, span, z) in worst[:3]:
        print("%-26s   ! %.1f mm2 span %.1f at z %.2f" % ("", a, span, z))
    return over_area


def main():
    print("rule: downward faces must be >= %.0f deg from the bed; spans <= %.0f mm "
          "count as bridges\n" % (ANGLE_MIN, BRIDGE_MAX))
    total = 0.0
    total += audit("plate_inner", C.plate_inner(),
                   note="print outboard face down; ledge + gussets grow upward")
    total += audit("motor_cradle_LOWER", C.motor_tube_lower(),
                   note="print as modelled, trough opens upward")
    total += audit("motor_cradle_UPPER", C.motor_tube_upper(), flip=True,
                   note="print FLIPPED, outer face on the bed, trough upward")
    total += audit("shim_gear", C.shim(4.5, 3.1, K.AXLE_SHIM_T))
    total += audit("shim_wheel", C.shim(4.5, 3.1, K.WHEEL_SHIM_T))
    print("\ntotal unsupported overhang: %.2f mm2  -> %s"
          % (total, "SUPPORT-FREE" if total < 1.0 else "REVIEW"))
    return 0 if total < 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
