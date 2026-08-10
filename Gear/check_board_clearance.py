"""
check_board_clearance.py - what the board outline must give up for the gears.

The xiao board is drawn for DIRECT DRIVE: its two wheel notches (board
x 0..13 / 87..100, y 68..100) are centred on y = 84, the same axis as the
motors. A geared train puts the wheel axles 18.00 mm away at y = 66 and 102,
so those notches have to move and grow.

This intersects every drivetrain solid with the real imported board and reports
the interference, then emits the notch envelope the outline needs, in BOARD
coordinates, as dxf/board_notch_required.dxf for import into KiCad.
"""

import os

import cadquery as cq
from cadquery import exporters

import chassis_lib as C
import config as K
import generate_drivetrain as G

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    motor_g, idler, wheel_g = G.make_gears()
    asm = G.build_assembly(motor_g, idler, wheel_g)

    board = None
    parts = []
    for ch in asm.children:
        if ch.obj is None:
            continue
        s = ch.obj.val().moved(ch.loc)
        if ch.name.startswith("PCB_"):
            board = s
        else:
            parts.append((ch.name, s))
    if board is None:
        print("no PCB in assembly")
        return 1

    print("board vs drivetrain, with the outline AS DRAWN:\n")
    total = 0.0
    envx = [1e9, -1e9]
    envy = [1e9, -1e9]
    for name, s in parts:
        try:
            common = board.intersect(s)
            v = common.Volume() if common is not None else 0.0
        except Exception:
            continue
        if v > 1e-3:
            bb = common.BoundingBox()
            total += v
            envx = [min(envx[0], bb.xmin), max(envx[1], bb.xmax)]
            envy = [min(envy[0], bb.ymin), max(envy[1], bb.ymax)]
            print("  %-24s %9.2f mm3   X %7.2f..%7.2f  Y %7.2f..%7.2f"
                  % (name, v, bb.xmin, bb.xmax, bb.ymin, bb.ymax))
    print("\n  total board material in the way: %.1f mm3" % total)

    # Required notch envelope: everything the drivetrain occupies laterally
    # outboard of the inner plate, over the full longitudinal sweep.
    lat_in = K.Y_IN_IN - 0.5                    # inboard edge of the notch
    x_sweep = K.X_AXLE + K.WHEEL_DIA / 2.0 + 1.0
    print("\nREQUIRED notch, drivetrain frame:")
    print("   |Y| from %.2f outward past the board edge (%.2f)"
          % (lat_in, K.BOARD_W / 2.0))
    print("   X  %.2f .. %.2f" % (-x_sweep, x_sweep))

    bx0, bx1 = 0.0, K.BOARD_CX - lat_in         # board x of the left notch
    by0 = K.BOARD_MOTOR_Y - x_sweep
    by1 = K.BOARD_MOTOR_Y + x_sweep
    print("\nREQUIRED notch, BOARD coordinates (KiCad Edge.Cuts):")
    print("   left  : x %.2f .. %.2f   y %.2f .. %.2f" % (bx0, bx1, by0, by1))
    print("   right : x %.2f .. %.2f   y %.2f .. %.2f"
          % (K.BOARD_W - bx1, K.BOARD_W, by0, by1))
    print("   as drawn: x 0.00 .. 13.00   y 68.00 .. 100.00")
    print("   -> widen %.2f mm, lengthen %.2f mm at each end"
          % (bx1 - 13.0, 68.0 - by0))

    d = os.path.join(HERE, "dxf")
    os.makedirs(d, exist_ok=True)
    sk = cq.Workplane("XY")
    for (x0, x1) in ((bx0, bx1), (K.BOARD_W - bx1, K.BOARD_W)):
        sk = sk.moveTo(x0, by0).lineTo(x1, by0).lineTo(x1, by1) \
               .lineTo(x0, by1).close()
    plate = sk.extrude(1.0)
    path = os.path.join(d, "board_notch_required.dxf")
    exporters.export(plate.faces("<Z"), path)
    print("\nwrote %s  (board coords, 1:1)" % os.path.relpath(path, HERE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
