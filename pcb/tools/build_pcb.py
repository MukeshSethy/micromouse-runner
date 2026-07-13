import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import PcbGen
import pcbnew

# 4-LAYER socketed micromouse carrier board (user decisions 2026-07-12).
# Stackup: F.Cu (signals + ALL components) / In1.Cu = GND plane /
# In2.Cu = +3V3 plane / B.Cu (signals + the 8 SMD line sensors only).
#
# SINGLE-SIDED-TOP placement (only the SMD line sensors on the bottom). Reason
# learned the hard way: the socketed modules, motor connectors, buttons and JST
# connectors are all THROUGH-HOLE -- their pins occupy every layer -- so you
# CANNOT tuck other parts on the bottom underneath them (the pins short into
# them; 27 DRC shorts when attempted). Two-sided packing only frees area under
# SMD top parts, and here the big parts are all THT. So everything lives on top
# except the line-sensor optics (SMD, bottom, facing the floor).
#
# That single-sided reality is exactly why keeping the sockets forces a larger
# board: three Nano-class plug-in modules + 14 sensors + motors + power laid
# out on ONE face need the room. Sized ~150 x 185mm. The 4 layers (the user's
# call) don't change this footprint -- they buy clean GND/PWR planes so the two
# outer layers are almost all signal, which this dense board needs. Wheels sit
# INSIDE the envelope (interior slots). See PROJECT_NOTES for the full size /
# socket / layer tension.

NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"
g = PcbGen(NETLIST)
# NOTE on layer count: the user asked for 4 layers, and the board is DESIGNED
# for a 4-layer stackup (GND + 3V3 internal planes). BUT in this headless
# environment I keep it at 2 copper layers with GND poured on the outer layers,
# because: (a) pcbnew's zone filler segfaults headless, and (b) an UNFILLED
# internal plane falsely shorts to every through-hole pad that passes through
# it in DRC (a filled plane clears around each pad -- but I can't fill/verify
# that here). The 2-layer outer-GND version is fully DRC-verifiable. Converting
# to the intended 4-layer (add In1=GND plane, In2=+3V3 plane, move the outer
# GND pour to In1, fill all zones) is a few clicks in the KiCad GUI where zones
# fill correctly -- routing is unaffected. Documented in PROJECT_NOTES.
# g.board.SetCopperLayerCount(4)   # do in GUI + fill planes

BOARD_W = 150
BOARD_H = 185
CX = BOARD_W / 2   # 75

AXLE_Y = 128        # drive axle toward the rear (2WD + front castor)
WHEEL_THK = 9
WHEEL_DIA = 32
WHEEL_INSET = 4     # wheels stay INSIDE the envelope
CHAMF = 25

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

# WALL sensors (THT, top, bent-lead), 7mm intra-cluster spacing.
def place_wall_sensor(i, ax, ay, sign):
    r = sensor_refs(i)
    g.place(r["photo"], ax, ay)
    g.place(r["led"], ax + sign*7, ay)
    g.place(r["pullup"], ax, ay + 7)
    g.place(r["curr"], ax + sign*7, ay + 7)
    g.place(r["switch"], ax + sign*14, ay)

place_wall_sensor(0, 22, 10, +1)             # WALL1 front-left diagonal
place_wall_sensor(1, BOARD_W - 22, 10, -1)   # WALL2 front-right diagonal
place_wall_sensor(2, 10, 42, +1)             # WALL3 front-side left
place_wall_sensor(3, BOARD_W - 10, 42, -1)   # WALL4 front-side right
place_wall_sensor(4, 10, 66, +1)             # WALL5 side-facing left
place_wall_sensor(5, BOARD_W - 10, 66, -1)   # WALL6 side-facing right

# LINE sensors: SMD, BOTTOM, front row, 9.525mm QTR pitch.
LINE_X0 = CX - 3.5 * 9.525
for i in range(6, 14):
    x = LINE_X0 + (i - 6) * 9.525
    r = sensor_refs(i)
    g.place(r["photo"], x, 12, flip=True)
    g.place(r["led"], x, 17, flip=True)
    g.place(r["pullup"], x, 22, flip=True)
    g.place(r["curr"], x, 27, flip=True)
    g.place(r["switch"], x, 32, flip=True)

# Mechanical: interior wheel slots + GENEROUS motor+bracket keep-outs + castor.
# User requirement (2026-07-13): leave significant space around the motors --
# the N20 motor MOUNTS/brackets occupy far more than the bare motor body, so
# the keep-out spans the full bracket envelope (~34mm inward x ~34mm along the
# axle) with NO components (traces allowed underneath -- the bracket stands
# off the board). MOUNT_LEN = inward reach; MOUNT_W = along-axle width.
MOUNT_LEN = 34
MOUNT_W = 34
g.add_edge_slot((WHEEL_INSET, AXLE_Y - WHEEL_DIA/2, WHEEL_INSET + WHEEL_THK, AXLE_Y + WHEEL_DIA/2))
g.add_edge_slot((BOARD_W - WHEEL_INSET - WHEEL_THK, AXLE_Y - WHEEL_DIA/2, BOARD_W - WHEEL_INSET, AXLE_Y + WHEEL_DIA/2))
g.add_keepout((0, AXLE_Y - MOUNT_W/2, WHEEL_INSET + WHEEL_THK + MOUNT_LEN, AXLE_Y + MOUNT_W/2), allow_tracks=True)
g.add_keepout((BOARD_W - WHEEL_INSET - WHEEL_THK - MOUNT_LEN, AXLE_Y - MOUNT_W/2, BOARD_W, AXLE_Y + MOUNT_W/2), allow_tracks=True)
# Motor-mount screw holes (M2.5) flanking each motor for the bracket.
for my in (AXLE_Y - 14, AXLE_Y + 14):
    g.add_mounting_hole((WHEEL_INSET + WHEEL_THK + MOUNT_LEN - 4, my), 2.5)
    g.add_mounting_hole((BOARD_W - WHEEL_INSET - WHEEL_THK - MOUNT_LEN + 4, my), 2.5)
g.add_mounting_hole((CX, 8), 3.0)            # front castor/skid

# --- MCU + ESP32 sockets: side by side, top, center band (rows 15.24mm apart) ---
g.place("J4", 45, 82)                        # STM32 digital row
g.place("J8", 45 + 15.24, 82)                # STM32 analog row
g.place("J12", 90, 82)                       # ESP32 digital row
g.place("J13", 90 + 15.24, 82)               # ESP32 analog row
g.place("C8", 128, 82)                       # STM32 decoupling

# --- IR mux/demux (top), below the wall-sensor band, above the axle ---
g.place("U4", 20, 100, rot=90)
g.place("U5", 130, 100, rot=90)
g.place("C13", 20, 90)
g.place("C14", 130, 90)

# --- Motor driver breakout (socketed, top), center just behind the modules ---
g.place("J10", 66, 108)
g.place("J11", 76, 108)

# --- Motor connectors + encoder pull-ups (top), on the axle line in the free
# center gap BETWEEN the two side motors (side motor keep-outs are x13-37 /
# x113-137; the center x40-110 at the axle is clear). ---
g.place("J5", 60, AXLE_Y + 8, rot=90)        # motor A connector (below module band)
g.place("J6", BOARD_W - 60, AXLE_Y + 8, rot=270)  # motor B connector
g.place("R6", 46, AXLE_Y)
g.place("R7", 46, AXLE_Y + 6)
g.place("R8", BOARD_W - 46, AXLE_Y)
g.place("R9", BOARD_W - 46, AXLE_Y + 6)

# --- Start button (top, right side clear of the breakout) ---
g.place("SW1", 120, 114)
g.place("R10", 120, 98)

# --- Power section (top, rear band y>=145) ---
g.place("J2", 16, 150)                       # ext switch
g.place("F1", 28, 150)
g.place("Q1", 40, 150)
g.place("R1", 40, 142)
g.place("C1", 52, 150, value="100uF")
g.place("C2", 62, 150, value="100nF")
g.place("C4", 72, 150, value="10uF")
g.place("U1", 84, 150)
g.place("L1", 98, 158)
g.place("C3", 84, 142, value="100nF")
g.place("C5", 112, 150, value="22uF")
g.place("R2", 128, 148)                      # battery-sense dividers
g.place("C6", 136, 148)
g.place("R3", 128, 158)
g.place("R4", 136, 158)
g.place("C7", 128, 168)
g.place("R5", 136, 168)
g.place("J1", 60, 172)                       # 2S battery input
g.place("J3", 78, 172)                       # balance connector

# --- Sanity + 4-layer planes + save ---
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
# 2-layer verifiable version: GND poured on both OUTER layers (the intended
# 4-layer stackup moves this to an internal In1 plane + adds an In2 +3V3 plane
# in the GUI). See the layer-count note at the top.
g.add_zone("GND", pcbnew.F_Cu, plane)
g.add_zone("GND", pcbnew.B_Cu, plane)

g.save(r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb")
print("Saved PCB with", len(g._placed), "footprints placed,", len(remaining), "unplaced.")
