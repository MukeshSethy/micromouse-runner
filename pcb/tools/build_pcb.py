import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import PcbGen
import pcbnew

# Rev 4 (2026-07-15): ESP32-S3-WROOM-1 SMD module (sole controller, real
# footprint + 3D), 1S LiPo + TPS63001 buck-boost, mux only for the line array
# (wall sensors direct to ADC1), ganged emitters (4 group FETs, U5 deleted),
# wall + line indicator LEDs on top, 3 user buttons + reset, rear USB-C with
# ESD, JTAG header, N20 motors as true-size mechanical footprints + 3D.
#
# Antenna rule (Espressif HW design guidelines, verified): interior module
# placement is DISALLOWED; the PCB antenna must overhang the board edge.
# Module sits on the RIGHT edge (rot=270 -> antenna points +x), anchor
# x=93.25 puts the antenna section AND its embedded keepout zone entirely
# off-board past x=100. Mid-edge overhang (corner is the gold standard but
# both rear corners are wheels and both front corners are chamfered sensor
# mounts); WiFi is telemetry-only -- deviation documented.
#
# Motors: verified 32.7mm body+encoder per side -- they physically cannot
# flank rear-center electronics on a 100mm board, which is what pushed the
# module to the side edge. Motor keep-outs now cover the TRUE body length.

NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"
g = PcbGen(NETLIST)
g.board.SetCopperLayerCount(4)

BOARD_W = 100
BOARD_H = 114
CX = BOARD_W / 2

AXLE_Y = 92
WHEEL_THK = 9
WHEEL_DIA = 32
WHEEL_INSET = 3
CHAMF = 16

BOARD_OUTLINE = [
    (CHAMF, 0), (BOARD_W - CHAMF, 0), (BOARD_W, CHAMF),
    (BOARD_W, BOARD_H), (0, BOARD_H), (0, CHAMF),
]
g.add_outline(BOARD_OUTLINE)

def sensor_refs(i):
    # Rev 4: no per-sensor switch FET (emitters are ganged on group FETs).
    return {
        "photo": f"Q{2 + i}", "pullup": f"R{13 + 2*i}", "curr": f"R{14 + 2*i}",
        "led": f"D{1 + i}",
    }

# --- WALL sensors: Decimus-style forward arrangement (unchanged from rev 3,
# research-verified), minus the per-sensor switch. ---
def front_cluster(i, ax, sign):
    r = sensor_refs(i)
    g.place(r["photo"], ax, 3)
    g.place(r["led"], ax + sign*8, 3, rot=270)
    g.place(r["pullup"], ax, 9)
    g.place(r["curr"], ax + sign*10, 9)
front_cluster(0, 30, +1)                      # WALL1 front-left (straight, toe-out)
front_cluster(1, BOARD_W - 30, -1)            # WALL2 front-right

def diag_cluster(i, ax, sign):
    # 45-degree pair at the chamfer: photo + LED stacked along the edge.
    r = sensor_refs(i)
    g.place(r["photo"], ax, 17)
    g.place(r["led"], ax, 24, rot=270)
    g.place(r["pullup"], ax + sign*7, 17)
    g.place(r["curr"], ax + sign*7, 23)
def side_cluster(i, ax, sign):
    # 90-degree pair: photo on the edge, LED beside it inboard (the vertical
    # stack would poke into the WROOM courtyard which starts at y=42).
    r = sensor_refs(i)
    g.place(r["photo"], ax, 32)
    g.place(r["led"], ax + sign*8, 36, rot=270)
    g.place(r["pullup"], ax + sign*7, 30)
    g.place(r["curr"], ax, 39)
diag_cluster(2, 5, +1)                        # WALL3 left 45-diagonal (chamfer)
diag_cluster(3, BOARD_W - 5, -1)              # WALL4 right 45-diagonal
side_cluster(4, 5, +1)                        # WALL5 left side (90, toe fwd)
side_cluster(5, BOARD_W - 5, -1)              # WALL6 right side

# --- LINE sensors (bottom) + line indicators (top, same columns) ---
LINE_X0 = CX - 3.5 * 9.525
for i in range(6, 14):
    x = LINE_X0 + (i - 6) * 9.525
    r = sensor_refs(i)
    g.place(r["photo"], x, 10, flip=True)
    g.place(r["led"], x, 15, flip=True)
    g.place(r["pullup"], x, 20, flip=True)
    g.place(r["curr"], x, 25, flip=True)
    k = i - 5
    g.place(f"D{14 + k}", x, 10)               # indicator LED (top)
    g.place(f"R{40 + k}", x, 15)               # 1k
    g.place(f"Q{19 + k}", x, 21)               # BSS138 driver (Q20..Q27)

# --- WALL indicators (top): two 3-LED dashboards flanking the line row.
# Left = WALL1/3/5, right = WALL2/4/6; PMOS drivers (LED ON = wall seen). ---
for k in range(1, 7):
    lx = (20 + (k - 1) // 2 * 5) if k % 2 == 1 else (70 + (k - 2) // 2 * 5)
    g.place(f"D{22 + k}", lx, 28)              # D23..D28
    g.place(f"R{48 + k}", lx, 32)              # R49..R54 (1k)
    g.place(f"Q{27 + k}", lx, 37)              # Q28..Q33 (PMOS)

# --- Emitter group FETs + their 100k gate pull-downs ---
g.place("Q16", 50, 14); g.place("R62", 50, 19)     # front pair (castor column gap)
g.place("Q17", 42, 30); g.place("R63", 46, 30)     # diagonal pair
g.place("Q18", 52, 30); g.place("R64", 56, 30)     # side pair
g.place("Q19", 62, 30); g.place("R61", 66, 30)     # line bank

# --- Mechanical: wheel slots, TRUE-SIZE motor keep-outs, castor, holes ---
MOUNT_LEN = 33          # verified: gearbox+can+encoder = 32.7mm from the slot
MOUNT_W = 20            # motor body is 12 + bracket margin; 20 frees the y>102
                        # band the rear USB-C's back pads need
g.add_edge_slot((WHEEL_INSET, AXLE_Y - WHEEL_DIA/2, WHEEL_INSET + WHEEL_THK, AXLE_Y + WHEEL_DIA/2))
g.add_edge_slot((BOARD_W - WHEEL_INSET - WHEEL_THK, AXLE_Y - WHEEL_DIA/2, BOARD_W - WHEEL_INSET, AXLE_Y + WHEEL_DIA/2))
# allow_footprints: the only footprints inside are MOT1/MOT2 -- the motors the
# keep-out REPRESENTS (placement discipline is enforced by generation).
g.add_keepout((0, AXLE_Y - MOUNT_W/2, WHEEL_INSET + WHEEL_THK + MOUNT_LEN, AXLE_Y + MOUNT_W/2), allow_tracks=True, allow_footprints=True)
g.add_keepout((BOARD_W - WHEEL_INSET - WHEEL_THK - MOUNT_LEN, AXLE_Y - MOUNT_W/2, BOARD_W, AXLE_Y + MOUNT_W/2), allow_tracks=True, allow_footprints=True)
for my in (AXLE_Y - 12, AXLE_Y + 12):
    g.add_mounting_hole((WHEEL_INSET + WHEEL_THK + MOUNT_LEN - 3, my), 2.5)
    g.add_mounting_hole((BOARD_W - WHEEL_INSET - WHEEL_THK - MOUNT_LEN + 3, my), 2.5)
g.add_mounting_hole((CX, 4), 3.0)

# N20 motors: true-size mechanical footprints (project n20.pretty) with the
# hand-authored 3D model. Not in the netlist -- added directly to the board.
N20_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "n20.pretty")
for ref, fx, rot in (("MOT1", WHEEL_INSET + WHEEL_THK, 180), ("MOT2", BOARD_W - WHEEL_INSET - WHEEL_THK, 0)):
    fp = pcbnew.FootprintLoad(N20_LIB, "N20_Motor_Encoder")
    fp.SetReference(ref)
    g.board.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(fx), pcbnew.FromMM(AXLE_Y)))
    fp.SetOrientationDegrees(rot)

# --- Controller: WROOM-1 on the RIGHT edge, antenna overhanging (+x). ---
# rot=270 maps local -y (antenna) to +x. Anchor x=93.25: antenna section
# (local y -6.75..-13.05) and its keepout zone land entirely past x=100.
g.place("U3", 93.25, 66, rot=270)
g.place("C8", 66, 52); g.place("C10", 66, 56)     # module decoupling

# EN reset RC
g.place("R11", 66, 62); g.place("C9", 71, 64)

# User buttons row (front-center band): SW1 start/BOOT, SW3/SW4 menu, SW2 reset
g.place("SW1", 20, 44)
g.place("R10", 31, 44)                             # SW1 10k pull-up
g.place("SW3", 38, 44)                             # BTN2 (IO35)
g.place("SW4", 48, 44)                             # BTN3 (IO36)
g.place("SW2", 58, 44)                             # RESET (ESP_EN)

# JTAG header (vertical) beside the module
g.place("J8", 77, 52)

# --- Mux (line array only) on the LEFT edge + decoupling ---
g.place("U4", 8, 59, rot=0)
g.place("C13", 17, 52)

# --- TB6612 breakout headers (horizontal rows, center-left) ---
g.place("J10", 22, 56, rot=90)
g.place("J11", 22, 62, rot=90)
g.place("R65", 45, 58); g.place("R66", 45, 64)     # strap pull-downs (BIN2/STBY)

# --- Motor connectors + encoder pull-ups + ENC2 series guards ---
g.place("J5", 13, 73, rot=0)
g.place("J6", 60, 72, rot=0)                       # shifted left: x 66-80 stays an
                                                    # open escape corridor for the
                                                    # module's USB/ENC/JTAG nets
g.place("R6", 3, 69); g.place("R7", 9, 69)
g.place("R1", 44, 54)                              # Q1 gate pull-down
g.place("R8", 50, 62); g.place("R9", 56, 62)
g.place("R57", 56, 66); g.place("R58", 62, 66)     # 1k guards (IO44/IO43)

# --- Power chain (1S -> TPS63001): rows at y=68/74 (clear of the y>=82 motor
# keep-outs), with the tall inductor + output cap dropped into the inter-motor
# corridor where VM/3V3 flow rearward anyway ---
g.place("J2", 17, 66)                              # ext switch (left pocket by the mux)
g.place("F1", 26, 66)
g.place("Q1", 37, 68)
g.place("C1", 44, 68, value="100uF")
g.place("C2", 50, 68, value="100nF")
g.place("C4", 31, 74, value="10uF")
g.place("U1", 37, 74)                              # TPS63001 (SON-10)
g.place("C3", 31, 68, value="100nF")
g.place("L1", 49, 76, value="1.5uH")               # beside U1, clear of the
                                                    # mounting-hole router squares
g.place("C5", 49, 84, value="22uF")                 # corridor, between the squares

# --- Rear strip (y>107, between the wheel slots): USB-C + ESD + battery ---
g.place("J7", 40, 109.3, rot=180)                  # USB-C, mouth ~flush with the rear edge
g.place("U6", 52, 108)                             # USBLC6 ESD array
g.place("R59", 58, 108); g.place("R60", 63, 108)   # 22R series
g.place("R12", 30, 108); g.place("R56", 25, 108)   # CC 5.1k pulldowns
g.place("J1", 74, 110)                             # 1S battery JST-PH
g.place("R2", 82, 108); g.place("R3", 86, 108)     # VBAT divider
g.place("C6", 84, 112)

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
