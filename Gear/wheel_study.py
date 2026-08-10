"""
wheel_study.py - re-pick the drivetrain for the REAL mini-sumo wheel.

Measured from miniSumoWheel.3mf (see slice/confirm scripts):
    tyre channel   dia 23.31   flanges dia 26.52   width 19.06
    bolt circle    dia 16.052  6 x dia 3.587
    centre bore    dia 2.85
With 1.5-2.0 mm of silicone in the channel the rolling dia is ~26.3-27.3.

Two questions:
  A. can the drive gear bolt straight to that bolt circle?
  B. if not, what ratio does a 3-gear layout give on this wheel?
"""
import math

M = 0.5
BOLT_R = 8.026           # measured
BOLT_HOLE_R = 1.7935     # measured
HOLE_OUTER = BOLT_R + BOLT_HOLE_R      # 9.820
WHEEL_DIA = 27.0         # channel 23.31 + 2 x ~1.85 silicone
AXLE_Z = WHEEL_DIA / 2.0
WEB = 1.2                # material needed between a bolt hole and a tooth root

tip = lambda n, m=M: m * (n + 2) / 2.0
root = lambda n, m=M: m * (n - 2.5) / 2.0

print("wheel: rolling dia %.2f -> axle line Z = %.2f" % (WHEEL_DIA, AXLE_Z))
print("bolt circle dia %.3f, holes dia %.3f, holes reach r = %.3f\n"
      % (2*BOLT_R, 2*BOLT_HOLE_R, HOLE_OUTER))

print("A. GEAR BOLTED TO THE WHEEL")
print("   the gear must have solid material out past the bolt holes:")
print("     root radius >= %.3f + %.1f = %.3f" % (HOLE_OUTER, WEB,
                                                  HOLE_OUTER + WEB))
best = None
for mm in (0.3, 0.4, 0.5, 0.6, 0.8):
    nmin = None
    for n in range(10, 120):
        if root(n, mm) >= HOLE_OUTER + WEB:
            nmin = n
            break
    if nmin is None:
        continue
    clr = AXLE_Z - tip(nmin, mm)
    print("     m%.1f -> needs >= %3dT, tip r %6.3f, ground clearance %6.3f"
          % (mm, nmin, tip(nmin, mm), clr))
    if best is None or clr > best[0]:
        best = (clr, mm, nmin)
print("   best case: %.2f mm of ground clearance (m%.1f, %dT)"
      % (best[0], best[1], best[2]))
print("   VERDICT: %s\n" % ("viable" if best[0] >= 2.5 else
      "NOT VIABLE - the bolt circle is too big for this wheel radius"))

print("B. 3-GEAR LAYOUT, gear on the axle (wheel presses on the same shaft)")
print("   WB = m(Nm+Nw) must clear the tyre; tip must clear the floor\n")
print("   %-22s %-11s %8s %8s %8s %8s %7s"
      % ("constraints", "teeth", "C", "WB", "tyregap", "gndclr", "ratio"))
print("   " + "-" * 78)
picks = []
for gap_min, gnd_min in ((3.0, 4.0), (2.5, 3.5), (2.5, 3.0), (2.0, 2.5)):
    bst = None
    for nm in range(17, 60):          # 17T = undercut limit at 20 deg
        for nw in range(17, 90):
            wb = M * (nm + nw)
            if wb - WHEEL_DIA < gap_min:
                continue
            if AXLE_Z - tip(nw) < gnd_min:
                continue
            r = nw / float(nm)
            if bst is None or r > bst[0]:
                bst = (r, nm, nw, wb)
    if bst:
        r, nm, nw, wb = bst
        print("   %-22s %-11s %8.2f %8.2f %8.2f %8.2f %6.2f:1"
              % ("gap>=%.1f gnd>=%.1f" % (gap_min, gnd_min),
                 "%dT x %dT" % (nm, nw), wb/2, wb, wb - WHEEL_DIA,
                 AXLE_Z - tip(nw), r))
        picks.append(bst)

print("\n   board-y landing points (motor axis stays at board y = 84):")
for (r, nm, nw, wb) in picks:
    print("     %2dT x %2dT  %.2f:1  axles at board y %.2f / %.2f"
          % (nm, nw, r, 84 - wb/2, 84 + wb/2))

print("\nC. LATERAL STACK IMPACT")
print("   wheel is %.2f wide (was 6.5) - the track grows by %.2f per side"
      % (19.06, 19.06 - 6.5))
print("   notch must widen to clear a %.2f wide wheel" % 19.06)
