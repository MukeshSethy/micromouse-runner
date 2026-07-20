"""Route the THT carrier: all non-plane nets (GND rides F/B/In1 pours,
PLUS3V3 rides the In2 plane -- every pad is THT so plane connection is
automatic at zone fill). Power nets first at 0.8mm, then signals."""
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
import board_geom

BASE = r"D:\Projects\micromouse-pcb\tht-assembly\pcb"
NETLIST = os.path.join(BASE, "netlist.net")
BOARD = os.path.join(BASE, "micromouse-tht.kicad_pcb")

g = PcbGen(NETLIST)
g.board = pcbnew.LoadBoard(BOARD)
try:
    _ = [fp.GetReference() for fp in g.board.GetFootprints()]
except TypeError:
    raise SystemExit("DEGRADED LOAD -- retry")
g.setup_design_rules()
g.LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
g._nets = {}
for code, ni in g.board.GetNetsByNetcode().items():
    if ni.GetNetname():
        g._nets[ni.GetNetname()] = ni
g._outline_pts = None   # outline occupancy handled via edge margin below
# rebuild outline points from Edge.Cuts for the router's inside test
pts = []
for d in g.board.GetDrawings():
    if d.GetLayerName() == "Edge.Cuts" and d.GetClass() == "PCB_SHAPE":
        try:
            s_, e_ = d.GetStart(), d.GetEnd()
            pts.append(((pcbnew.ToMM(s_.x), pcbnew.ToMM(s_.y)),
                        (pcbnew.ToMM(e_.x), pcbnew.ToMM(e_.y))))
        except Exception:
            pass
# chain segments into a polygon
poly = [pts[0][0], pts[0][1]]
used = {0}
while len(used) < len(pts):
    for i, (a, b) in enumerate(pts):
        if i in used:
            continue
        if abs(a[0]-poly[-1][0]) < 0.01 and abs(a[1]-poly[-1][1]) < 0.01:
            poly.append(b); used.add(i); break
        if abs(b[0]-poly[-1][0]) < 0.01 and abs(b[1]-poly[-1][1]) < 0.01:
            poly.append(a); used.add(i); break
    else:
        break
g._outline_pts = poly
g._extra_keepouts = []
for (hx, hy, hr) in board_geom.MOUNT_HOLES:
    m = hr + 0.75
    g._extra_keepouts.append((hx - m, hy - m, hx + m, hy + m))
g._pads_geo_cache = None
g._track_segs, g._vias = [], []
g._unrouted = []

POUR = {"GND", "PLUS3V3"}
POWER = {"BATT_RAW", "VM_BATT", "VM_6V", "SW_3V3", "SW_6V", "F1_OUT", "MOTA_P",
         "MOTA_N", "MOTB_P", "MOTB_N"}
CLR = 0.3
t0 = time.time()
all_nets = sorted(set(g.pad_to_net.values()) - POUR - {""})

def width_for(n):
    return 0.8 if n in POWER else 0.4

for n in sorted(all_nets, key=lambda n: (n not in POWER)):
    g.route_net(n, width_mm=width_for(n), clearance_mm=CLR, max_expansions=300000)
print(f"[{time.time()-t0:.0f}s] first pass done, {len(g._unrouted)} fails")

prev, g._unrouted[:] = list(g._unrouted), []
for (net, p1, p2, reason) in prev:
    ok = False
    for (ww, cc, gg, ee) in ((width_for(net), CLR, None, 500000),
                             (width_for(net), 0.4, 0.25, 600000),
                             (width_for(net), CLR, 0.25, 900000),
                             (0.4, CLR, 0.2, 1200000),
                             (0.3, 0.18, 0.2, 2000000),
                             (0.25, 0.18, 0.1, 2500000)):
        kw = dict(width_mm=ww, clearance_mm=cc, max_expansions=ee)
        if gg: kw["grid_mm"] = gg
        if g.retry_edge(net, p1, p2, **kw):
            ok = True
            break
    if not ok:
        g._unrouted.append((net, p1, p2, reason))
        print(f"STILL UNROUTED: {net} {p1} -> {p2}")
print(f"[{time.time()-t0:.0f}s] ladder done, {len(g._unrouted)} left")
print("zone fill:", g.fill_zones())
pcbnew.SaveBoard(BOARD, g.board)
g.board.BuildConnectivity()
print("ratsnest:", g.board.GetConnectivity().GetUnconnectedCount(True))
print(f"SAVED, unrouted={len(g._unrouted)}")
