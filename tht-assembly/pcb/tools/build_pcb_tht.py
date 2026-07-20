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

def bbox_inside(x1, y1, x2, y2, poly=OUTLINE, m=0.6):
    # all 4 corners of a part's extent must be on-board (checking only the
    # CENTRE lets a long axial resistor hang a pad off the chamfered front
    # edge -- the closer caught R152 at y=-9.4).
    def pip(x, y):
        c = False; n = len(poly)
        for i in range(n):
            ax, ay = poly[i]; bx, by = poly[(i + 1) % n]
            if (ay > y) != (by > y):
                xi = ax + (y - ay) * (bx - ax) / (by - ay)
                if xi > x:
                    c = not c
        return c
    return (pip(x1 - m, y1 - m) and pip(x2 + m, y1 - m)
            and pip(x1 - m, y2 + m) and pip(x2 + m, y2 + m))

# ---- FIXED anchors (ref -> (x, y, rot, flip)) --------------------------------
FIX = {
    # wall optics (SMD-verified geometry)
    "D1": (21.43, 16.27, 90, False), "D2": (78.57, 16.27, 90, False),
    "D3": (16.972, 30.668, 45, False), "D4": (81.232, 28.872, -45, False),
    "D5": (15.0, 45.47, 90, False), "D6": (85.0, 42.93, -90, False),
    "Q2": (30.95, 16.27, 90, False), "Q3": (69.05, 16.27, 90, False),
    "Q4": (13.4, 25.3, 135, False), "Q5": (86.6, 25.3, 45, False),
    "Q6": (15.0, 37.87, 90, False), "Q7": (85.0, 35.33, -90, False),
    # sockets / connectors / switches (mux U4 + JTAG J8 removed). DevKit socket
    # shifted to pin1 x=22 so its 53mm row sits BETWEEN the bracket holes
    # (x17.25 / x82.75) instead of over the right one.
    "J13": (25.5, 94.5, 90, False), "J14": (25.5, 117.36, 90, False),
    "J11": (78.5, 50, 90, False), "J12": (78.5, 65.24, 90, False),
    "J15": (25, 99, 0, False),
    "J10": (17.8, 100, 90, False), "J1": (16, 113.8, 0, False),
    "J9": (35, 100, 0, False),   # balance tap: rear-inboard, OUT of the diag-L
                                 # sensor's forward path (was (4,12) -- blocked it)
    "J5": (16, 66, 0, False), "J6": (68, 73, 0, False),
    # 2 RGB LEDs (top face, visible in the open mid-band; repair nudges if tight)
    "D40": (36, 90, 0, False), "D41": (60, 90, 0, False),
    "SW5": (3.5, 99.2, 90, False), "SW6": (3.5, 113, 90, False),
    # buttons A/B/C in the empty lower-centre (top face, accessible); RST rear
    "SW1": (44, 82, 0, False), "SW3": (54, 82, 0, False),
    "SW4": (64, 82, 0, False), "SW2": (91, 105, 90, False),
    # power block (starts x24, right of the left-edge side optics D5/Q6;
    # 13mm part spacing for TO-220 + D9.5 inductor courtyards)
    "Q1": (5.5, 55, 0, False), "F1": (5.5, 61, 0, False),
    "C1": (11.5, 55, 0, False), "C2": (11.5, 61, 0, False),
    "U1": (26, 49, 0, False), "L1": (39, 49, 0, False), "D30": (49, 49, 0, False),
    "C5": (56, 49, 0, False), "C7": (62, 49, 0, False),
    "U7": (26, 62, 0, False), "L2": (39, 62, 0, False), "D31": (49, 62, 0, False),
    "C16": (56, 62, 0, False), "C17": (62, 62, 0, False),
    # 3 wall emitter-bank gates near their banks (line gate Q19 removed)
    "Q16": (50, 15, 0, False), "Q17": (50, 30, 0, False), "Q18": (50, 43, 0, False),
    "BZ1": (11, 88, 0, True),
}
# 6 wall-indicator LEDs (D121-126) placed INBOARD, each BEHIND its sensor
# pair (toward board centre) exactly like the SMD board's D23-28 -- so the
# sensors' OUTWARD IR paths stay clear. WALL1..6 = front-L, front-R, diag-L,
# diag-R, side-L, side-R. (User: nothing may obstruct the emitters/receivers
# toward the outside; all support parts go inboard.)
_IND_POS = {
    "D121": (26, 24), "D122": (74, 24),    # behind the front pairs (y16 -> 24)
    "D123": (26, 33), "D124": (74, 33),    # inboard of the diagonals
    "D125": (27, 44), "D126": (73, 44),    # inboard of the side pairs
}
for _ref, (_x, _y) in _IND_POS.items():
    FIX[_ref] = (_x, _y, 0, False)

# ---- OPTICAL KEEPOUT: the outward IR path of every wall sensor. NO part
# (support, indicator, connector) may sit in these bands -- only the sensors
# themselves, at the perimeter, facing out. The auto-placer + repair reject
# any position whose extent intersects a band.
# bands sized to each sensor's actual outward BEAM (not a generous box) --
# a part BODY (opaque) here blocks IR; thin leads passing through are OK.
OPTICAL = [
    (13, 0, 39, 15),    # front-left pair -> forward (nose)
    (61, 0, 87, 15),    # front-right pair -> forward
    (0, 10, 17, 30),    # diagonal-left -> front-left corner
    (83, 10, 100, 30),  # diagonal-right -> front-right corner
    (0, 34, 15, 47),    # side-left -> left edge (beam ~y38-46)
    (85, 34, 100, 47),  # side-right -> right edge
]
def in_optical(x1, y1, x2, y2, m=0.4):
    return any(x2 > kx1 - m and x1 < kx2 + m and y2 > ky1 - m and y1 < ky2 + m
               for (kx1, ky1, kx2, ky2) in OPTICAL)

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
    # anchor on FIXED neighbours only (optics/LEDs/sockets) -- centroid of ALL
    # neighbours let support parts drag each other away from their real anchor
    # and scattered the buzzer/RGB/indicator clusters (v1: those nets failed to
    # route because the parts spanned to reach each other).
    fixed = [x for x in neigh[ref] if x in FIX]
    src = fixed if fixed else [x for x in neigh[ref] if x in g._placed]
    ps = [(MM(g._placed[x].GetPosition().x), MM(g._placed[x].GetPosition().y))
          for x in src if x in g._placed]
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
                if (bbox_inside(*fc) and not in_optical(*fc)
                        and not collides_boxes(fh, fc, True)):
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
        | {f"H{i}" for i in range(1, 6)}          # mount holes -- NEVER move
        | {"U1","U7","L1","L2","Q16","Q17","Q18"})
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
            cb = cbb(fp)
            if (bbox_inside(*cb) and not in_optical(*cb)
                    and not hits_any(ref, hb, cbs, fl)):
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
