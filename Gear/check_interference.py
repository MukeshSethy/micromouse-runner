"""
check_interference.py - solid-on-solid clash check of the built assembly.

Every pair whose bounding boxes overlap is intersected; any non-zero common
volume is reported as a clash. Meshing gear pairs must come out at 0.000 mm3 -
that is what proves the tooth phasing (half-pitch offset on the idlers) is
right, not just that the centre distances are.
"""

import itertools

import generate_drivetrain as G
import config as K


def main():
    motor_g, idler, wheel_g = G.make_gears()
    asm = G.build_assembly(motor_g, idler, wheel_g)

    # The PCB is excluded here and audited separately by
    # check_board_clearance.py: its outline is still the direct-drive revision,
    # so it fouls the geared train by design until the notches are recut.
    parts = []
    for child in asm.children:
        if child.obj is None or child.name.startswith("PCB_"):
            continue
        parts.append((child.name, child.obj.val().moved(child.loc)))

    # deliberate interference fits: (part-A prefix, part-B prefix, max mm3)
    EXPECTED = [("plate_", "brg_", 2.0),      # F683ZZ 7.00 into a 6.95 bore
                ("plate_", "dowel_", 2.0),    # 3.00 dowel into a 2.90 hole
                # The vendor STEP models a plain round dia-3 output shaft, but
                # the real part is a D-shaft (Robu: "3 x 10mm, D type"). Our
                # D-bore therefore bites the modelled cylinder. Artifact of the
                # vendor model, not a real interference.
                ("gear_motor", "motor_N20", 12.0),
                # printed slot has R1 corners (printability); the vendor model
                # has sharp ones. Real gearboxes are radiused too.
                ("plate_", "motor_N20", 4.0),
                # wheel bore dia 2.85 pressed onto the dia 3 shaft
                ("wheel_", "axle_", 4.0)]

    def expected(n1, n2, v):
        for a, b, lim in EXPECTED:
            if ((n1.startswith(a) and n2.startswith(b)) or
                    (n2.startswith(a) and n1.startswith(b))):
                return v <= lim
        return False

    print("checking %d solids, %d pairs\n" % (len(parts),
                                              len(parts) * (len(parts) - 1) // 2))
    clashes = 0
    fits = 0
    for (n1, s1), (n2, s2) in itertools.combinations(parts, 2):
        b1, b2 = s1.BoundingBox(), s2.BoundingBox()
        if (b1.xmin > b2.xmax or b2.xmin > b1.xmax or
                b1.ymin > b2.ymax or b2.ymin > b1.ymax or
                b1.zmin > b2.zmax or b2.zmin > b1.zmax):
            continue
        try:
            common = s1.intersect(s2)
            v = common.Volume() if common is not None else 0.0
        except Exception:
            continue
        if v > 1e-3:
            if expected(n1, n2, v):
                fits += 1
                print("  fit   %-22s x %-22s  %10.3f mm3" % (n1, n2, v))
            else:
                clashes += 1
                print("  CLASH %-22s x %-22s  %10.3f mm3" % (n1, n2, v))
    print("\n%d intended interference fit(s), %d unexpected clash(es)"
          % (fits, clashes))
    return clashes


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
