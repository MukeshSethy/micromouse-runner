"""Connect each fragmented GND pour region to the MAIN pour on the OPPOSITE
layer. A via placed at a point that is inside fragment F_i (on F.Cu) AND inside
the main pour (on B.Cu) ties F_i to the main net when the zones re-fill. This is
the correct 2-layer stitch (vs a blind grid, which drops vias in spots the main
pour never reaches -> new isolated points).

One pass here (using the current fill), save WITHOUT re-filling; fill + ratsnest
is a separate crash-isolated process. Re-run to chain fragments that only reach
the opposite main after an earlier via merged them.
"""
import sys, os
sys.path.insert(0, r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\tools")
import pcbnew, heal_all

g = heal_all.load()
g.fill_zones()
board = g.board
gz = [z for z in board.Zones() if z.GetNetname() == "GND"]


def polys(layer):
    out = []
    for z in gz:
        if not z.IsOnLayer(layer):
            continue
        pl = z.GetFilledPolysList(layer)
        for i in range(pl.OutlineCount()):
            out.append(pl.Outline(i))
    return out


def main_of(chains):
    return max(chains, key=lambda c: abs(c.Area())) if chains else None


F = polys(pcbnew.F_Cu)
B = polys(pcbnew.B_Cu)
Fmain, Bmain = main_of(F), main_of(B)
added = 0


def try_connect(frags, main_other, layer_other):
    global added
    n = 0
    for ch in frags:
        if ch is (Fmain if layer_other == pcbnew.B_Cu else Bmain):
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
                # point inside THIS fragment and inside the OTHER layer's main pour
                if ch.PointInside(pv, 0, True) and main_other.PointInside(pv, 0, True):
                    if not any(vn == "GND" and abs(vx - p[0]) < 1.0 and abs(vy - p[1]) < 1.0
                               for (vx, vy, vn, vr) in g._vias):
                        if g._verify_geo([], [p], "GND", 0.2) is None:
                            g.add_via(p, "GND")
                            g._vias.append((p[0], p[1], "GND", 0.3))
                            added += 1
                            n += 1
                            placed = True
                yi += 0.5
            xi += 0.5
    return n


nf = try_connect(F, Bmain, pcbnew.B_Cu)   # F fragments -> B main
nb = try_connect(B, Fmain, pcbnew.F_Cu)   # B fragments -> F main
pcbnew.SaveBoard(heal_all.BOARD, g.board)
sys.stdout.write("smart stitch: %d vias (F-frag->Bmain %d, B-frag->Fmain %d)\n" % (added, nf, nb))
sys.stdout.flush()
os._exit(0)
