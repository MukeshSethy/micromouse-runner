"""Overnight completion pass, step 2: widen clearance around THT solder pads
(the 12 hand-soldered wall-sensor LEDs/phototransistors, Q2-Q7/D1-D6) per user
request. gen_pcb.py's own verify_clr_tht default was bumped 0.3->0.5mm; this
script rips up and re-routes, with the new rule now in effect, the specific
small/local nets a pre-scan found sitting under 0.25mm (rect-distance) from a
THT pad on a DIFFERENT net.

Scope decision: only small, local, 2-4 pad nets are ripped up and redone here
(cheap, low-risk full re-route via route_net's own MST). PLUS3V3 (a 50+ pad
net) and the J5/J6 pin-field nets were in the same pre-scan but are left
alone -- fully re-routing PLUS3V3 unattended overnight risks a worse outcome
than the ~0.2mm gaps it currently has (already at this project's normal
0.15-0.2mm baseline, not egregiously tight).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from complete_routing import load, BOARD

TARGET_NETS = [
    "WALL_DL_SENSE", "WALL_DR_SENSE", "WALL_FL_SENSE", "WALL_SR_SENSE",
    "EMIT_DIAG_K", "EMIT_FRONT_K",
    "ENC2_A", "ENC1_B", "AIN2", "MOTA_P", "MOTB_P",
    "Net-(D1-A)", "Net-(D2-A)", "Net-(D3-A)", "Net-(D4-A)", "Net-(D5-A)", "Net-(D6-A)",
]


def main():
    g = load()
    board = g.board

    # Rip up every existing track/via belonging to these nets.
    removed_tracks = removed_vias = 0
    for t in list(board.GetTracks()):
        net = t.GetNet().GetNetname()
        if net in TARGET_NETS:
            if t.GetClass() == "PCB_VIA":
                removed_vias += 1
            else:
                removed_tracks += 1
            board.Remove(t)
    print(f"removed {removed_tracks} track segs, {removed_vias} vias across {len(TARGET_NETS)} nets")

    # Rebuild the router's in-memory track/via bookkeeping from what's left on
    # the board (everything EXCEPT the nets we just ripped up).
    g._track_segs, g._vias = [], []
    for t in board.GetTracks():
        net = t.GetNet().GetNetname()
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            g._vias.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), net,
                            pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            a, b = t.GetStart(), t.GetEnd()
            g._track_segs.append(((pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)),
                                  (pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)), net,
                                  pcbnew.ToMM(t.GetWidth()) / 2, t.GetLayer()))
    g._pads_geo_cache = None

    ok, fail = [], []
    for net in TARGET_NETS:
        g._unrouted = []
        result = g.route_net(net, width_mm=0.25, clearance_mm=0.2, max_expansions=300000)
        if result and not g._unrouted:
            ok.append(net)
            print(f"  OK {net}")
        else:
            # retry with a bigger budget for anything the first pass missed
            retry_list = list(g._unrouted)
            g._unrouted = []
            still_bad = []
            for (n, p1, p2, reason) in retry_list:
                if not g.retry_edge(n, p1, p2, width_mm=0.25, clearance_mm=0.18,
                                     max_expansions=600000):
                    if not g.retry_edge(n, p1, p2, width_mm=0.2, clearance_mm=0.15,
                                         grid_mm=0.15, max_expansions=800000):
                        still_bad.append((n, p1, p2, reason))
            if still_bad:
                fail.append((net, still_bad))
                print(f"  PARTIAL/FAIL {net}: {still_bad}")
            else:
                ok.append(net)
                print(f"  OK {net} (after retry)")

    print(f"\n{len(ok)}/{len(TARGET_NETS)} nets re-routed clean with wider THT clearance")
    if fail:
        print("still failing:", fail)

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
