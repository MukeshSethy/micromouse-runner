"""THT carrier board: outline + placement + zones (no routing -- route_tht.py).

Placement doctrine (worked out against the hard constraints):
  - sensor geometry (D1-6, Q2-7, LS1-8) is COPIED from the SMD rev-7.2 board
    verbatim -- it is research-verified and all three part families are THT
  - motor bodies own the waist top face (x2.7-46.2 / x53.8-97.3, y76.9-91.1):
    nothing else goes there
  - the DevKitC-1 lies across the REAR (rows y94.5 / y117.36, pin1 x31.0,
    USB end facing RIGHT where the corridor is kept clear); only FLAT parts
    live under its deck (the mux DIP is soldered flat there, no socket)
  - the antenna U-notch of the SMD outline is REMOVED (DevKit antenna sits
    ~10 mm above the board) -- gives the rear row continuous board
  - left rear column: XT60 + XH battery in; left edge: the two slide switches
  - front-center pocket (between the front sensor pairs, above the line
    array): 8 horizontal 1k indicator resistors
  - mid band, left-to-right: power block | indicator field | TB6612 socket
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
import board_geom

BASE = r"D:\Projects\micromouse-pcb\tht-assembly\pcb"
NETLIST = os.path.join(BASE, "netlist.net")
BOARD = os.path.join(BASE, "micromouse-tht.kicad_pcb")

# ---- outline: SMD outline minus the antenna U-notch ---------------------------
# board_geom.BOARD_OUTLINE traces the notch between the two rear segments at
# y=120; rebuild the polygon with the rear edge straight across.
OUT = []
skip = False
pts = list(board_geom.BOARD_OUTLINE)
for i, (x, y) in enumerate(pts):
    if abs(y - board_geom.ANTENNA_NOTCH[1]) < 0.01 or \
       (abs(y - 120.0) > 0.01 and board_geom.ANTENNA_NOTCH[0] - 0.01 <= x <= board_geom.ANTENNA_NOTCH[2] + 0.01
        and y > 110):
        continue      # drop notch-wall points
    OUT.append((x, y))
# dedupe consecutive duplicates
OUTLINE = [p for i, p in enumerate(OUT) if i == 0 or p != OUT[i - 1]]

g = PcbGen(NETLIST)
g.setup_design_rules()
g.LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]

# ---- placements ----------------------------------------------------------------
# copied SMD optic geometry (ref: (x, y, rot, flip))
OPTICS = {
    "D1": (21.43, 16.27, 90, False),  "D2": (78.57, 16.27, 90, False),
    "D3": (16.972, 30.668, 45, False), "D4": (81.232, 28.872, -45, False),
    "D5": (15.0, 45.47, 90, False),   "D6": (85.0, 42.93, -90, False),
    "Q2": (30.95, 16.27, 90, False),  "Q3": (69.05, 16.27, 90, False),
    "Q4": (13.4, 25.3, 135, False),   "Q5": (86.6, 25.3, 45, False),
    "Q6": (15.0, 37.87, 90, False),   "Q7": (85.0, 35.33, -90, False),
}
for k in range(8):
    OPTICS[f"LS{k+1}"] = (16.663 + 9.525 * k, 19.0, 90, True)

P = {}   # ref -> (x, y, rot)
P.update({r: (x, y, rot) for r, (x, y, rot, fl) in OPTICS.items()})

# ---- v6: explicit bottom-face tables + measured-courtyard greedy packers ----
# Bottom face budget: parts <= ~7mm tall (ride height). Horizontal axial R
# (3.5mm), TO-92 (5.2mm), DO-35 (2.5mm), PS1240 piezo (7mm) qualify.
ALL_R = ([f"R{101+i}" for i in range(8)] + [f"R{111+i}" for i in range(8)]
         + [f"R{131+i}" for i in range(6)] + [f"R{141+i}" for i in range(6)]
         + ["R61", "R62", "R63", "R64"]
         + [f"R{151+i}" for i in range(6)] + [f"R{161+i}" for i in range(8)]
         + ["R1", "R2", "R3", "R69", "R70", "R73", "R74", "R75", "R76",
            "R77", "R78", "R10", "R65", "R81",
            "R6", "R7", "R8", "R9", "R57", "R58"])
R_SLOTS = ([(x, 28 + 4.4 * r) for r in range(10)
            for x in (10, 24.5, 39, 53.5, 68, 82.5)
            if (x, round(28 + 4.4 * r, 1)) not in
               {(82.5, 50.0), (82.5, 63.2), (82.5, 67.6), (10, 67.6)}]
           + [(x, y) for y in (98.5, 105.5) for x in (12.5, 26, 39.5, 53)]
           + [(81, 112.5), (52, 90.5)])
assert len(R_SLOTS) >= len(ALL_R), (len(R_SLOTS), len(ALL_R))
BOT = {}
for ref, (x, y) in zip(ALL_R, R_SLOTS):
    BOT[ref] = (x, y, 0)
_fets = ([f"Q{121+i}" for i in range(6)] + [f"Q{131+i}" for i in range(8)]
         + ["Q16", "Q17", "Q18", "Q19", "Q35", "Q34"])
F_SLOTS = ([(91, 28 + 5.6 * r) for r in range(4)]
           + [(38 + 7.5 * k, 112.5) for k in range(5)]
           + [(x, y) for y in (98.5, 105.5) for x in (67, 74.5, 82, 89.5)]
           + [(23.5, 90.5), (31, 90.5), (38.5, 90.5)])
assert len(F_SLOTS) >= len(_fets)
for ref, (x, y) in zip(_fets, F_SLOTS):
    BOT[ref] = (x, y, 0)
BOT["D29"] = (30, 112.5, 0)
BOT["BZ1"] = (50, 78, 0)
P.update(BOT)

# ---- top face fixed parts -----------------------------------------------------
P.update({
    # left strip (packed top-down by the greedy pass below): Q1/F1/C1
    # power ranks + C column: packed below
    "C2": (4.5, 44, 0), "C6": (4.5, 35, 0), "C19": (13, 8, 0),
    "J8": (61, 40, 90),
    "J11": (78.5, 50, 90), "J12": (78.5, 65.24, 90),
    "SW2": (95, 105, 90),
    "J5": (16, 72, 0), "J6": (77.5, 72, 0),
    "J13": (31.0, 94.5, 90), "J14": (31.0, 117.36, 90),
    "U4": (57, 113.4, 90),
    "J10": (17.8, 100, 90), "J1": (16, 113.8, 0),
    "J15": (25, 99, 0),
    "SW5": (3.5, 99.2, 90), "SW6": (3.5, 113, 90),
    "J9": (4.2, 19.6, 0),
})
# nose: 8 line-indicator LEDs, 2x4 grid
for i in range(8):
    P[f"D{131+i}"] = (38 + 5.7 * (i % 4), 4.5 if i < 4 else 10.2, 0)
# mid rows packed after initial placement (see PACK below): wall LEDs + buttons
for i in range(6):
    P[f"D{121+i}"] = (52 + 5.7 * i, 51, 0)      # seed; PACK refines
P.update({"SW1": (67, 51, 0), "SW3": (67, 60.5, 0), "SW4": (95, 115, 90)})
# power parts seeds; PACK refines rank x-positions with measured widths
P.update({
    "Q1": (5.5, 47, 0), "F1": (4.5, 54, 0), "C1": (3.5, 60.5, 0),
    "U1": (18, 52, 0), "L1": (29, 52, 0), "D30": (38, 52, 0),
    "C5": (45.5, 47, 0), "C7": (45.5, 53.5, 0),
    "U7": (18, 63, 0), "L2": (29, 63, 0), "D31": (38, 63, 0),
    "C16": (45.5, 60, 0), "C17": (45.5, 66.5, 0),
})

# ---- build ---------------------------------------------------------------------
g.add_outline(OUTLINE)
for (hx, hy, hr) in board_geom.MOUNT_HOLES:
    g.add_mounting_hole((hx, hy), hr * 2)

placed = 0
for ref, (x, y, rot) in P.items():
    flip = OPTICS.get(ref, (0, 0, 0, False))[3] or (ref in BOT)
    g.place(ref, x, y, rot=rot, flip=flip)
    placed += 1


# ---- PACK: measured-courtyard greedy passes -----------------------------------
def _bbox(ref):
    fp = g._placed[ref]
    bb = fp.GetBoundingBox(False)
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
            pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))

def _move(ref, x, y):
    fp = g._placed[ref]
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))

def pack_row(refs, x0, y, gap=0.6):
    cur = x0
    for r in refs:
        x1, _, x2, _ = _bbox(r)
        w = x2 - x1
        fp = g._placed[r]
        cx = pcbnew.ToMM(fp.GetPosition().x)
        _move(r, cur + (cx - x1), y)
        cur += w + gap
    return cur

def pack_col(refs, x, y0, gap=0.6):
    cur = y0
    for r in refs:
        _, y1, _, y2 = _bbox(r)
        h = y2 - y1
        fp = g._placed[r]
        cy = pcbnew.ToMM(fp.GetPosition().y)
        _move(r, x, cur + (cy - y1))
        cur += h + gap
    return cur

end1 = pack_col(["Q1", "F1", "C1"], 4.8, 49.0)          # left strip
print(f"left strip ends y={end1:.1f}")
end2 = pack_row(["U1", "L1", "D30", "C5"], 14, 52)      # 3V3 rank
end3 = pack_row(["U7", "L2", "D31", "C16"], 14, 63.2)   # 6V rank
print(f"power ranks end x={end2:.1f}/{end3:.1f}")
_move("C7", end2 + 3.0, 52)
_move("C17", end3 + 3.0, 63.2)
end4 = pack_row([f"D{121+i}" for i in range(6)], 27, 70.8, gap=0.7)   # wall LEDs (waist row)
print(f"wall LED row ends x={end4:.1f}")
print("buttons at fixed column x70")
missing = g.unplaced_refs()
print(f"placed {placed}; unplaced: {sorted(missing) if missing else 'NONE'}")

# zones: GND on F/B/In1, PLUS3V3 on In2 (full board rect)
RECT = [(1, 1), (99, 1), (99, 119), (1, 119)]
g.add_zone("GND", pcbnew.F_Cu, RECT)
g.add_zone("GND", pcbnew.B_Cu, RECT)
g.add_zone("GND", pcbnew.In1_Cu, RECT)
g.add_zone("PLUS3V3", pcbnew.In2_Cu, RECT)

g.assert_netlist_pads_mapped()
for _r in ("J13", "J14", "J11", "J12", "J15", "J8", "SW5", "U4", "C2", "D5", "J6", "SW4"):
    _fp = g._placed.get(_r)
    if _fp:
        _bb = _fp.GetBoundingBox(False)
        print(f"  {_r}: x[{pcbnew.ToMM(_bb.GetLeft()):.1f},{pcbnew.ToMM(_bb.GetRight()):.1f}] "
              f"y[{pcbnew.ToMM(_bb.GetTop()):.1f},{pcbnew.ToMM(_bb.GetBottom()):.1f}]")
IGN = {frozenset(p) for p in (("D3", "Q4"), ("D3", "Q6"), ("D4", "Q5"), ("D4", "Q7"), ("J9", "Q4"))}
bad = [pr for pr in g.check_overlaps(margin_mm=0.25) if frozenset(pr) not in IGN]
print("overlaps:", bad if bad else "NONE")
g.save(BOARD)
print("SAVED", BOARD)
