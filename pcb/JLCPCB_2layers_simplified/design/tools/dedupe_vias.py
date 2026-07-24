"""Rev 8 cleanup (2026-07-21): heal_all.py's repeated GND-fragment healing
rounds kept adding a "new" stitching via near the same spot instead of
reliably detecting the one already there (its duplicate-via guard used a
0.2-0.3mm radius check that clearly wasn't catching everything across
rounds) -- left 521 total vias on the board, 407 pairs of which physically
overlap (GND alone has 364 vias, most stacked in tight clusters). This
collapses each same-net cluster of near-coincident vias down to one, then
nudges apart any pairs that are still touching after dedup.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")

CLUSTER_RADIUS_MM = 0.65   # >= via diameter: vias this close are "the same via"


def main():
    board = pcbnew.LoadBoard(BOARD)
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    print(f"total vias before: {len(vias)}")

    by_net = {}
    for v in vias:
        by_net.setdefault(v.GetNet().GetNetname(), []).append(v)

    removed = 0
    kept_positions = []  # (x_mm, y_mm, net) for the post-dedup nudge pass
    for net, vs in by_net.items():
        # simple greedy clustering: for each via, if it's within radius of an
        # already-kept via on this net, drop it; else keep it.
        kept = []
        for v in vs:
            p = v.GetPosition()
            x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
            dup = any(math.hypot(x - kx, y - ky) < CLUSTER_RADIUS_MM for (kx, ky) in kept)
            if dup:
                board.Remove(v)
                removed += 1
            else:
                kept.append((x, y))
                kept_positions.append((x, y, net))

    print(f"removed {removed} duplicate/near-coincident vias")
    print(f"remaining vias: {len(kept_positions)}")

    # second pass: any still-touching pairs among the survivors (different
    # nets, or same-net pairs just outside the cluster radius but still
    # overlapping) get nudged apart along their connecting line.
    nudged = 0
    vias2 = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    for i in range(len(vias2)):
        for j in range(i + 1, len(vias2)):
            v1, v2 = vias2[i], vias2[j]
            p1, p2 = v1.GetPosition(), v2.GetPosition()
            x1, y1 = pcbnew.ToMM(p1.x), pcbnew.ToMM(p1.y)
            x2, y2 = pcbnew.ToMM(p2.x), pcbnew.ToMM(p2.y)
            d1 = pcbnew.ToMM(v1.GetWidth(pcbnew.F_Cu))
            d2 = pcbnew.ToMM(v2.GetWidth(pcbnew.F_Cu))
            dist = math.hypot(x1 - x2, y1 - y2)
            need = (d1 + d2) / 2 + 0.2  # + clearance
            if dist < need and dist > 1e-6:
                push = (need - dist) / 2 + 0.05
                ux, uy = (x1 - x2) / dist, (y1 - y2) / dist
                v1.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x1 + ux * push),
                                               pcbnew.FromMM(y1 + uy * push)))
                v2.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x2 - ux * push),
                                               pcbnew.FromMM(y2 - uy * push)))
                nudged += 1
            elif dist < 1e-6:
                # exactly coincident (different nets, extremely unlikely) --
                # nudge v2 by half the needed gap in an arbitrary direction
                v2.SetPosition(pcbnew.VECTOR2I(p2.x + pcbnew.FromMM(need), p2.y))
                nudged += 1
    print(f"nudged {nudged} still-touching pairs apart")

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
