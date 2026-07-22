"""Fresh, clean re-route of ESP_EN after clearing it entirely (rev 8
follow-up): connects R11 pad2 -> C9 pad1 -> U3 pad3 -> SW4 pad1, one edge at
a time. See PROJECT context in route_switch_nets.py for why
setup_design_rules() is deliberately NOT called here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")


def main():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
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

    edges = [
        ("R11 -> C9", (33.0875, 60.0), (39.05, 60.0)),
        ("C9 -> U3pad3", (39.05, 60.0), (58.75, 109.42)),
        ("U3pad3 -> SW4", (58.75, 109.42), (65.2, 103.45)),
    ]
    for label, p1, p2 in edges:
        print(f"routing ESP_EN {label}: {p1} -> {p2}")
        ok = (g.retry_edge("ESP_EN", p1, p2, width_mm=0.25, clearance_mm=0.18,
                            grid_mm=0.15, max_expansions=100000)
              or g.retry_edge("ESP_EN", p1, p2, width_mm=0.2, clearance_mm=0.15,
                               grid_mm=0.1, max_expansions=200000))
        print(f"  -> {'OK' if ok else 'FAILED'}")
        if not ok:
            break

    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
