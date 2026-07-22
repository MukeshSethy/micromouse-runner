"""Recovery step 7 (hopefully final): close out the last real gaps.
  - U8's local GND pad2/pad25 fragment, isolated from the main GND pour.
  - A tiny RESET F.Cu/B.Cu fragment left dangling after removing the via
    that used to bridge it (that via also shorted PLUS3V3 -- net win to
    remove it, but need a clean replacement bridge).
  - A stray GND via near (64.02, 62.15) disconnected from the main pour.
Leaves WALL_EMIT_SIDE and the original RESET(53.15,61.05)->(54.34,59.35)
gap alone -- both have failed every routing attempt across this whole
recovery and match/predate the known pre-existing hard spots in this
crowded U8/IMU area.
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


GAPS = [
    ("GND", (47.6875, 58.25), (49.75, 57.4375)),
    ("Net-(U8-~{RESET})", (53.948, 61.3433), (54.0798, 61.4751)),
]


def main():
    g = load()
    board = g.board

    ok_count = 0
    for (net, A, B) in GAPS:
        ok = (g.retry_edge(net, A, B, width_mm=0.25, clearance_mm=0.2,
                           grid_mm=0.1, max_expansions=300000)
              or g.retry_edge(net, A, B, width_mm=0.2, clearance_mm=0.15,
                              grid_mm=0.05, max_expansions=600000))
        print(f"  {net} {A}->{B}: {'OK' if ok else 'FAILED'}")
        if ok:
            ok_count += 1

    # stray GND via near (64.02, 62.15): find nearest same-net copper and
    # link with retry_edge (clearance-checked, unlike a blind via drop)
    stray = (64.019999, 62.15)
    best = None
    for pad in g._pads_geo():
        if pad["net"] != "GND":
            continue
        import math
        dd = math.hypot(pad["cx"] - stray[0], pad["cy"] - stray[1])
        if dd > 0.3 and (best is None or dd < best[0]):
            best = (dd, (pad["cx"], pad["cy"]))
    if best:
        ok3 = g.retry_edge("GND", stray, best[1], width_mm=0.25, clearance_mm=0.15,
                           grid_mm=0.05, max_expansions=300000)
        print(f"  GND stray-via {stray} -> nearest pad {best[1]} (d={best[0]:.2f}mm): {'OK' if ok3 else 'FAILED'}")

    print(f"routed {ok_count}/{len(GAPS)} gaps")
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
