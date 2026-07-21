"""Chained GND stitch: connect ANY F.Cu fragment to ANY B.Cu fragment they
overlap (not just to the main pour). Iterating + re-filling merges fragments
into progressively larger nets until everything reaches main. This closes the
multi-hop islands that single-hop smart_stitch leaves behind.

One via per (F-frag, B-frag) overlapping pair per round; re-fill; repeat until a
round adds nothing. Crash-isolated per round is not possible (needs the live g),
so we cap rounds and add incrementally (add_via is safe; only the final fill is
the risk -- do it, then save)."""
import sys, os
sys.path.insert(0, r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\tools")
import pcbnew, heal_all

g = heal_all.load()
board = g.board
gz = [z for z in board.Zones() if z.GetNetname() == "GND"]


def frags(layer):
    out = []
    for z in gz:
        if z.IsOnLayer(layer):
            pl = z.GetFilledPolysList(layer)
            for i in range(pl.OutlineCount()):
                out.append(pl.Outline(i))
    return out


total = 0
for rnd in range(8):
    g.fill_zones()
    F = frags(pcbnew.F_Cu)
    B = frags(pcbnew.B_Cu)
    if not F or not B:
        break
    Fmain = max(F, key=lambda c: abs(c.Area()))
    Bmain = max(B, key=lambda c: abs(c.Area()))
    added = 0
    # connect every non-main F fragment to whatever B fragment overlaps it
    for fc in F:
        if fc is Fmain:
            continue
        bb = fc.BBox()
        x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
        x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
        done = False
        xi = x0 + 0.4
        while xi < x1 - 0.4 and not done:
            yi = y0 + 0.4
            while yi < y1 - 0.4 and not done:
                p = (round(xi, 2), round(yi, 2))
                pv = pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))
                if fc.PointInside(pv, 0, True) and any(bc.PointInside(pv, 0, True) for bc in B):
                    if not any(vn == "GND" and abs(vx - p[0]) < 0.8 and abs(vy - p[1]) < 0.8
                               for (vx, vy, vn, vr) in g._vias):
                        if g._verify_geo([], [p], "GND", 0.2) is None:
                            g.add_via(p, "GND"); g._vias.append((p[0], p[1], "GND", 0.3))
                            added += 1; done = True
                yi += 0.4
            xi += 0.4
    total += added
    sys.stdout.write("round %d: +%d vias\n" % (rnd + 1, added)); sys.stdout.flush()
    if added == 0:
        break

g.fill_zones()
pcbnew.SaveBoard(heal_all.BOARD, g.board)
b2 = pcbnew.LoadBoard(heal_all.BOARD); b2.BuildConnectivity()
sys.stdout.write("chained stitch total %d vias -> ratsnest %d\n"
                 % (total, b2.GetConnectivity().GetUnconnectedCount(True)))
sys.stdout.flush()
os._exit(0)
