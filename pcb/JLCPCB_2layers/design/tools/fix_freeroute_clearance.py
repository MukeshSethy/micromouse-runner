"""Fix the LED-clearance and board-edge-clearance spots left over from the
Freerouting full-board reroute. Same small-perpendicular-jog technique
validated earlier today; run one target at a time via sys.argv index so a
mismatch on one doesn't affect the others.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(BASE), "micromouse-pcb-test", "micromouse-pcb.kicad_pcb")

MM = pcbnew.FromMM
TOMM = pcbnew.ToMM

# (net, layer, track_point, pad_or_edge_ref_pos, actual_mm, target_mm)
LED_TARGETS = [
    ("Net-(D4-A)", "B.Cu", (82.7994, 28.4394), (81.232, 26.872), 0.1946, 0.2),
    ("EMIT_SIDE_K", "B.Cu", (86.1952, 45.9287), (85.0, 45.47), 0.1695, 0.2),
    ("EMIT_SIDE_K", "B.Cu", (86.1952, 44.989), (85.0, 45.47), 0.1952, 0.2),
    ("EMIT_SIDE_K", "B.Cu", (85.2879, 44.0817), (85.0, 45.47), 0.1853, 0.2),
    ("EMIT_SIDE_K", "B.Cu", (85.4607, 46.6632), (85.0, 45.47), 0.1932, 0.2),
    ("WALL3_SENSE", "F.Cu", (12.4164, 25.7412), (16.972, 28.668), 0.1517, 0.2),
    ("Net-(D1-A)", "B.Cu", (20.2783, 17.3386), (21.43, 16.27), 0.1517, 0.2),
    ("Net-(D1-A)", "B.Cu", (26.9314, 23.9917), (21.43, 16.27), 0.1972, 0.2),
    ("EMIT_FRONT_K", "B.Cu", (39.6859, 12.5359), (78.57, 13.73), 0.1941, 0.2),
    ("EMIT_FRONT_K", "B.Cu", (79.7701, 14.2061), (78.57, 13.73), 0.1853, 0.2),
]

EDGE_TARGETS = [
    ("BATT_RAW", "F.Cu", (90.1095, 64.5), (87.0, 68.0), 0.1761, 0.2),
    ("PWR_EN", "F.Cu", (13.2784, 107.4399), (0.0, 100.0), 0.1784, 0.2),
]


def layer_id(name):
    return pcbnew.F_Cu if name == "F.Cu" else pcbnew.B_Cu


def seg_closest_param(px, py, sx, sy, ex, ey):
    dx, dy = ex - sx, ey - sy
    length2 = dx * dx + dy * dy
    if length2 < 1e-9:
        return 0.0
    t = ((px - sx) * dx + (py - sy) * dy) / length2
    return max(0.0, min(1.0, t))


def find_track(board, net_name, layer_name, pt):
    layer = layer_id(layer_name)
    px, py = pt
    best, bestd = None, 1e9
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != layer or t.GetNet().GetNetname() != net_name:
            continue
        s, e = t.GetStart(), t.GetEnd()
        sx, sy = TOMM(s.x), TOMM(s.y)
        ex, ey = TOMM(e.x), TOMM(e.y)
        tt = seg_closest_param(px, py, sx, sy, ex, ey)
        cx, cy = sx + tt * (ex - sx), sy + tt * (ey - sy)
        d = math.hypot(px - cx, py - cy)
        if d < bestd:
            bestd, best = d, t
    return best, bestd


def fix_one(board, net_name, layer_name, track_pt, away_from, actual_mm, target_mm):
    track, dist = find_track(board, net_name, layer_name, track_pt)
    if track is None or dist > 0.5:
        print(f"  SKIP: no match for {net_name}/{layer_name} near {track_pt} (best {dist:.3f})")
        return False

    s, e = track.GetStart(), track.GetEnd()
    sx, sy = TOMM(s.x), TOMM(s.y)
    ex, ey = TOMM(e.x), TOMM(e.y)
    px, py = track_pt
    tt = seg_closest_param(px, py, sx, sy, ex, ey)
    cx, cy = sx + tt * (ex - sx), sy + tt * (ey - sy)

    awx, awy = away_from
    away_x, away_y = cx - awx, cy - awy
    norm = math.hypot(away_x, away_y)
    if norm < 1e-6:
        print(f"  SKIP: coincident closest point for {net_name}")
        return False
    away_x, away_y = away_x / norm, away_y / norm

    needed = max(target_mm - actual_mm + 0.04, 0.05)

    dlen = math.hypot(ex - sx, ey - sy)
    if dlen < 1e-6:
        return False
    along_x, along_y = (ex - sx) / dlen, (ey - sy) / dlen
    half_len = min(0.25, tt * dlen * 0.9, (1 - tt) * dlen * 0.9)
    if half_len < 0.02:
        half_len = min(0.25, dlen * 0.3)

    p1x, p1y = cx - along_x * half_len + away_x * needed, cy - along_y * half_len + away_y * needed
    p2x, p2y = cx + along_x * half_len + away_x * needed, cy + along_y * half_len + away_y * needed

    width = track.GetWidth()
    layer = track.GetLayer()
    netcode = track.GetNetCode()

    seg1 = pcbnew.PCB_TRACK(board)
    seg1.SetStart(pcbnew.VECTOR2I(s.x, s.y))
    seg1.SetEnd(pcbnew.VECTOR2I(MM(p1x), MM(p1y)))
    seg1.SetWidth(width)
    seg1.SetLayer(layer)
    seg1.SetNetCode(netcode)

    seg2 = pcbnew.PCB_TRACK(board)
    seg2.SetStart(pcbnew.VECTOR2I(MM(p1x), MM(p1y)))
    seg2.SetEnd(pcbnew.VECTOR2I(MM(p2x), MM(p2y)))
    seg2.SetWidth(width)
    seg2.SetLayer(layer)
    seg2.SetNetCode(netcode)

    seg3 = pcbnew.PCB_TRACK(board)
    seg3.SetStart(pcbnew.VECTOR2I(MM(p2x), MM(p2y)))
    seg3.SetEnd(pcbnew.VECTOR2I(e.x, e.y))
    seg3.SetWidth(width)
    seg3.SetLayer(layer)
    seg3.SetNetCode(netcode)

    board.Remove(track)
    board.Add(seg1)
    board.Add(seg2)
    board.Add(seg3)
    print(f"  fixed {net_name}/{layer_name} near {track_pt}: jog {needed:.3f}mm")
    return True


def main():
    board = pcbnew.LoadBoard(BOARD)
    ok_count = 0
    for (net, layer, pt, away, actual, target) in LED_TARGETS + EDGE_TARGETS:
        if fix_one(board, net, layer, pt, away, actual, target):
            ok_count += 1
    print(f"fixed {ok_count}/{len(LED_TARGETS) + len(EDGE_TARGETS)}")
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
