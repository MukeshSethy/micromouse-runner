"""Undo fix_tht_clearance.py: that script's 26 perpendicular jogs (each
splitting one track into 3) turned out to push several traces into OTHER
nearby copper (vias, adjacent bends) in these already-crowded zones (J5/J6
motor connector fanout, D4/D6 LED legs), creating 11 new violations worse
than the ones being fixed. Reverting by finding each 3-segment jog chain
(a short <=0.6mm middle segment whose two endpoints each connect to
exactly one other track on the same net) and merging it back into a single
straight segment between the original two endpoints.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")

TOUCHED_NET_LAYERS = {
    ("EMIT_FRONT_K", "B.Cu"), ("USB_DM_C", "F.Cu"), ("BUZZ_CTRL", "F.Cu"),
    ("WALL_EMIT_SIDE", "B.Cu"), ("Net-(D4-A)", "B.Cu"), ("ENC2_B", "B.Cu"),
    ("ENC2_A", "F.Cu"), ("EMIT_SIDE_K", "B.Cu"), ("IMU_SCL", "F.Cu"),
    ("Net-(D1-A)", "B.Cu"), ("ENC1_B", "B.Cu"), ("ENC1_B", "F.Cu"),
    ("PLUS3V3", "B.Cu"), ("MOTA_P", "B.Cu"),
}


def layer_id(name):
    return pcbnew.F_Cu if name == "F.Cu" else pcbnew.B_Cu


def pt_key(v):
    return (v.x, v.y)


def main():
    board = pcbnew.LoadBoard(BOARD)
    all_tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]

    for (net_name, layer_name) in TOUCHED_NET_LAYERS:
        layer = layer_id(layer_name)
        group = [t for t in all_tracks if t.GetLayer() == layer and t.GetNet().GetNetname() == net_name]
        if not group:
            continue

        # build endpoint adjacency: point -> list of tracks touching it
        adj = {}
        for t in group:
            for p in (pt_key(t.GetStart()), pt_key(t.GetEnd())):
                adj.setdefault(p, []).append(t)

        merged_any = True
        while merged_any:
            merged_any = False
            adj = {}
            for t in group:
                for p in (pt_key(t.GetStart()), pt_key(t.GetEnd())):
                    adj.setdefault(p, []).append(t)

            for seg2 in list(group):
                length_mm = pcbnew.ToMM(seg2.GetLength()) if hasattr(seg2, "GetLength") else None
                s, e = seg2.GetStart(), seg2.GetEnd()
                length_mm = math.hypot(pcbnew.ToMM(e.x - s.x), pcbnew.ToMM(e.y - s.y))
                if length_mm > 0.65:
                    continue
                p1, p2 = pt_key(s), pt_key(e)
                at_p1 = [t for t in adj.get(p1, []) if t is not seg2]
                at_p2 = [t for t in adj.get(p2, []) if t is not seg2]
                if len(at_p1) != 1 or len(at_p2) != 1:
                    continue
                seg1, seg3 = at_p1[0], at_p2[0]
                if seg1 is seg3:
                    continue
                # the far endpoints of seg1/seg3 (not p1/p2) become the new segment's ends
                s1s, s1e = pt_key(seg1.GetStart()), pt_key(seg1.GetEnd())
                far1 = s1e if s1s == p1 else s1s
                s3s, s3e = pt_key(seg3.GetStart()), pt_key(seg3.GetEnd())
                far3 = s3e if s3s == p2 else s3s

                width = seg2.GetWidth()
                netcode = seg2.GetNetCode()
                new_track = pcbnew.PCB_TRACK(board)
                new_track.SetStart(pcbnew.VECTOR2I(far1[0], far1[1]))
                new_track.SetEnd(pcbnew.VECTOR2I(far3[0], far3[1]))
                new_track.SetWidth(width)
                new_track.SetLayer(layer)
                new_track.SetNetCode(netcode)

                board.Remove(seg1)
                board.Remove(seg2)
                board.Remove(seg3)
                board.Add(new_track)
                print(f"merged jog on {net_name}/{layer_name}: {far1} -> {far3}")

                group = [t for t in group if t not in (seg1, seg2, seg3)]
                group.append(new_track)
                merged_any = True
                break

    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
