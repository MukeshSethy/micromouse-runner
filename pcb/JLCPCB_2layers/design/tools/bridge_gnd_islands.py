"""Bridge the remaining isolated GND zone fragments (both F.Cu and B.Cu)
into the main pour with stitching vias, using the same bridge_fragments
logic proven in heal_all.py earlier today. These fragments are non-critical
(the only pad-level case, U8 GND pads 2/25, is grounded elsewhere via pads
5/6/17/18) -- this is purely for extra certainty, not a required fix.
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


def bridge_fragments(g, net, zlayer, maxn=999):
    zone = None
    for z in g.board.Zones():
        if z.GetNetname() == net and z.GetLayer() == zlayer:
            zone = z
    if zone is None:
        return 0
    poly = zone.GetFilledPolysList(zlayer)
    if poly.OutlineCount() <= 1:
        return 0
    areas = [(abs(poly.Outline(i).Area()), i) for i in range(poly.OutlineCount())]
    main = max(areas)[1]
    n = 0
    for (_, fi) in sorted(areas):
        if fi == main:
            continue
        if n >= maxn:
            break
        chain = poly.Outline(fi)
        done = False
        for (a, b, tn, hw, L) in list(g._track_segs):
            if tn != net or L not in (pcbnew.F_Cu, pcbnew.B_Cu) or done:
                continue
            ln = math.hypot(b[0] - a[0], b[1] - a[1])
            for s in range(int(ln / 0.4) + 2):
                t_ = min(1.0, s * 0.4 / ln) if ln else 0
                p = (round(a[0] + (b[0] - a[0]) * t_, 3),
                     round(a[1] + (b[1] - a[1]) * t_, 3))
                pv = pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))
                if not chain.PointInside(pv, 0, True):
                    continue
                if any(vn == net and abs(vx - p[0]) < 0.2 and abs(vy - p[1]) < 0.2
                       for (vx, vy, vn, vr) in g._vias):
                    continue
                if g._verify_geo([], [p], net, 0.125) is None:
                    g.add_via(p, net)
                    print(f"  fragment({net}/{fi}) bridge via @ {p}")
                    done = True
                    n += 1
                    break
        if not done:
            bb = chain.BBox()
            cx = (pcbnew.ToMM(bb.GetLeft()) + pcbnew.ToMM(bb.GetRight())) / 2
            cy = (pcbnew.ToMM(bb.GetTop()) + pcbnew.ToMM(bb.GetBottom())) / 2
            best = None
            for pad in g._pads_geo():
                if pad["net"] != net:
                    continue
                dd = math.hypot(pad["cx"] - cx, pad["cy"] - cy)
                if dd > 0.5 and (best is None or dd < best[0]):
                    best = (dd, (pad["cx"], pad["cy"]))
            placed = None
            for ddx in (0.0, 0.6, -0.6, 1.2, -1.2):
                if placed:
                    break
                for ddy in (0.0, 0.6, -0.6, 1.2, -1.2):
                    v = (round(cx + ddx, 3), round(cy + ddy, 3))
                    pv2 = pcbnew.VECTOR2I(pcbnew.FromMM(v[0]), pcbnew.FromMM(v[1]))
                    if not chain.PointInside(pv2, 0, True):
                        continue
                    if any(vn == net and abs(vx - v[0]) < 0.3 and abs(vy - v[1]) < 0.3
                           for (vx, vy, vn, vr) in g._vias):
                        continue
                    if g._verify_geo([], [v], net, 0.125) is None:
                        g.add_via(v, net)
                        placed = v
                        break
            if placed and best and g.retry_edge(net, placed, best[1], width_mm=0.25,
                                                clearance_mm=0.18, grid_mm=0.1,
                                                max_expansions=300000):
                print(f"  fragment({net}/{fi}) island via {placed} -> routed to {best[1]}")
                done = True
                n += 1
            else:
                print(f"  fragment({net}/{fi}) NO bridge -- bbox "
                      f"({pcbnew.ToMM(bb.GetLeft()):.1f},{pcbnew.ToMM(bb.GetTop()):.1f})-"
                      f"({pcbnew.ToMM(bb.GetRight()):.1f},{pcbnew.ToMM(bb.GetBottom()):.1f})")
    return n


def main():
    g = load()
    n1 = bridge_fragments(g, "GND", pcbnew.F_Cu)
    n2 = bridge_fragments(g, "GND", pcbnew.B_Cu)
    print(f"bridged {n1} F.Cu fragments, {n2} B.Cu fragments")
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
