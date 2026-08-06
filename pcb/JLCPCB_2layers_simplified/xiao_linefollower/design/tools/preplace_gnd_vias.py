"""Pre-place a ground via beside every SMD ground pad BEFORE routing.

WHY
On this 2-layer board the B.Cu ground pour is essentially solid, but the F.Cu
pour gets chopped into islands by dense signal routing. Any SMD ground pad that
relies on the F.Cu pour can therefore end up electrically isolated -- DRC stays
clean, ERC stays clean, and the board is still broken. U1 pad 4 (buck ground)
and U2 pad 18 (TB6612 logic ground) both hit this, and patching it after routing
turned into a whack-a-mole because by then there is no legal room left for a via.

Doing it BEFORE the autorouter runs inverts the problem: on a stripped board
there is plenty of room, every via lands legally, and the autorouter then has to
route around them -- so no ground pad can be stranded by the routing.

THT ground pads are skipped: their own plated hole already reaches both layers.

Run on a stripped board, before convert_2layer.py dsn:
    preplace_gnd_vias.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
import vendor_geo as VG

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified-2l.kicad_pcb")
mm = pcbnew.ToMM
FM = pcbnew.FromMM


def main():
    b = pcbnew.LoadBoard(BOARD)
    ntracks = sum(1 for t in b.GetTracks())
    if ntracks:
        print("WARNING: board still has %d track items -- run this on a stripped board"
              % ntracks, flush=True)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    gnd = b.FindNet("GND")

    targets = []
    for f in b.GetFootprints():
        for pad in f.Pads():
            if pad.GetNetname() != "GND":
                continue
            if pad.GetDrillSize().x > 0:
                continue          # THT: its own hole already spans both layers
            q = pad.GetPosition()
            targets.append((f.GetReference(), pad.GetPadName(),
                            round(mm(q.x), 3), round(mm(q.y), 3)))
    print("SMD ground pads needing a via to the plane: %d" % len(targets), flush=True)

    placed = 0
    skipped = []
    m = VG.build(b)
    for ref, pn, cx, cy in targets:
        # already covered by a via within 1.2mm? then don't add another
        if any(t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
               and math.hypot(mm(t.GetPosition().x) - cx, mm(t.GetPosition().y) - cy) < 1.2
               for t in b.GetTracks()):
            continue
        done = False
        for r in [round(0.45 + 0.05 * k, 2) for k in range(0, 40)]:
            if done:
                break
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
                m = VG.build(b)        # subsequent vias must clear this one too
                placed += 1
                done = True
                print("   %s.%s -> via (%.2f,%.2f) at %.2fmm" % (ref, pn, vx, vy, r), flush=True)
                break
        if not done:
            skipped.append(ref + "." + pn)

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(BOARD, b)
    print("\nplaced %d ground vias; could not place: %s"
          % (placed, skipped if skipped else "none"), flush=True)
    sys.stdout.flush()
    os._exit(0)


main()
