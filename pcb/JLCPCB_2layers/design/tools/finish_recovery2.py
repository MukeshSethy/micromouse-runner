"""Recovery step 4: close the remaining real gaps after finish_recovery.py --
U8's local GND pour fragment (pad2/pad25 isolated from the main GND zone),
a cluster of stray/disconnected GND stitch vias near (63-67,98-101) left
over from heal_all.py's automatic fragment-bridging, the WALL_EMIT_SIDE
gap that failed to auto-route, and a re-check of ESP_EN (reported fixed
by finish_recovery.py but still showing in DRC -- verify and re-fix if
needed).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
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
    return g


# GND stitch vias near J6/BUZZ area that are isolated from each other/the
# main zone -- chain them together with short GND tracks on F.Cu.
STRAY_VIA_CHAIN = [
    (63.44, 98.31), (64.3375, 99.610147), (65.237499, 99.608852),
    (65.735, 100.209), (65.135, 100.809), (66.334999, 100.809),
    (66.935, 101.409), (66.935, 100.209), (66.334999, 99.609), (65.64, 98.01),
]

GAPS = [
    ("GND", (47.6875, 58.25), (49.75, 57.4375)),   # U8 pad2 <-> pad25
    ("ESP_EN", (69.7295, 101.2295), (70.5, 102.0)),
    ("WALL_EMIT_SIDE", (60.8173, 66.0605), (60.1665, 80.3831)),
]


def main():
    g = load()
    board = g.board

    ok_count = 0
    for (net, A, B) in GAPS:
        ok = (g.retry_edge(net, A, B, width_mm=0.25, clearance_mm=0.2,
                           grid_mm=0.1, max_expansions=300000)
              or g.retry_edge(net, A, B, width_mm=0.25, clearance_mm=0.13,
                              grid_mm=0.1, max_expansions=400000)
              or g.retry_edge(net, A, B, width_mm=0.2, clearance_mm=0.13,
                              grid_mm=0.05, max_expansions=500000))
        print(f"  {net} {A}->{B}: {'OK' if ok else 'FAILED'}")
        if ok:
            ok_count += 1

    # chain the stray GND vias together pairwise (nearest-neighbor order
    # already given), using retry_edge so it routes around obstacles
    chain_ok = 0
    for i in range(len(STRAY_VIA_CHAIN) - 1):
        A, B = STRAY_VIA_CHAIN[i], STRAY_VIA_CHAIN[i + 1]
        d = math.hypot(A[0] - B[0], A[1] - B[1])
        ok = g.retry_edge("GND", A, B, width_mm=0.25, clearance_mm=0.15,
                          grid_mm=0.05, max_expansions=200000)
        print(f"  GND-stitch {A}->{B} (d={d:.2f}mm): {'OK' if ok else 'FAILED'}")
        if ok:
            chain_ok += 1

    print(f"routed {ok_count}/{len(GAPS)} gaps, {chain_ok}/{len(STRAY_VIA_CHAIN)-1} stray-via links")
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
