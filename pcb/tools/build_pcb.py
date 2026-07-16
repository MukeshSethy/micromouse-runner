import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import PcbGen
import pcbnew

# Rev 5 (2026-07-16). User directives + deep research (all verified primary):
#  - TB6612 bare SMD (U2), sockets gone.
#  - Motors FORWARD (axle y=84); the rear is the service/drive panel: ESP32
#    module with the ANTENNA OVERHANGING THE REAR EDGE (Espressif-preferred;
#    user-chosen over the interior slot), USB-C, JTAG, lettered buttons,
#    TB6612 + motor connectors + battery -- everything near the module.
#  - N20 bracket = UKMARSBot printable Pololu-pattern clone (STL-measured):
#    2x D3.2mm NPTH per motor, 18.0mm c-c, perpendicular to the motor axis,
#    4.25mm inboard of the gearbox faceplate. Bracket tabs span 26.6mm.
#    STL: github.com/ukmars/ukmarsbot -> mechanical/pololu-gear-motor-bracket-standard.stl
#  - Wall sensors per the research synthesis (UKMARSBOT advanced V1.2 parsed
#    + Decimus/Zeetah doctrine): per cluster the DETECTOR sits FORWARD and
#    the EMITTER 7.6mm BEHIND, in-line along the local board edge, both
#    co-aimed; front pairs 10 deg toe-out, diagonal 45 deg (the chamfer
#    normal), side 75 deg (15 deg forward of perpendicular -- never exactly
#    90 to a shiny wall). Assembly: bend up ~5 deg (spot ~20mm above floor),
#    heat-shrink emitters, epoxy after alignment.
#  - Bottom face carries SMD passives (user permission) to decongest the top.
#  - In1 = GND plane, In2 = +3V3 plane (stitched + filled); signals on F/B.

from board_geom import (BOARD_W, BOARD_H, CX, AXLE_Y, WHEEL_THK, WHEEL_DIA,
                        WHEEL_INSET, CHAMF, FACE_L, FACE_R, BOARD_OUTLINE,
                        WHEEL_SLOTS, MOTOR_KEEPOUTS, MOUNT_HOLES)

NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"
g = PcbGen(NETLIST)
g.board.SetCopperLayerCount(4)
g.add_outline(BOARD_OUTLINE)

def sensor_refs(i):
    return {
        "photo": f"Q{2 + i}", "pullup": f"R{13 + 2*i}", "curr": f"R{14 + 2*i}",
        "led": f"D{1 + i}",
    }

# ---------------------------------------------------------------------------
# WALL sensors -- research-synthesis coordinates (absolute, this board frame).
# det = SFH309 detector (forward), emit = SFH4550 emitter (7.6mm behind along
# the edge), both TOP face, bent-lead co-aimed. Support passives on BOTTOM.
# ---------------------------------------------------------------------------
WALL_GEOM = [
    # i, det(x,y),      emit(x,y),     rot(silk/hole axis)
    (0, (33.8, 3.5),  (26.2, 3.5),  0),    # FRONT-L, aim 10 deg left
    (1, (66.2, 3.5),  (73.8, 3.5),  0),    # FRONT-R, aim 10 deg right
    (2, (12.0, 9.5),  (7.0, 14.5),  45),   # DIAG-L, aim 45 (chamfer normal)
    (3, (88.0, 9.5),  (93.0, 14.5), 315),  # DIAG-R
    (4, (5.0, 24.0),  (5.0, 31.5),  90),   # SIDE-L, aim 75
    (5, (95.0, 24.0), (95.0, 31.5), 270),  # SIDE-R
]
for i, det, emit, rot in WALL_GEOM:
    r = sensor_refs(i)
    g.place(r["photo"], det[0], det[1], rot=rot)
    g.place(r["led"], emit[0], emit[1], rot=rot)
# Support passives: two BOTTOM-face columns at the board edges below the side
# pairs (clear of the line array x>=15 and of every sensor hole).
for k, i in enumerate((0, 2, 4)):              # left column: WALL1/3/5
    r = sensor_refs(i)
    g.place(r["pullup"], 4, 36 + 4*k, flip=True)
    g.place(r["curr"], 10, 36 + 4*k, flip=True)
for k, i in enumerate((1, 3, 5)):              # right column: WALL2/4/6
    r = sensor_refs(i)
    g.place(r["pullup"], BOARD_W - 4, 36 + 4*k, flip=True)
    g.place(r["curr"], BOARD_W - 10, 36 + 4*k, flip=True)

# --- LINE sensors (bottom) + line indicators (top, same columns) ---
LINE_X0 = CX - 3.5 * 9.525
for i in range(6, 14):
    x = LINE_X0 + (i - 6) * 9.525
    r = sensor_refs(i)
    g.place(r["photo"], x, 12, flip=True)
    g.place(r["led"], x, 17, flip=True)
    g.place(r["pullup"], x, 22, flip=True)
    g.place(r["curr"], x, 27, flip=True)
    k = i - 5
    g.place(f"D{14 + k}", x, 12)               # indicator LED (top)
    g.place(f"R{40 + k}", x, 17)               # 1k
    g.place(f"Q{19 + k}", x, 23)               # BSS138 driver (Q20..Q27)

# --- WALL indicators (top): 3-LED dashboards flanking the line row ---
for k in range(1, 7):
    lx = (20 + (k - 1) // 2 * 5) if k % 2 == 1 else (70 + (k - 2) // 2 * 5)
    g.place(f"D{22 + k}", lx, 32)              # D23..D28
    g.place(f"R{48 + k}", lx, 36)              # R49..R54 (1k)
    g.place(f"Q{27 + k}", lx, 41)              # Q28..Q33 (PMOS)

# --- Emitter group FETs + gate pull-downs (top, center, behind front band) ---
g.place("Q16", 40, 34); g.place("R62", 44, 34)     # front pair
g.place("Q17", 50, 34); g.place("R63", 54, 34)     # diagonal pair
g.place("Q18", 40, 40); g.place("R64", 44, 40)     # side pair
g.place("Q19", 50, 40); g.place("R61", 54, 40)     # line bank

# ---------------------------------------------------------------------------
# Mechanical: wheel slots, motor-body + bracket keep-outs (two precise rects
# per side), UKMARS bracket holes, castor, true-size motor models.
# ---------------------------------------------------------------------------
for _slot in WHEEL_SLOTS:
    g.add_edge_slot(_slot)
for _ko in MOTOR_KEEPOUTS:
    g.add_keepout(_ko, allow_tracks=True, allow_footprints=True)
for _hx, _hy, _hr in MOUNT_HOLES:
    g.add_mounting_hole((_hx, _hy), _hr * 2)

N20_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "n20.pretty")
for ref, fx, rot in (("MOT1", FACE_L, 180), ("MOT2", FACE_R, 0)):
    fp = pcbnew.FootprintLoad(N20_LIB, "N20_Motor_Encoder")
    fp.SetReference(ref)
    g.board.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(fx), pcbnew.FromMM(AXLE_Y)))
    fp.SetOrientationDegrees(rot)

# ---------------------------------------------------------------------------
# MID-BOARD (y 44..66): mux + power chain. The motor band starts at y~70.
# ---------------------------------------------------------------------------
g.place("U4", 8, 48, rot=0)                   # line read-mux, left edge
g.place("C13", 16, 42)

g.place("J2", 26, 50)                          # ext switch header
g.place("F1", 16, 58)
g.place("Q1", 34, 54)
g.place("R1", 34, 54, flip=True)               # gate pulldown (bottom, under Q1)
g.place("C1", 42, 54, value="100uF")
g.place("C2", 48, 54, value="100nF")
g.place("C4", 54, 54, value="10uF")
g.place("U1", 61, 54)                          # TPS63001
g.place("C3", 68, 48, value="100nF")
g.place("L1", 69, 56, value="1.5uH")
g.place("C5", 84, 58, value="22uF")
g.place("R2", 84, 48, flip=True); g.place("R3", 90, 48, flip=True)  # VBAT divider (bottom)
g.place("R67", 20, 111, flip=True); g.place("R68", 14, 111, flip=True)  # VBUS sense divider (bottom, clear of the module pad column)
g.place("C6", 84, 54, flip=True)

# ---------------------------------------------------------------------------
# REAR SERVICE + DRIVE PANEL. Module rear-center-left (clear of the bracket
# tabs x<=25.5 / x>=74.5 up to y 97.3), antenna out the rear edge.
# ---------------------------------------------------------------------------
g.place("U3", 35.25, 113.5, rot=180)           # body x 26.25..44.25 (pads clear the bracket keep-out)
# Module decoupling + EN RC on TOP in the mid-band (bottom-rear stays clear
# -- it is the rear cluster's only routing plane).
g.place("C8", 22, 60); g.place("C10", 28, 60)
g.place("R11", 34, 60); g.place("C9", 40, 60)

g.place("J7", 54, 114.3, rot=180)   # 1mm recessed: widens the pad-row strip the USB nets live in              # USB-C rear-center, mouth out
# USB support (bottom): spread AROUND the connector's pad field, not under it
# USB chain strung ALONG the module->connector path on the bottom:
# module USB pads (x~28) -> R60/R59 22R -> U6 ESD (x54, under the plug) -> J7
g.place("U6", 54, 106, flip=True)              # ESD (bottom)
g.place("R59", 42, 106, flip=True); g.place("R60", 36, 106, flip=True)  # 22R (bottom)
g.place("R12", 62, 110, flip=True); g.place("R56", 46, 110, flip=True)  # CC (bottom; R12=CC1 east / R56=CC2 west, uncrossed)

g.place("J8", 76, 55)                          # JTAG 1x6, mid-band right (pins clear the bracket keep-out)

# Buttons: A/B/C along the rear-right edge, RST tucked forward of them
BTN_LABELS = (("SW1", "A"), ("SW3", "B"), ("SW4", "C"), ("SW2", "RST"))
g.place("SW1", 71, 114)
g.place("R10", 76, 104, flip=True)              # A's pull-up (bottom -- was under SW2's THT pin: real short)
g.place("SW3", 81, 114)
g.place("SW4", 91, 114)
g.place("SW2", 64, 102)                         # RST
for _ref, _lbl in BTN_LABELS:
    _fp = g._placed[_ref]
    _pos = _fp.GetPosition()
    if len(_lbl) == 1:
        # letters go BELOW the button (rear-edge side): the old NW offset put
        # A under J6's connector housing
        g.add_silk_text(_lbl, (pcbnew.ToMM(_pos.x), pcbnew.ToMM(_pos.y) + 4.6),
                        size_mm=2.2)
    else:
        g.add_silk_text(_lbl, (pcbnew.ToMM(_pos.x) + 3.1, pcbnew.ToMM(_pos.y) - 5.2),
                        size_mm=1.4)

# TB6612 (SMD) in the inter-motor corridor + caps (bottom) + motor connectors
g.place("U2", 64, 66, rot=0)   # mid-band right: the inter-motor corridor
                                # starved its 24-pin fan-out (even same-net
                                # micro-bridges failed there); ~25mm from J6
g.place("C11", 60, 72, flip=True, value="10uF")    # under U2 (bottom)
g.place("C12", 68, 72, flip=True, value="100nF")
g.place("C14", 60, 60, flip=True, value="100nF")
g.place("J5", 8, 107, rot=0)                  # motor A connector (left, below bracket)
g.place("J6", 76, 107, rot=0)                  # motor B connector (right, below bracket)
# Encoder pull-ups/guards + strap pull-downs: TOP mid-band rows
g.place("R6", 22, 66); g.place("R7", 28, 66)     # ENC1 pullups
g.place("R8", 46, 60); g.place("R9", 52, 60)     # ENC2 pullups
g.place("R57", 58, 60); g.place("R58", 34, 66)   # ENC2 guards
g.place("R65", 46, 66); g.place("R66", 52, 66)   # strap pulldowns
g.place("J1", 8, 116)                          # 1S battery, rear-left corner

# --- Sanity + planes + save ---
remaining = g.unplaced_refs()
if remaining:
    print("WARNING -- unplaced refs:", remaining)
# Whitelisted pairs: the 45-degree diagonal clusters. Axis-aligned bboxes of
# rotated round parts over-flag; true geometry verified by hand -- courtyard
# circles r 3.55 (5mm LED) + r 2.55 (3mm det) at 7.07mm separation = 0.97mm
# real clearance, and D15's box sits 0.6mm from Q4's true circle.
overlaps = g.check_overlaps(ignore={frozenset(("D3", "Q4")), frozenset(("D4", "Q5")),
                                     frozenset(("D15", "Q4")), frozenset(("D22", "Q5")),
                                     # J7 vs U3: 0.1mm graze between the USB shell courtyard
                                     # and the module's antenna-zone border LINE at the board
                                     # edge -- the zone itself is off-board; x-separated bodies.
                                     frozenset(("J7", "U3"))})
if overlaps:
    print(f"COURTYARD OVERLAPS ({len(overlaps)}):")
    for a, b in overlaps:
        print(" ", a, "<->", b)
else:
    print("No courtyard overlaps detected.")

cx_out = sum(p[0] for p in BOARD_OUTLINE) / len(BOARD_OUTLINE)
cy_out = sum(p[1] for p in BOARD_OUTLINE) / len(BOARD_OUTLINE)
def shrink(points, amount):
    out = []
    for x, y in points:
        dx, dy = x - cx_out, y - cy_out
        d = (dx**2 + dy**2) ** 0.5
        out.append((x, y) if d == 0 else (x - dx/d*amount, y - dy/d*amount))
    return out

plane = shrink(BOARD_OUTLINE, 1.0)
g.add_zone("GND", pcbnew.In1_Cu, plane)
g.add_zone("PLUS3V3", pcbnew.In2_Cu, plane, solid=True)  # solid: thermal spokes starved at slot-pinched THT pins
# VM_BATT: partial pour on B.Cu over the power/drive region (battery, Q1,
# TPS input, TB6612 VM all live here). Fills AROUND existing bottom parts and
# tracks; stitched like the planes. Removes the raw-battery net from the
# router entirely -- its 0.35mm traces could not escape past the TPS63001's
# same-pitch neighbors, and a pour beats a trace for motor current anyway.
g.add_zone("VM_BATT", pcbnew.B_Cu, [(16, 44), (99, 44), (99, 113), (16, 113)])

g.assert_netlist_pads_mapped()   # hard gate: no netlist pin may load netless
g.save(r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb")
# Repoint U1/L1 3D models to project-local models: the KiCad install ships NO
# .step (or even .wrl) for DRC0010J / SRP7028A, so STEP fit-check exports
# silently omitted the regulator and the tallest part. gen_step_models.py
# authors box-true substitutes; --subst-models picks the sibling .step.
# Text-level because pcbnew's fp.Models() returns a SWIG copy.
_pcbp = r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb"
_txt = open(_pcbp, encoding="utf-8", newline="").read()
_txt = _txt.replace("${KICAD10_3DMODEL_DIR}/Package_SON.3dshapes/Texas_DRC0010J.step",
                    "${KIPRJMOD}/3d/Texas_DRC0010J.wrl")
_txt = _txt.replace("${KICAD10_3DMODEL_DIR}/Inductor_SMD.3dshapes/L_Bourns_SRP7028A_7.3x6.6mm.step",
                    "${KIPRJMOD}/3d/L_Bourns_SRP7028A_7.3x6.6mm.wrl")
open(_pcbp, "w", encoding="utf-8", newline="").write(_txt)
print(f"Saved {BOARD_W}x{BOARD_H}mm PCB with {len(g._placed)} footprints, {len(remaining)} unplaced.")
