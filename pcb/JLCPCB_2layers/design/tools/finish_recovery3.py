"""Recovery step 5: close out the last few items.
  - ESP_EN: F.Cu and B.Cu track ends meet at the same XY (70.5,102.0) with
    no via joining the layers -- drop one.
  - GND stray-via chain: one via (66.612,102.588) still isn't joined to
    the track end at (66.935,101.409) -- direct short link.
  - WALL_EMIT_SIDE: retry_edge partially routed; the remaining gap moved
    to a via at (63.2251,68.4683) -> track end (60.1665,80.3831).
  - U8's local GND fragment (pad2/pad25 <-> main GND zone) and the
    RESET/PLUS3V3 cluster near U8: these match the *pre-existing*,
    already-known-pending gaps from before today's session (see
    PROJECT memory: "2 track segments ... removed earlier but never
    rerouted"), not something introduced by today's recovery -- still
    worth one more routing attempt while in here.
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


def main():
    g = load()
    board = g.board

    # ESP_EN: add the missing via at the shared XY
    v = pcbnew.PCB_VIA(board)
    p = pcbnew.VECTOR2I(pcbnew.FromMM(70.5), pcbnew.FromMM(102.0))
    v.SetPosition(p)
    v.SetDrill(pcbnew.FromMM(0.3))
    v.SetWidth(pcbnew.FromMM(0.6))
    v.SetNetCode(g._nets["ESP_EN"].GetNetCode())
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(v)
    print("added ESP_EN via at (70.5, 102.0)")

    GAPS = [
        ("GND", (66.611999, 102.588), (66.934999, 101.409)),
        ("WALL_EMIT_SIDE", (63.2251, 68.4683), (60.1665, 80.3831)),
        ("GND", (47.6875, 58.25), (49.75, 57.4375)),
        ("PLUS3V3", (43.05, 59.5), (47.6875, 58.75)),
        ("PLUS3V3", (50.6905, 61.8964), (48.7217, 58.7254)),
        ("Net-(U8-~{RESET})", (53.1483, 61.0484), (54.3408, 59.3505)),
    ]
    ok_count = 0
    for (net, A, B) in GAPS:
        ok = (g.retry_edge(net, A, B, width_mm=0.25, clearance_mm=0.15,
                           grid_mm=0.1, max_expansions=300000)
              or g.retry_edge(net, A, B, width_mm=0.2, clearance_mm=0.13,
                              grid_mm=0.05, max_expansions=600000)
              or g.retry_edge(net, A, B, width_mm=0.15, clearance_mm=0.13,
                              grid_mm=0.05, max_expansions=800000))
        print(f"  {net} {A}->{B}: {'OK' if ok else 'FAILED'}")
        if ok:
            ok_count += 1

    print(f"routed {ok_count}/{len(GAPS)} gaps")
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
