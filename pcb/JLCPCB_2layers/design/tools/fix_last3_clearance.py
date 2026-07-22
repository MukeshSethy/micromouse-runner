"""Fix the last 3 pre-existing clearance violations (predate today's THT
work). All 3 are the same shape: a DIFFERENT-net track passing close to a
via, on a not-crowded part of the board -- safe to jog just that track
(not the via, which could be mid-junction) away by a small amount, same
technique validated on the LED fixes earlier today. One at a time, no
batch/cascading logic this time.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")

MM = pcbnew.FromMM
TOMM = pcbnew.ToMM

# (via_net, via_pos_mm, track_net, track_layer, track_point_mm, actual_mm)
TARGETS = [
    ("MOT_EN", (65.065549, 56.237464), "WALL_EMIT_FRONT", "B.Cu", (57.2701, 49.1524), 0.1023),
    ("IMU_SCL", (53.67142, 60.739973), "Net-(U8-~{RESET})", "B.Cu", (53.1483, 61.0484), 0.1231),
    ("GND", (47.934, 62.9), "ESP_EN", "B.Cu", (39.1484, 63.3269), 0.0269),
]

TARGET_CLEARANCE = 0.15
MARGIN = 0.04
JOG_HALF_LEN = 0.25


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
        if t.GetClass() != "PCB_TRACK":
            continue
        if t.GetLayer() != layer:
            continue
        if t.GetNet().GetNetname() != net_name:
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


def fix_one(board, via_pos, net_name, layer_name, track_pt, actual_mm):
    track, dist = find_track(board, net_name, layer_name, track_pt)
    if track is None or dist > 0.5:
        print(f"  SKIP: no track match for {net_name}/{layer_name} near {track_pt} (best dist {dist:.3f})")
        return False

    s, e = track.GetStart(), track.GetEnd()
    sx, sy = TOMM(s.x), TOMM(s.y)
    ex, ey = TOMM(e.x), TOMM(e.y)
    px, py = track_pt
    tt = seg_closest_param(px, py, sx, sy, ex, ey)
    cx, cy = sx + tt * (ex - sx), sy + tt * (ey - sy)

    vx, vy = via_pos
    away_x, away_y = cx - vx, cy - vy
    norm = math.hypot(away_x, away_y)
    if norm < 1e-6:
        print(f"  SKIP: closest point coincides with via center for {net_name}")
        return False
    away_x, away_y = away_x / norm, away_y / norm

    needed = max(TARGET_CLEARANCE - actual_mm + MARGIN, 0.05)

    dlen = math.hypot(ex - sx, ey - sy)
    if dlen < 1e-6:
        print(f"  SKIP: degenerate track for {net_name}")
        return False
    along_x, along_y = (ex - sx) / dlen, (ey - sy) / dlen

    half_len = min(JOG_HALF_LEN, tt * dlen * 0.9, (1 - tt) * dlen * 0.9)
    if half_len < 0.02:
        half_len = min(JOG_HALF_LEN, dlen * 0.45)

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
    print(f"  fixed {net_name}/{layer_name} near via {via_pos}: jog {needed:.3f}mm away")
    return True


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    board = pcbnew.LoadBoard(BOARD)
    (via_net, via_pos, track_net, track_layer, track_pt, actual_mm) = TARGETS[idx]
    fix_one(board, via_pos, track_net, track_layer, track_pt, actual_mm)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
