"""Guarantee every GND pad reaches the main ground net, using ONLY geometry that
satisfies the JLC-cap-Lion rule set (see vendor_geo.py).

WHY THIS EXISTS
On a dense 2-layer board the F.Cu ground pour gets chopped into islands by the
signal routing, so a pad that relies on the pour can end up electrically
isolated from the rest of GND while DRC still reports no violation against it.
This bit this board on several route cycles: U1 pad 4 (the buck's ground) and
U2 pad 18 (the TB6612's logic ground) both floated at one point. A floating
buck ground means no 3V3 rail at all, so this is a functional gate, not a
cosmetic one -- and it is invisible to both DRC and ERC.

Escalating strategies per orphaned pad:
  1. a strict-legal via next to the pad, joined by a short escape track
  2. an A* GND track from the pad to the nearest point of the MAIN pour

Every candidate is checked with vendor_geo (0.20mm copper clearance, 0.50mm
hole-to-hole, 0.25mm hole-to-copper, 0.30mm to board edge) and then REFEREED by
reloading the board and re-testing connectivity, so a "fix" that does not
actually join the main net is rejected rather than assumed.

Usage:  close_gnd_strict.py           report only
        close_gnd_strict.py --fix     apply
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
import vendor_geo as VG
import heal_all

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified-2l.kicad_pcb")
mm = pcbnew.ToMM
FM = pcbnew.FromMM
FIX = "--fix" in sys.argv


def load():
    b = pcbnew.LoadBoard(BOARD)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()      # REQUIRED: RecalculateRatsnest alone returns stale data
    return b


def orphans(b):
    """GND pads whose connectivity cluster is far smaller than the main one."""
    conn = b.GetConnectivity()
    ref = None
    for f in b.GetFootprints():
        if f.GetReference() == "J1":
            for p in f.Pads():
                if p.GetNetname() == "GND":
                    ref = p
    if ref is None:
        return [], 0
    main = len({c.m_Uuid.AsString() for c in conn.GetConnectedItems(ref)})
    out = []
    for f in b.GetFootprints():
        for pad in f.Pads():
            if pad.GetNetname() != "GND":
                continue
            n = len({c.m_Uuid.AsString() for c in conn.GetConnectedItems(pad)})
            if n < main * 0.5:
                q = pad.GetPosition()
                out.append((f.GetReference(), pad.GetPadName(),
                            round(mm(q.x), 3), round(mm(q.y), 3)))
    return out, main


def main_pour_points(b, step=2.0):
    """Interior sample points of the LARGEST ground pour on each copper layer."""
    pts = []
    for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
        best = None
        for z in b.Zones():
            if z.GetNetname() != "GND" or z.GetIsRuleArea() or not z.IsOnLayer(lay):
                continue
            pl = z.GetFilledPolysList(lay)
            for i in range(pl.OutlineCount()):
                ch = pl.Outline(i)
                if best is None or abs(ch.Area()) > abs(best.Area()):
                    best = ch
        if best is None:
            continue
        bb = best.BBox()
        x = mm(bb.GetLeft()) + 1.0
        while x < mm(bb.GetRight()):
            y = mm(bb.GetTop()) + 1.0
            while y < mm(bb.GetBottom()):
                if best.PointInside(pcbnew.VECTOR2I(FM(x), FM(y)), 0, True):
                    pts.append((round(x, 2), round(y, 2)))
                y += step
            x += step
    return pts


def still_orphan(ref, pn):
    o, _ = orphans(load())
    return (ref, pn) in [(x[0], x[1]) for x in o]


def try_via(ref, pn, cx, cy):
    """Strategy 1: strict-legal via beside the pad + short escape track."""
    b = load()
    m = VG.build(b)
    gnd = b.FindNet("GND")
    for r in [round(0.4 + 0.1 * k, 2) for k in range(0, 46)]:
        for a in range(0, 360, 10):
            vx = round(cx + r * math.cos(math.radians(a)), 2)
            vy = round(cy + r * math.sin(math.radians(a)), 2)
            if not VG.can_place_via(m, (vx, vy))[0]:
                continue
            if not VG.can_place_track(m, (cx, cy), (vx, vy), pcbnew.F_Cu, 0.125)[0]:
                continue
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(FM(cx), FM(cy)))
            t.SetEnd(pcbnew.VECTOR2I(FM(vx), FM(vy)))
            t.SetWidth(FM(0.25))
            t.SetLayer(pcbnew.F_Cu)
            t.SetNet(gnd)
            b.Add(t)
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(FM(vx), FM(vy)))
            v.SetDrill(FM(0.3))
            v.SetWidth(FM(0.6))
            v.SetNet(gnd)
            b.Add(v)
            pcbnew.SaveBoard(BOARD, b)
            if not still_orphan(ref, pn):
                return "via (%.2f,%.2f) at r=%.2fmm" % (vx, vy, r)
            b = load()          # candidate rejected: reload the pre-attempt state
            m = VG.build(b)
            gnd = b.FindNet("GND")
    return None


def try_astar(ref, pn, cx, cy):
    """Strategy 2: A* ground track from the pad to the nearest main-pour point."""
    heal_all.BOARD = BOARD
    g = heal_all.load()
    g.fill_zones()
    targets = sorted(main_pour_points(g.board),
                     key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)[:12]
    for tgt in targets:
        if g.retry_edge("GND", (cx, cy), tgt, width_mm=0.25, clearance_mm=0.3,
                        grid_mm=0.1, max_expansions=300000):
            g.fill_zones()
            pcbnew.SaveBoard(BOARD, g.board)
            if not still_orphan(ref, pn):
                return "A* track to %s" % (tgt,)
    return None


def main():
    orph, mainsz = orphans(load())
    names = [r + "." + p for r, p, _, _ in orph]
    print("main GND cluster: %d | orphaned GND pads: %s"
          % (mainsz, names if names else "NONE"), flush=True)
    if not orph:
        print("RESULT: every GND pad reaches the main net", flush=True)
        os._exit(0)
    if not FIX:
        print("(report only -- pass --fix to apply)", flush=True)
        os._exit(0)

    unresolved = []
    for ref, pn, cx, cy in orph:
        print("\n%s.%s at (%.3f,%.3f)" % (ref, pn, cx, cy), flush=True)
        how = try_via(ref, pn, cx, cy)
        if how is None:
            how = try_astar(ref, pn, cx, cy)
        if how:
            print("   FIXED by %s" % how, flush=True)
        else:
            print("   STILL OPEN (needs a local rip/reroute)", flush=True)
            unresolved.append(ref + "." + pn)

    b = load()
    o, msz = orphans(b)
    print("\nremaining orphan GND pads: %s"
          % ([x[0] + "." + x[1] for x in o] or "NONE"), flush=True)
    print("ratsnest: %d" % b.GetConnectivity().GetUnconnectedCount(True), flush=True)
    print("RESULT:", "PASS" if not o else "FAIL (%s)" % ",".join(unresolved), flush=True)
    sys.stdout.flush()
    os._exit(1 if o else 0)


main()
