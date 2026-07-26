"""Connect every fragmented GND pour region to the MAIN pour on the OPPOSITE
layer, spreading stitching vias across the board wherever a fragment and the
opposite layer's main pour actually overlap (not a blind grid, which drops
vias in spots the main pour never reaches). Adapted from the JLCPCB_2layers
reference project's gnd_smart_stitch.py -- same algorithm, xiao board paths.

Runs several passes (re-filling zones between each) since merging one
fragment can newly connect a second fragment that only touches the first.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from complete_routing import load, BOARD

g = load()
board = g.board


def polys(layer):
    out = []
    for z in board.Zones():
        if z.GetNetname() != "GND" or not z.IsOnLayer(layer):
            continue
        pl = z.GetFilledPolysList(layer)
        for i in range(pl.OutlineCount()):
            out.append(pl.Outline(i))
    return out


def main_of(chains):
    return max(chains, key=lambda c: abs(c.Area())) if chains else None


def try_connect(frags, main_other, layer_other, added_list):
    n = 0
    for ch in frags:
        if ch is main_other:
            continue
        bb = ch.BBox()
        x0, x1 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())
        y0, y1 = pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())
        placed = False
        xi = x0 + 0.6
        while xi < x1 - 0.6 and not placed:
            yi = y0 + 0.6
            while yi < y1 - 0.6 and not placed:
                p = (round(xi, 2), round(yi, 2))
                pv = pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))
                if ch.PointInside(pv, 0, True) and main_other.PointInside(pv, 0, True):
                    if not any(vn == "GND" and abs(vx - p[0]) < 1.0 and abs(vy - p[1]) < 1.0
                               for (vx, vy, vn, vr) in g._vias):
                        if g._verify_geo([], [p], "GND", 0.2) is None:
                            g.add_via(p, "GND")
                            g._vias.append((p[0], p[1], "GND", 0.3))
                            added_list.append(p)
                            n += 1
                            placed = True
                yi += 0.5
            xi += 0.5
    return n


total_added = []
for round_i in range(4):
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    F = polys(pcbnew.F_Cu)
    B = polys(pcbnew.B_Cu)
    Fmain, Bmain = main_of(F), main_of(B)
    if Fmain is None or Bmain is None:
        print(f"round {round_i}: no GND fill yet on one layer, stopping")
        break
    added_this_round = []
    nf = try_connect(F, Bmain, pcbnew.B_Cu, added_this_round)
    nb = try_connect(B, Fmain, pcbnew.F_Cu, added_this_round)
    total_added.extend(added_this_round)
    print(f"round {round_i}: F-frag->Bmain {nf}, B-frag->Fmain {nb}, "
          f"fragments now F={len(F)} B={len(B)}")
    if nf == 0 and nb == 0:
        break

filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
F = polys(pcbnew.F_Cu)
B = polys(pcbnew.B_Cu)
print(f"FINAL: {len(total_added)} stitching vias added, "
      f"F.Cu fragments={len(F)}, B.Cu fragments={len(B)}")
print("stitch via locations:", total_added)
pcbnew.SaveBoard(BOARD, board)
print("saved", BOARD)
