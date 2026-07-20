"""THT carrier placement v12 -- NET-AWARE clustering auto-placer.

v4-v11 scattered all 66 support resistors onto a generic bottom grid; that
made ~47% of nets span a resistor forest to reach the part they serve, and
routing failed. v12: only parts with a NATURAL fixed position are hard-placed
(optics by sensor geometry, sockets/connectors/switches by edge/ergonomics,
mux under the DevKit deck, the buck power block as one cluster, the four
emitter-bank gates centrally). EVERY support part (limiter/pull-up R,
indicator PMOS+R+LED, strap/encoder/IMU R, buzzer parts) is then AUTO-PLACED
on the bottom face by spiral-searching outward from the centroid of its
already-placed neighbours for a courtyard+hole-clear spot -- so each support
net stays LOCAL and routes. Only the inherently-spanning buses remain
(symmetric emitter pairs share one gate; the two board-spanning power rails)
-- those are hand-routed by handroute_power.py.
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
import board_geom

BASE = r"D:\Projects\micromouse-pcb\tht-assembly\pcb"
NETLIST = os.path.join(BASE, "netlist.net")
BOARD = os.path.join(BASE, "micromouse-tht.kicad_pcb")
MM = pcbnew.ToMM

# outline minus the antenna notch (DevKit antenna rides above the board)
pts = list(board_geom.BOARD_OUTLINE)
OUT = []
for (x, y) in pts:
    if (board_geom.ANTENNA_NOTCH[0] - 0.01 <= x <= board_geom.ANTENNA_NOTCH[2] + 0.01
            and y > 110 and abs(y - 120.0) > 0.01):
        continue
    OUT.append((x, y))
OUTLINE = [p for i, p in enumerate(OUT) if i == 0 or p != OUT[i - 1]]

def inside(px, py, poly=OUTLINE, m=1.2):
    # point-in-polygon with an inward margin (sample the 4 margin corners too)
    def pip(x, y):
        c = False
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if xi > x:
                    c = not c
        return c
    return all(pip(px + dx, py + dy) for dx in (-m, m) for dy in (-m, m))

# ---- FIXED anchors (ref -> (x, y, rot, flip)) --------------------------------
FIX = {
    # wall optics (SMD-verified geometry)
    "D1": (21.43, 16.27, 90, False), "D2": (78.57, 16.27, 90, False),
    "D3": (16.972, 30.668, 45, False), "D4": (81.232, 28.872, -45, False),
    "D5": (15.0, 45.47, 90, False), "D6": (85.0, 42.93, -90, False),
    "Q2": (30.95, 16.27, 90, False), "Q3": (69.05, 16.27, 90, False),
    "Q4": (13.4, 25.3, 135, False), "Q5": (86.6, 25.3, 45, False),
    "Q6": (15.0, 37.87, 90, False), "Q7": (85.0, 35.33, -90, False),
    # sockets / connectors / switches / mux
    "J13": (31.0, 94.5, 90, False), "J14": (31.0, 117.36, 90, False),
    "U4": (57, 113.4, 90, False),
    "J11": (78.5, 50, 90, False), "J12": (78.5, 65.24, 90, False),
    "J15": (25, 99, 0, False),
    "J10": (17.8, 100, 90, False), "J1": (16, 113.8, 0, False),
    "J9": (4, 12, 0, False), "J8": (63, 40, 90, False),
    "J5": (16, 72, 0, False), "J6": (77.5, 72, 0, False),
    "SW5": (3.5, 99.2, 90, False), "SW6": (3.5, 113, 90, False),
    # buttons A/B/C in the mid-gap between the power block (ends x65) and the
    # TB6612 socket (pin-1 origin at x78.5, extends +x); RST rear
    "SW1": (71, 46, 0, False), "SW3": (71, 55, 0, False),
    "SW4": (71, 64, 0, False), "SW2": (95, 105, 90, False),
    # power block (starts x24, right of the left-edge side optics D5/Q6;
    # 13mm part spacing for TO-220 + D9.5 inductor courtyards)
    "Q1": (5.5, 55, 0, False), "F1": (5.5, 61, 0, False),
    "C1": (11.5, 55, 0, False), "C2": (11.5, 61, 0, False),
    "U1": (26, 49, 0, False), "L1": (39, 49, 0, False), "D30": (49, 49, 0, False),
    "C5": (56, 49, 0, False), "C7": (62, 49, 0, False),
    "U7": (26, 62, 0, False), "L2": (39, 62, 0, False), "D31": (49, 62, 0, False),
    "C16": (56, 62, 0, False), "C17": (62, 62, 0, False),
    # emitter-bank gates near their banks; LINE gate under the array (bottom)
    "Q16": (50, 15, 0, False), "Q17": (50, 30, 0, False),
    "Q18": (50, 43, 0, False), "Q19": (50, 24, 0, True),
    "BZ1": (8, 88, 0, True),
}
# 14 indicator LEDs (D121-126 wall + D131-138 line) in the open nose (y3-12),
# two rows of 7 at ~9mm -- forward of the sensor row (y16+), clearly visible.
_NOSE = [(20 + 9 * i, 3.5) for i in range(7)] + [(20 + 9 * i, 11.5) for i in range(7)]
_IND_LEDS = [f"D{121+i}" for i in range(6)] + [f"D{131+i}" for i in range(8)]
for _ref, (_x, _y) in zip(_IND_LEDS, _NOSE):
    FIX[_ref] = (_x, _y, 0, False)

g = PcbGen(NETLIST)
g.setup_design_rules()
g.LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
g.add_outline(OUTLINE)
for (hx, hy, hr) in board_geom.MOUNT_HOLES:
    g.add_mounting_hole((hx, hy), hr * 2)

for ref, (x, y, rot, flip) in FIX.items():
    g.place(ref, x, y, rot=rot, flip=flip)

# ---- overlap primitives (courtyard same-face + hole-bbox any-face) -----------
def hole_bbox(fp):
    xs, ys = [], []
    for pad in fp.Pads():
        if not pad.HasHole():
            continue
        p = pad.GetPosition()
        r = MM(pad.GetDrillSize().x) / 2 + 0.35   # hole + hole-to-hole margin
        xs += [MM(p.x) - r, MM(p.x) + r]
        ys += [MM(p.y) - r, MM(p.y) + r]
    if not xs:
        bb = fp.GetBoundingBox(False)
        return (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
    return (min(xs), min(ys), max(xs), max(ys))

def cbb(fp):
    return g._courtyard_bbox_mm(fp)

def rects_hit(a, b, m=0.0):
    return (a[0] < b[2] + m and a[2] > b[0] - m and
            a[1] < b[3] + m and a[3] > b[1] - m)

# cache (hole_bbox, courtyard_bbox, flip) of every FIXED/placed part; only the
# candidate part's boxes are recomputed per trial -- collides() is then O(n),
# not O(n * pads).
_CACHE = []   # list of (hbb, cbb, flip)
def cache_placed(ref):
    fp = g._placed[ref]
    _CACHE.append((hole_bbox(fp), cbb(fp), fp.IsFlipped()))

for _r in FIX:
    cache_placed(_r)

def collides_boxes(fh, fc, ff):
    for (ohb, ocb, ofl) in _CACHE:
        if rects_hit(fh, ohb):
            return True
        if ff == ofl and rects_hit(fc, ocb, 0.35):   # > checker's 0.25 margin
            return True
    return False

# ---- net-aware spiral auto-placement -----------------------------------------
neigh = json.load(open(r"D:\tmp\tht_neigh.json"))
AUTO = [r for r in neigh if r not in FIX]
# most-constrained first: parts with the most already-fixed neighbours
def n_fixed(r):
    return sum(1 for x in neigh[r] if x in FIX)
AUTO.sort(key=lambda r: -n_fixed(r))

def anchor_xy(ref):
    ps = [(MM(g._placed[x].GetPosition().x), MM(g._placed[x].GetPosition().y))
          for x in neigh[ref] if x in g._placed]
    if not ps:
        return (50, 55)
    return (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))

placed_auto = 0
failed_place = []
for ref in AUTO:
    ax, ay = anchor_xy(ref)
    # place ONCE at the anchor (bottom face), extract geometry as Python rects
    fp = g.place(ref, ax, ay, rot=0, flip=True)
    cx0, cy0 = MM(fp.GetPosition().x), MM(fp.GetPosition().y)
    holes0 = []
    for pad in fp.Pads():
        if pad.HasHole():
            p = pad.GetPosition()
            holes0.append((MM(p.x) - cx0, MM(p.y) - cy0,
                           MM(pad.GetDrillSize().x) / 2 + 0.35))
    if not holes0:
        holes0 = [(0, 0, 0.5)]
    c = cbb(fp)
    cw, ch = (c[2] - c[0]) / 2, (c[3] - c[1]) / 2   # courtyard half-extents

    def trial_boxes(x, y, rot90):
        hs = [((-dy, dx, r) if rot90 else (dx, dy, r)) for (dx, dy, r) in holes0]
        hx = [x + dx - r for dx, dy, r in hs] + [x + dx + r for dx, dy, r in hs]
        hy = [y + dy - r for dx, dy, r in hs] + [y + dy + r for dx, dy, r in hs]
        fh = (min(hx), min(hy), max(hx), max(hy))
        w, h = (ch, cw) if rot90 else (cw, ch)
        fc = (x - w, y - h, x + w, y + h)
        return fh, fc

    done = None
    for radius in [r * 1.6 for r in range(0, 30)]:
        steps = max(1, int(radius / 1.6) * 6)
        for s in range(steps if radius else 1):
            th = 2 * math.pi * s / max(1, steps)
            x = round(ax + radius * math.cos(th), 2)
            y = round(ay + radius * math.sin(th), 2)
            if not inside(x, y):
                continue
            for rot in (0, 90):
                fh, fc = trial_boxes(x, y, rot == 90)
                if not collides_boxes(fh, fc, True):
                    done = (x, y, rot, fh, fc)
                    break
            if done:
                break
        if done:
            break
    if done:
        x, y, rot, fh, fc = done
        fp.SetPosition(g._mm(x, y))
        if rot:
            fp.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
        _CACHE.append((fh, fc, True))
        placed_auto += 1
    else:
        failed_place.append(ref)

print(f"fixed {len(FIX)}, auto-placed {placed_auto}, FAILED {failed_place}")

# ---- repair pass: drive check_overlaps -> 0 using the ACCURATE checker -------
# HARD parts never move (geometry/ergonomics/edge); everything else can be
# re-spiralled to a fresh clear spot.
HARD = ({"D1","D2","D3","D4","D5","D6","Q2","Q3","Q4","Q5","Q6","Q7"}
        | {r for r in FIX if r.startswith("J")} | {f"SW{i}" for i in range(1,7)}
        | {"U1","U4","U7","L1","L2","Q16","Q17","Q18","Q19"})
def real_boxes(ref):
    fp = g._placed[ref]
    return (hole_bbox(fp), g._courtyard_boxes_mm(fp), fp.IsFlipped())
def hits_any(ref, hb, cbs, fl):
    for o, ofp in g._placed.items():
        if o == ref:
            continue
        ohb = hole_bbox(ofp)
        if rects_hit(hb, ohb):
            return True
        if fl == ofp.IsFlipped():
            ocbs = g._courtyard_boxes_mm(ofp)
            if any(rects_hit(a, b, 0.3) for a in cbs for b in ocbs):
                return True
    return False
for it in range(40):
    bad = g.check_overlaps(margin_mm=0.25)
    if not bad:
        print(f"repair: 0 overlaps after {it} iterations")
        break
    movable = [r for pr in bad for r in pr if r not in HARD]
    if not movable:
        print(f"repair STUCK: all {len(bad)} overlaps involve HARD parts: {bad[:8]}")
        break
    ref = max(set(movable), key=movable.count)   # the most-conflicting movable part
    fp = g._placed[ref]
    ax, ay = MM(fp.GetPosition().x), MM(fp.GetPosition().y)
    moved = False
    for radius in [r * 1.4 for r in range(1, 40)]:
        for s in range(max(6, int(radius))):
            th = 2 * math.pi * s / max(6, int(radius))
            x = round(ax + radius * math.cos(th), 2)
            y = round(ay + radius * math.sin(th), 2)
            if not inside(x, y):
                continue
            fp.SetPosition(g._mm(x, y))
            hb, cbs, fl = real_boxes(ref)
            if not hits_any(ref, hb, cbs, fl):
                moved = True
                break
        if moved:
            break
    if not moved:
        print(f"repair: could not relocate {ref}")
        break
missing = g.unplaced_refs()
print("unplaced:", sorted(missing) if missing else "NONE")

RECT = [(1, 1), (99, 1), (99, 119), (1, 119)]
g.add_zone("GND", pcbnew.F_Cu, RECT)
g.add_zone("GND", pcbnew.B_Cu, RECT)
g.add_zone("GND", pcbnew.In1_Cu, RECT)
g.add_zone("PLUS3V3", pcbnew.In2_Cu, RECT)

g.assert_netlist_pads_mapped()
bad = g.check_overlaps(margin_mm=0.25)
print("same-face courtyard overlaps:", len(bad) if bad else "NONE")
g.save(BOARD)
print("SAVED", BOARD)
