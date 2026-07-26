"""Fix the 3 copper_edge_clearance DRC errors left after Freerouting (tracks on
WALL5_SENSE and BATT_RAW routed too close to the wheel-notch inner edges,
0.166-0.215mm actual vs the board's 0.3mm min_copper_edge_clearance rule).

Freerouting's own edge-clearance handling isn't tied to this project's
gen_pcb.py-side outline margin logic (_outline_ok, default 0.6mm effective
margin -- comfortably over the 0.3mm rule), so re-deriving just these two
nets with the in-house router is expected to clear the violation. This
mirrors the same approach already proven safe for the PLUS3V3/D29 fix
earlier in this session (route_net() rebuilds the net's MST and is a no-op
over already-good edges; DRC stayed clean of new violations there).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")


def load():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
    g.setup_design_rules()
    g.LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
    g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
    g._nets = {}
    for code, ni in g.board.GetNetsByNetcode().items():
        if ni.GetNetname():
            g._nets[ni.GetNetname()] = ni
    g._outline_pts = list(BOARD_OUTLINE)
    g._extra_keepouts = []
    for (sx1, sy1, sx2, sy2) in WHEEL_NOTCHES:
        g._extra_keepouts.append((sx1 - 0.6, sy1 - 0.6, sx2 + 0.6, sy2 + 0.6))
    for (hx, hy, hr) in MOUNT_HOLES:
        m = hr + 0.75
        g._extra_keepouts.append((hx - m, hy - m, hx + m, hy + m))
    g._pads_geo_cache = None
    g._track_segs, g._vias = [], []
    for t in g.board.GetTracks():
        net = t.GetNet().GetNetname()
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            g._vias.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), net,
                            pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        elif t.GetClass() == "PCB_TRACK":
            a, b = t.GetStart(), t.GetEnd()
            g._track_segs.append(((pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)),
                                  (pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)), net,
                                  pcbnew.ToMM(t.GetWidth()) / 2, t.GetLayer()))
    g._unrouted = []
    return g


# First, RIP UP the two specific violating track segments so the router has
# room to reroute around them (gen_pcb.py's own router always respects the
# edge margin, so a fresh path here will not touch the edge). Identified by
# the DRC-reported violation positions (drc_post_route2.json):
#   WALL5_SENSE @ (23.2616,107.1795) and (13.2662,97.1841)
#   BATT_RAW    @ (90.054,64.5)
VIOLATION_NETS = {"WALL5_SENSE", "BATT_RAW"}
VIOLATION_PTS = [
    ("WALL5_SENSE", 23.2616, 107.1795),
    ("WALL5_SENSE", 13.2662, 97.1841),
    ("BATT_RAW", 90.054, 64.5),
]

board = pcbnew.LoadBoard(BOARD)
removed = 0
for t in list(board.GetTracks()):
    if t.GetClass() != "PCB_TRACK":
        continue
    net = t.GetNet().GetNetname()
    if net not in VIOLATION_NETS:
        continue
    a, b = t.GetStart(), t.GetEnd()
    ax, ay = pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)
    bx, by = pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)
    for (vnet, vx, vy) in VIOLATION_PTS:
        if vnet != net:
            continue
        # point-to-segment distance
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t_ = 0 if L2 == 0 else max(0, min(1, ((vx - ax) * dx + (vy - ay) * dy) / L2))
        px, py = ax + t_ * dx, ay + t_ * dy
        import math
        if math.hypot(px - vx, py - vy) < 0.5:
            board.Remove(t)
            removed += 1
            break
print(f"removed {removed} violating track segment(s)")
pcbnew.SaveBoard(BOARD, board)

g = load()
for net in ("WALL5_SENSE", "BATT_RAW"):
    width = 0.3 if net == "WALL5_SENSE" else 0.8
    g._unrouted = []
    g.route_net(net, width_mm=width, clearance_mm=0.3, max_expansions=400000)
    print(f"{net}: unrouted after route_net = {len(g._unrouted)}")
    still = []
    for (n, p1, p2, reason) in g._unrouted:
        ok = (g.retry_edge(n, p1, p2, width_mm=width, clearance_mm=0.25,
                           grid_mm=0.2, max_expansions=600000)
              or g.retry_edge(n, p1, p2, width_mm=max(0.25, width - 0.2),
                              clearance_mm=0.18, grid_mm=0.1, max_expansions=800000))
        print(f"  retry {n} {p1}->{p2}: {'OK' if ok else 'FAILED'} ({reason})")
        if not ok:
            still.append((n, p1, p2, reason))
    g._unrouted = still

print("zone fill:", g.fill_zones())
pcbnew.SaveBoard(BOARD, g.board)
print("saved", BOARD)
print("final unrouted:", len(g._unrouted))
for u in g._unrouted:
    print("  ", u)
