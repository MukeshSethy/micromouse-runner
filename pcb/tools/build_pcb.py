import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import PcbGen
import pcbnew

# ESP32-ONLY micromouse carrier board (user decision 2026-07-13: drop the STM32,
# use a single socketed Arduino Nano ESP32 as the sole controller to save space).
# The whole STM32 dev-board footprint + its UART flash relay are gone, so this
# board is packed MUCH tighter than the two-module version: ~95 x 122mm vs the
# old 150 x 185. User also asked (2026-07-13) to keep components very close for a
# tight arrangement to satisfy the dimension target -- so bands are compressed and
# margins are small.
#
# Single controller = A1, placed with the REAL Module:Arduino_Nano footprint
# (true ~18x45mm board outline), NOT generic headers -- so its courtyard reflects
# the actual board and tight placement respects it.
#
# Layer plan unchanged from before: designed for 4 layers (GND + 3V3 internal
# planes) but kept at 2 copper layers with GND poured on both outer faces here,
# because pcbnew's zone filler segfaults headless and an unfilled internal plane
# falsely shorts to THT pads in DRC. Convert to 4-layer + fill in the GUI.
#
# SINGLE-SIDED-TOP: only the 8 SMD line sensors live on the bottom (facing the
# floor). Everything else (sockets, connectors, muxes, power) is THT/top -- their
# through-hole pins occupy every layer so nothing can tuck under them.

NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"
g = PcbGen(NETLIST)
# 4 copper layers, ALL as signal layers (user-approved 3-4 layer board). No
# internal planes here -- unfilled internal zones falsely short THT pads in
# headless DRC; GND is poured on the outer faces as before. Freerouting uses
# all 4 layers; convert In1/In2 to planes later in the GUI if desired.
g.board.SetCopperLayerCount(4)

BOARD_W = 100
BOARD_H = 128
CX = BOARD_W / 2   # 50

AXLE_Y = 108        # drive axle at the rear; ALL electronics sit fore of it
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

# WALL sensors (THT, top, bent-lead). Compact cluster: photo + led(+5) + switch(+10)
# across, pull-up / current-limit stacked above. Tighter than the old 7mm spread.
def place_wall_sensor(i, ax, ay, sign):
    # Compact cluster hugging a side edge: photo + LED across (7mm), pull-up +
    # current-limit stacked below, low-side switch tucked above. Reaches only
    # ~7mm inward, so the whole 76mm-wide bottom line array + the center control
    # band stay clear. ALL 6 wall sensors are side-mounted (the front two are the
    # forward-most, aimed diagonally forward) -- nothing sits over the bottom
    # line-sensor optics, which was shorting THT pins into the SMD pads before.
    r = sensor_refs(i)
    g.place(r["photo"], ax, ay)
    # LED rotated 90 so its THT pads stack VERTICALLY (x stays at ax+7*sign,
    # max extent ~0.8mm) -- horizontal pads reached x=14.5 and pierced the
    # bottom line-sensor columns (real DRC short caught at D1/R26).
    g.place(r["led"], ax + sign*7, ay, rot=90)
    g.place(r["pullup"], ax, ay + 7)
    g.place(r["curr"], ax + sign*7, ay + 7)
    g.place(r["switch"], ax + sign*3, ay - 8)

# y=24 minimum for the front pair: the cluster's switch sits 8mm above its
# anchor, and the front chamfers (0,16)-(16,0) / (84,0)-(100,16) cut into
# anything above y=16 at these x positions (previous anchor y=16 put the
# switches exactly ON the board edge -- unroutable + edge-clearance errors).
place_wall_sensor(0, 5, 24, +1)               # WALL1 front-left, aimed fwd-diagonal
place_wall_sensor(1, BOARD_W - 5, 24, -1)     # WALL2 front-right, aimed fwd-diagonal
place_wall_sensor(2, 5, 46, +1)               # WALL3 mid-left, aimed forward
place_wall_sensor(3, BOARD_W - 5, 46, -1)     # WALL4 mid-right, aimed forward
place_wall_sensor(4, 5, 68, +1)               # WALL5 side-facing left (90 deg)
place_wall_sensor(5, BOARD_W - 5, 68, -1)     # WALL6 side-facing right (90 deg)

# LINE sensors: SMD, BOTTOM, front, 9.525mm QTR pitch, stacked columns.
LINE_X0 = CX - 3.5 * 9.525
for i in range(6, 14):
    x = LINE_X0 + (i - 6) * 9.525
    r = sensor_refs(i)
    # 5mm vertical pitch inside each column -- at 4mm the 0.3mm-clearance router
    # had no channel between the 1206 pads and left most of the array unrouted.
    g.place(r["photo"], x, 10, flip=True)
    g.place(r["led"], x, 15, flip=True)
    g.place(r["pullup"], x, 20, flip=True)
    g.place(r["curr"], x, 25, flip=True)
    g.place(r["switch"], x, 30, flip=True)

# Mechanical: interior wheel slots + motor+bracket keep-outs + castor. Motors face
# inward from the side slots; MOUNT_LEN kept modest (tight board) so the two
# motors' inner ends don't collide across the ~95mm width -- a center gap remains
# for the battery connectors. Tracks allowed under the bracket (it stands off).
MOUNT_LEN = 22
MOUNT_W = 30
g.add_edge_slot((WHEEL_INSET, AXLE_Y - WHEEL_DIA/2, WHEEL_INSET + WHEEL_THK, AXLE_Y + WHEEL_DIA/2))
g.add_edge_slot((BOARD_W - WHEEL_INSET - WHEEL_THK, AXLE_Y - WHEEL_DIA/2, BOARD_W - WHEEL_INSET, AXLE_Y + WHEEL_DIA/2))
g.add_keepout((0, AXLE_Y - MOUNT_W/2, WHEEL_INSET + WHEEL_THK + MOUNT_LEN, AXLE_Y + MOUNT_W/2), allow_tracks=True)
g.add_keepout((BOARD_W - WHEEL_INSET - WHEEL_THK - MOUNT_LEN, AXLE_Y - MOUNT_W/2, BOARD_W, AXLE_Y + MOUNT_W/2), allow_tracks=True)
for my in (AXLE_Y - 12, AXLE_Y + 12):
    g.add_mounting_hole((WHEEL_INSET + WHEEL_THK + MOUNT_LEN - 3, my), 2.5)
    g.add_mounting_hole((BOARD_W - WHEEL_INSET - WHEEL_THK - MOUNT_LEN + 3, my), 2.5)
# Castor hole at the very front edge margin -- previous (CX,8) sat in the
# MIDDLE of the line array's center columns and made LINE3/LINE4 unroutable.
g.add_mounting_hole((CX, 4), 3.0)            # front castor/skid

# --- Controller: single Arduino Nano ESP32 (A1), centered in the control band ---
# Arduino_Nano footprint: pad1 at origin, pads span +15.24mm (x) x +35.56mm (y),
# body/courtyard ~18 x 42mm. Centered on CX, occupying the control band y=32..74.
g.place("A1", CX - 7.62, 34)

# Lateral gaps beside A1 (x 16..38 left, 57..79 right) hold the muxes, TB6612
# breakout, button, and A1 decoupling -- everything the old center band had, now
# packed either side of the controller so nothing stacks front-to-back.
# Lateral gaps beside A1 (left x11..38, right x57..84) hold the muxes, TB6612
# breakout, button and A1 decoupling -- packed either side of the controller.
# Lateral gaps beside A1 (left x12..40, right x60..88) hold the muxes, TB6612
# breakout, button and A1 decoupling -- packed either side of the controller.
# --- IR mux/demux (top) ---
g.place("U4", 24, 40, rot=0)                 # read-mux, left gap
g.place("U5", 76, 40, rot=0)                 # write-demux, right gap
g.place("C13", 32, 40)
g.place("C14", 68, 40)
# --- Motor driver breakout (socketed 2x 1x8), right gap below the mux ---
g.place("J10", 66, 56)
g.place("J11", 73, 56)
# --- Start button + pull-up + A1 decoupling, left gap below the mux ---
g.place("SW1", 24, 60)
g.place("R10", 24, 68)
g.place("C8", 34, 68)                        # A1 3V3 decoupling

# --- Motor connectors + encoder pull-ups, at the sides fore of each motor ---
g.place("J5", 12, 80, rot=0)                 # motor A encoder connector (left)
g.place("J6", BOARD_W - 12, 80, rot=0)       # motor B encoder connector (right)
g.place("R6", 6, 88); g.place("R7", 18, 88)
g.place("R8", BOARD_W - 18, 88); g.place("R9", BOARD_W - 6, 88)

# --- Power section (top, 2-row center band y=78..90, fore of the rear axle) ---
g.place("J2", 32, 82)                        # ext switch
g.place("F1", 38, 82)
g.place("Q1", 44, 82)
g.place("C1", 51, 82, value="100uF")
g.place("C2", 57, 82, value="100nF")
g.place("C4", 63, 82, value="10uF")
g.place("U1", 69, 82)
g.place("R1", 38, 90)
g.place("C3", 46, 90, value="100nF")
g.place("L1", 56, 90, value="3.3uH")
g.place("C5", 66, 90, value="22uF")

# --- Rear center gap (between the two side motors): battery + sense dividers ---
g.place("J1", 44, 100)                       # 2S battery input
g.place("J3", 58, 100)                       # balance connector
g.place("R2", 38, 108); g.place("C6", 45, 108); g.place("R3", 38, 114)
g.place("R4", 45, 114); g.place("C7", 52, 114); g.place("R5", 59, 114)

# --- Sanity + GND pour + save ---
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
