"""Restore ESP_EN's pre-existing R11<->C9<->U3-pad3 routing (mistakenly wiped
wholesale by the original switch-swap script, which assumed ESP_EN was a
simple 2-terminal net like USER_BTN2/3 -- it's actually 4-terminal, with a
long-distance chunk that has nothing to do with the switch), then adds the
one genuinely-new short edge: U3 pad3 -> SW4 pad1.
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

# (start_mm, end_mm, layer_name, width_mm) -- extracted from git HEAD's board
TRACKS = [
    ((49.6756, 62.5481), (52.1039, 62.5481), "F.Cu", 0.2),
    ((69.7295, 64.8591), (69.7295, 101.2295), "F.Cu", 0.2),
    ((58.75, 109.42), (59.7517, 109.42), "F.Cu", 0.2),
    ((34.9125, 60.0), (39.05, 60.0), "F.Cu", 0.2),
    ((39.1484, 60.0984), (39.1484, 63.3269), "F.Cu", 0.2),
    ((62.0602, 107.1115), (62.0602, 103.4121), "F.Cu", 0.2),
    ((39.05, 60.0), (39.1484, 60.0984), "F.Cu", 0.2),
    ((69.7295, 101.2295), (70.5, 102.0), "F.Cu", 0.2),
    ((59.7517, 109.42), (62.0602, 107.1115), "F.Cu", 0.2),
    ((68.8194, 63.949), (69.7295, 64.8591), "B.Cu", 0.2),
    ((70.5, 102.0), (64.0, 102.0), "B.Cu", 0.2),
    ((39.1484, 63.3269), (48.8968, 63.3269), "B.Cu", 0.2),
    ((52.1039, 62.5481), (53.5048, 63.949), "B.Cu", 0.2),
    ((48.8968, 63.3269), (49.6756, 62.5481), "B.Cu", 0.2),
    ((62.5879, 103.4121), (64.0, 102.0), "B.Cu", 0.2),
    ((53.5048, 63.949), (68.8194, 63.949), "B.Cu", 0.2),
    ((62.0602, 103.4121), (62.5879, 103.4121), "B.Cu", 0.2),
]
VIAS = [  # (pos_mm, diameter_mm, drill_mm)
    ((62.0602, 103.4121), 0.6, 0.3),
    ((69.7295, 64.8591), 0.6, 0.3),
    ((39.1484, 63.3269), 0.6, 0.3),
    ((49.6756, 62.5481), 0.6, 0.3),
    ((52.1039, 62.5481), 0.6, 0.3),
]

LAYER_MAP = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}


def mm2iu(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main():
    board = pcbnew.LoadBoard(BOARD)
    net = None
    for code, ni in board.GetNetsByNetcode().items():
        if ni.GetNetname() == "ESP_EN":
            net = ni
            break
    assert net is not None

    cleared = 0
    for t in list(board.GetTracks()):
        if t.GetNet().GetNetname() == "ESP_EN":
            board.Remove(t)
            cleared += 1
    print(f"cleared {cleared} existing ESP_EN items before restoring")

    for (a, b, layer, width) in TRACKS:
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(mm2iu(*a))
        tr.SetEnd(mm2iu(*b))
        tr.SetLayer(LAYER_MAP[layer])
        tr.SetWidth(pcbnew.FromMM(width))
        tr.SetNet(net)
        board.Add(tr)
    for (pos, dia, drill) in VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(mm2iu(*pos))
        v.SetWidth(pcbnew.FromMM(dia))
        v.SetDrill(pcbnew.FromMM(drill))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(net)
        board.Add(v)
    print(f"restored {len(TRACKS)} tracks + {len(VIAS)} vias on ESP_EN")
    pcbnew.SaveBoard(BOARD, board)

    # now the one genuinely-new edge: U3 pad3 -> SW4 pad1
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
        tnet = t.GetNet().GetNetname()
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            g._vias.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), tnet,
                            pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        elif t.GetClass() == "PCB_TRACK":
            a, b = t.GetStart(), t.GetEnd()
            g._track_segs.append(((pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)),
                                  (pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)), tnet,
                                  pcbnew.ToMM(t.GetWidth()) / 2, t.GetLayer()))
    g._unrouted = []

    ok = (g.retry_edge("ESP_EN", (58.75, 109.42), (65.2, 103.45), width_mm=0.25,
                        clearance_mm=0.18, grid_mm=0.15, max_expansions=100000)
          or g.retry_edge("ESP_EN", (58.75, 109.42), (65.2, 103.45), width_mm=0.2,
                           clearance_mm=0.15, grid_mm=0.1, max_expansions=200000))
    print("U3pad3 -> SW4:", "OK" if ok else "FAILED")
    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
