"""Second half of the edge-clearance fix, run as a FRESH process (the
project's own tooling notes that removing tracks then continuing to use
pcbnew in the same process corrupts SWIG proxies -- route_loaded.py has the
same warning). fix_edge_clearance2.py already ripped up the 5 violating
WALL5_SENSE/BATT_RAW segments and saved; this script reloads fresh and
reroutes those two nets, respecting the router's normal 0.6mm effective
edge margin (well over the board's 0.3mm min_copper_edge_clearance rule).
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
