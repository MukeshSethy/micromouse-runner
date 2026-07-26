"""Targeted fix for the one genuine unrouted edge left after Freerouting:
PLUS3V3 net, a stub near (72.5,58.5) never reached D29's pad-1 at (84,71.65).
Uses the same gen_pcb.py A* router as the rest of the pipeline, restricted to
just this one net/edge instead of a full heal_all.py convergence loop (which
was taking too long generically re-deriving the same 24 GND-fragment items).
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
d29_pad = None
for pp in g._pads_geo():
    if pp["ref"] == "D29" and pp["num"] == "1":
        d29_pad = (pp["cx"], pp["cy"])
        break
print("D29 pad1 at", d29_pad)

ok = g.route_net("PLUS3V3", width_mm=0.4, clearance_mm=0.3, max_expansions=400000)
print("route_net PLUS3V3:", "unrouted left:", len(g._unrouted))
for u in g._unrouted:
    print("  ", u)

if g._unrouted:
    still = []
    for (net, p1, p2, reason) in g._unrouted:
        if net != "PLUS3V3":
            still.append((net, p1, p2, reason))
            continue
        ok2 = (g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=0.25,
                            grid_mm=0.2, max_expansions=600000)
               or g.retry_edge(net, p1, p2, width_mm=0.25, clearance_mm=0.18,
                               grid_mm=0.1, max_expansions=800000)
               or g.retry_edge(net, p1, p2, width_mm=0.25, clearance_mm=0.15,
                               grid_mm=0.1, max_expansions=1000000))
        print("retry", net, p1, "->", p2, ":", "OK" if ok2 else "FAILED")
        if not ok2:
            still.append((net, p1, p2, reason))
    g._unrouted = still

print("zone fill:", g.fill_zones())
pcbnew.SaveBoard(BOARD, g.board)
print("saved", BOARD)
print("final unrouted:", len(g._unrouted))
