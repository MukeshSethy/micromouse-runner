import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import PcbGen
import pcbnew

# ESP32-ONLY micromouse carrier board, rev 3 (2026-07-15).
# Rev-3 changes on top of the ESP32-only rev 2:
#  - 8 top-side INDICATOR LEDs (D15-D22 + R41-R48 + Q30-Q37), one per line
#    sensor, brightness analogically tracking the IR receiver (BSS138 gate on
#    the sense node = zero DC load). Placed directly above their sensor column.
#  - Wall sensors repositioned per professional micromouse practice (Harrison/
#    UKMARSBOT-style): everything senses FORWARD of the wheels -- a front-facing
#    pair at the front edge, a 45-degree diagonal pair on the chamfered front
#    corners, and a 90-degree side pair close behind them. No sensors trail
#    down the body.
#  - Board tightened 100x128 -> 100x114: A1 rotated HORIZONTAL (rot=270, its
#    43.6mm length now spans the board width instead of its length), muxes
#    moved to the side edges the wall sensors vacated, drive axle pulled up to
#    y=92. Width stays 100 -- it is pinned by the 76.2mm line array plus the
#    two side sensor clusters.
#
# 4 copper layers, all signal (unfilled internal planes falsely short THT pads
# in headless DRC; GND poured on outer faces, convert In1/In2 to planes in the
# GUI if desired). Only the line-sensor optics are on the bottom.

NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"
g = PcbGen(NETLIST)
g.board.SetCopperLayerCount(4)

BOARD_W = 100
BOARD_H = 114
CX = BOARD_W / 2   # 50

AXLE_Y = 92         # drive axle; ALL electronics sit fore of the wheel band
WHEEL_THK = 9
WHEEL_DIA = 32
WHEEL_INSET = 3     # wheels stay INSIDE the envelope
CHAMF = 16

BOARD_OUTLINE = [
    (CHAMF, 0), (BOARD_W - CHAMF, 0), (BOARD_W, CHAMF),
    (BOARD_W, BOARD_H), (0, BOARD_H), (0, CHAMF),
]
g.add_outline(BOARD_OUTLINE)

def sensor_refs(i):
    return {
        "photo": f"Q{2 + 2*i}", "pullup": f"R{13 + 2*i}", "curr": f"R{14 + 2*i}",
        "led": f"D{1 + i}", "switch": f"Q{3 + 2*i}",
    }

# ---------------------------------------------------------------------------
# WALL sensors -- professional forward-sensing arrangement.
# THT optics (photo + LED, leads bent to aim) sit at the cluster anchor; the
# LED is rotated 90 so its pads stack vertically (keeps the cluster's x-reach
# ~1mm past the LED position -- horizontal pads once pierced the bottom line
# array, caught as a real DRC short). SMD support parts (pull-up, current
# limit, low-side switch) trail BEHIND (toward +y). THT parts must never sit
# over x=15..85 within y=8..32 (bottom line-array pads).
# ---------------------------------------------------------------------------
# Front-facing pair (y=3, clear of the bottom array whose pads start ~8.4):
# photo + LED side by side aimed straight ahead, support behind. LED rot=270
# puts its second pad at ay+2.54 (rot=90 would land it off the front edge).
def front_cluster(i, ax, sign):
    r = sensor_refs(i)
    g.place(r["photo"], ax, 3)
    g.place(r["led"], ax + sign*8, 3, rot=270)
    g.place(r["pullup"], ax, 9)
    g.place(r["curr"], ax + sign*10, 9)   # x+10: clears the indicator LED courtyard
    g.place(r["switch"], ax + sign*1, 14) # x+1: clears both indicator R columns
front_cluster(0, 30, +1)                      # WALL1 front-left (straight ahead)
front_cluster(1, BOARD_W - 30, -1)            # WALL2 front-right (straight ahead)

# Diagonal (45) and side (90) pairs: EDGE-COLUMN clusters. The 5mm THT LED's
# ~7.1mm courtyard cannot sit beside the photo without hitting the line
# array's first column (x=16.7), so the LED stacks BEHIND the photo along the
# board edge -- optically fine, both parts' leads are bent outward to aim
# anyway. Support parts sit one column inboard (x=ax+7*sign, still < 15).
def edge_cluster(i, ax, ay, sign):
    r = sensor_refs(i)
    g.place(r["photo"], ax, ay)
    g.place(r["led"], ax, ay + 7, rot=270)
    g.place(r["pullup"], ax + sign*7, ay)
    g.place(r["curr"], ax + sign*7, ay + 6)
    g.place(r["switch"], ax + sign*7, ay + 12)
# 45-degree diagonal pair AT the chamfered corners (the chamfer exists for
# exactly this) -- the workhorse sensors for wall-edge detection while turning.
# Anchor (5,18): as close as the chamfer allows (a THT pad needs ~1.9mm of
# diagonal margin, i.e. x+y >= ~19 for the photo's upper pad).
edge_cluster(2, 5, 18, +1)                    # WALL3 left diagonal (bend 45 out)
edge_cluster(3, BOARD_W - 5, 18, -1)          # WALL4 right diagonal (bend 45 out)
# 90-degree side pair immediately behind, still well fore of the axle.
edge_cluster(4, 5, 36, +1)                    # WALL5 left side (bend 90 out)
edge_cluster(5, BOARD_W - 5, 36, -1)          # WALL6 right side (bend 90 out)

# ---------------------------------------------------------------------------
# LINE sensors: SMD, BOTTOM face, 8 columns at the 9.525mm QTR pitch,
# 5mm intra-column pitch (4mm left no routing channel at 0.3mm clearance).
# INDICATOR chain (rev 3): visible LED + 1k + BSS138 on the TOP face directly
# above the same column -- LED at the very front so it's visible in operation.
# ---------------------------------------------------------------------------
LINE_X0 = CX - 3.5 * 9.525
for i in range(6, 14):
    x = LINE_X0 + (i - 6) * 9.525
    r = sensor_refs(i)
    g.place(r["photo"], x, 10, flip=True)
    g.place(r["led"], x, 15, flip=True)
    g.place(r["pullup"], x, 20, flip=True)
    g.place(r["curr"], x, 25, flip=True)
    g.place(r["switch"], x, 30, flip=True)
    k = i - 5                                  # 1..8
    g.place(f"D{14 + k}", x, 10)               # indicator LED (top, above column)
    g.place(f"R{40 + k}", x, 15)               # 1k limiter
    g.place(f"Q{29 + k}", x, 21)               # BSS138 driver

# ---------------------------------------------------------------------------
# Mechanical: interior wheel slots + motor+bracket keep-outs + castor.
# ---------------------------------------------------------------------------
MOUNT_LEN = 22
MOUNT_W = 30
g.add_edge_slot((WHEEL_INSET, AXLE_Y - WHEEL_DIA/2, WHEEL_INSET + WHEEL_THK, AXLE_Y + WHEEL_DIA/2))
g.add_edge_slot((BOARD_W - WHEEL_INSET - WHEEL_THK, AXLE_Y - WHEEL_DIA/2, BOARD_W - WHEEL_INSET, AXLE_Y + WHEEL_DIA/2))
g.add_keepout((0, AXLE_Y - MOUNT_W/2, WHEEL_INSET + WHEEL_THK + MOUNT_LEN, AXLE_Y + MOUNT_W/2), allow_tracks=True)
g.add_keepout((BOARD_W - WHEEL_INSET - WHEEL_THK - MOUNT_LEN, AXLE_Y - MOUNT_W/2, BOARD_W, AXLE_Y + MOUNT_W/2), allow_tracks=True)
for my in (AXLE_Y - 12, AXLE_Y + 12):
    g.add_mounting_hole((WHEEL_INSET + WHEEL_THK + MOUNT_LEN - 3, my), 2.5)
    g.add_mounting_hole((BOARD_W - WHEEL_INSET - WHEEL_THK - MOUNT_LEN + 3, my), 2.5)
g.add_mounting_hole((CX, 4), 3.0)             # front castor/skid (out of the array)

# ---------------------------------------------------------------------------
# Controller: A1 HORIZONTAL (rot=270). Calibrated geometry: anchor = pad 1
# (VIN, analog row); at rot=270 the analog row runs -x from the anchor at
# y=anchor_y, the digital row sits BELOW it (+15.24, toward the rear -- its
# D2..D13 nets all go to the TB6612/motor side), and the body spans roughly
# x = anchor-42.2 .. anchor+5.9. Anchor (69, 38): body ~x 26.8..74.9,
# y ~36.5..55, centered on the board.
# ---------------------------------------------------------------------------
A1_Y = 38
g.place("A1", 69, A1_Y, rot=270)

# Muxes: vertical on the side edges the wall sensors vacated (long axis along
# the edge). U4 (read) left, U5 (write) right, decoupling just below.
g.place("U4", 8, 59, rot=0)
g.place("U5", BOARD_W - 8, 59, rot=0)
g.place("C13", 17, 52)
g.place("C14", BOARD_W - 17, 52)

# Motor driver breakout (socketed 2x 1x8): HORIZONTAL rows (rot=90, pads run
# +x) tucked between A1's body (ends y~56) and the wheel keep-outs (y=77) --
# a vertical column would not fit that 21mm band.
g.place("J10", 17, 60, rot=90)
g.place("J11", 17, 66, rot=90)

# Start button + pull-up + A1 3V3 decoupling: center gap under A1.
g.place("C8", 39, 57)                         # near A1's 3V3 pin (x=36 on the analog row)
g.place("SW1", 45, 61)
g.place("R10", 56, 61)

# Motor connectors just above each wheel keep-out; encoder pull-ups inboard.
g.place("J5", 9, 72, rot=0)
g.place("J6", BOARD_W - 9, 72, rot=0)
g.place("R6", 57, 58); g.place("R7", 63, 58)
g.place("R8", 69, 58); g.place("R9", 75, 58)

# Power chain: center column between the wheel keep-outs (x 34..66), two rows.
g.place("J2", 37, 78)                         # ext switch
g.place("F1", 43, 78)
g.place("Q1", 49, 78)
g.place("C1", 56, 78, value="100uF")
g.place("C2", 62, 78, value="100nF")
g.place("C4", 36, 84, value="10uF")
g.place("U1", 42, 84)
g.place("C3", 47, 84, value="100nF")
g.place("L1", 54, 84, value="3.3uH")
g.place("C5", 61, 84, value="22uF")
g.place("R1", 36, 90)                         # Q1 gate pulldown

# Battery + balance + sense dividers: rear center gap between the wheels.
g.place("J1", 43, 96)                         # 2S battery input
g.place("J3", 57, 96)                         # balance connector
g.place("R2", 38, 104); g.place("C6", 45, 104); g.place("R3", 52, 104)
g.place("R4", 38, 110); g.place("C7", 45, 110); g.place("R5", 52, 110)

# --- Sanity + GND pours + save ---
remaining = g.unplaced_refs()
if remaining:
    print("WARNING -- unplaced refs:", remaining)
overlaps = g.check_overlaps()
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

plane = shrink(BOARD_OUTLINE, 2.0)
g.add_zone("GND", pcbnew.F_Cu, plane)
g.add_zone("GND", pcbnew.B_Cu, plane)

g.save(r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb")
print(f"Saved {BOARD_W}x{BOARD_H}mm PCB with {len(g._placed)} footprints, {len(remaining)} unplaced.")
