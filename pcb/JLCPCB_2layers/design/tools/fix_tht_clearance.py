"""Rev 8 (2026-07-22): fixes the 26 spots flagged by the new THT-pad
hand-solder clearance rule (micromouse-pcb.kicad_dru, 0.2mm min vs. board's
base 0.127mm). All 26 fail by only 0.002-0.05mm -- nearly all are a track
leaving a *neighboring* pin of the same tight-pitch connector (J5/J6 @
1.5mm pitch) or an LED's own second-leg trace passing close to its other
pad. None need a full reroute: each gets a small perpendicular jog (insert
2 vertices bulging the track away from the offending pad) right at the
point of closest approach, leaving both original endpoints (and therefore
all existing connectivity) untouched.
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

# (net_name, layer, track_point_xy_mm, pad_ref, pad_num, pad_pos_xy_mm, actual_mm)
VIOLATIONS = [
    ("EMIT_FRONT_K", "B.Cu", (38.9273, 15.1183), "Q2", "1", (30.95, 16.27), 0.1517),
    ("USB_DM_C", "F.Cu", (65.3304, 113.8722), "J7", "SH", (65.68, 112.57), 0.1522),
    ("USB_DM_C", "F.Cu", (63.8301, 112.3719), "J7", "SH", (65.68, 112.57), 0.1791),
    ("BUZZ_CTRL", "F.Cu", (67.7685, 75.2073), "J6", "1", (67.0, 70.0), 0.1535),
    ("WALL_EMIT_SIDE", "B.Cu", (67.7716, 69.1808), "J6", "1", (67.0, 70.0), 0.1526),
    ("WALL_EMIT_SIDE", "B.Cu", (67.7716, 75.9999), "J6", "1", (67.0, 70.0), 0.1566),
    ("Net-(D4-A)", "B.Cu", (83.0281, 27.038), "D4", "1", (81.232, 26.872), 0.1527),
    ("Net-(D4-A)", "B.Cu", (81.3156, 25.3255), "D4", "1", (81.232, 26.872), 0.1737),
    ("ENC2_B", "B.Cu", (59.4283, 68.8833), "J6", "6", (59.5, 70.0), 0.1550),
    ("ENC2_B", "B.Cu", (62.5, 68.8833), "J6", "5", (61.0, 70.0), 0.1517),
    ("ENC2_A", "F.Cu", (63.5263, 69.0394), "J6", "4", (62.5, 70.0), 0.1781),
    ("ENC2_A", "F.Cu", (63.0062, 69.0394), "J6", "4", (62.5, 70.0), 0.1781),
    ("EMIT_SIDE_K", "B.Cu", (86.1517, 45.9792), "D6", "2", (85.0, 45.47), 0.1744),
    ("EMIT_SIDE_K", "B.Cu", (86.1517, 44.9454), "D6", "2", (85.0, 45.47), 0.1517),
    ("EMIT_SIDE_K", "B.Cu", (85.5025, 46.6284), "D6", "2", (85.0, 45.47), 0.1584),
    ("EMIT_SIDE_K", "B.Cu", (85.288, 44.0817), "D6", "2", (85.0, 45.47), 0.1853),
    ("IMU_SCL", "F.Cu", (58.565, 70.5503), "J6", "6", (59.5, 70.0), 0.1878),
    ("Net-(D1-A)", "B.Cu", (20.2067, 17.2647), "D1", "1", (21.43, 16.27), 0.1956),
    ("EMIT_FRONT_K", "B.Cu", (76.2666, 15.1183), "Q3", "1", (69.05, 16.27), 0.1517),
    ("ENC1_B", "B.Cu", (39.5287, 70.2167), "J5", "5", (39.0, 69.1), 0.1517),
    ("ENC1_B", "F.Cu", (37.4606, 70.2561), "J5", "1", (33.0, 69.1), 0.1911),
    ("PLUS3V3", "B.Cu", (50.3687, 106.2988), "U3", "41", (52.2, 105.64), 0.1588),
    ("PLUS3V3", "B.Cu", (52.4729, 106.2988), "U3", "41", (52.9, 104.94), 0.1588),
    ("PLUS3V3", "B.Cu", (65.5, 71.2167), "J6", "5", (61.0, 70.0), 0.1517),
    ("MOTA_P", "B.Cu", (33.0, 69.1), "J5", "2", (34.5, 69.1), 0.1982),
    ("MOTA_P", "B.Cu", (34.1479, 67.9521), "J5", "5", (39.0, 69.1), 0.1829),
]

TARGET = 0.2
MARGIN = 0.04  # extra beyond target so we clear DRC's own rounding
JOG_HALF_LEN = 0.25  # mm of track on each side of the jog point that gets angled


def layer_id(name):
    return pcbnew.F_Cu if name == "F.Cu" else pcbnew.B_Cu


def find_pad(board, ref, num):
    for fp in board.GetFootprints():
        if fp.GetReference() != ref:
            continue
        for pad in fp.Pads():
            if pad.GetNumber() == num:
                return pad
    return None


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


def fix_one(board, net_name, layer_name, track_pt, pad_ref, pad_num, pad_pt, actual_mm):
    track, dist = find_track(board, net_name, layer_name, track_pt)
    if track is None:
        print(f"  SKIP: no track found for {net_name}/{layer_name} near {track_pt}")
        return False
    if dist > 0.5:
        print(f"  WARN: best match for {net_name}/{layer_name} near {track_pt} is {dist:.3f}mm away -- skipping")
        return False

    s, e = track.GetStart(), track.GetEnd()
    sx, sy = TOMM(s.x), TOMM(s.y)
    ex, ey = TOMM(e.x), TOMM(e.y)
    px, py = track_pt
    tt = seg_closest_param(px, py, sx, sy, ex, ey)
    cx, cy = sx + tt * (ex - sx), sy + tt * (ey - sy)

    padx, pady = pad_pt
    away_x, away_y = cx - padx, cy - pady
    norm = math.hypot(away_x, away_y)
    if norm < 1e-6:
        print(f"  SKIP: closest point coincides with pad center for {net_name} near {pad_ref}.{pad_num}")
        return False
    away_x, away_y = away_x / norm, away_y / norm

    needed = max(TARGET - actual_mm + MARGIN, 0.05)

    # direction along the track at the closest point
    dlen = math.hypot(ex - sx, ey - sy)
    if dlen < 1e-6:
        print(f"  SKIP: degenerate track for {net_name}")
        return False
    along_x, along_y = (ex - sx) / dlen, (ey - sy) / dlen

    # clamp jog half-length so we don't run past the segment's own endpoints
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
    print(f"  fixed {net_name}/{layer_name} near {pad_ref}.{pad_num}: jog {needed:.3f}mm away")
    return True


def main():
    board = pcbnew.LoadBoard(BOARD)
    fixed = 0
    for (net_name, layer_name, track_pt, pad_ref, pad_num, pad_pt, actual_mm) in VIOLATIONS:
        if fix_one(board, net_name, layer_name, track_pt, pad_ref, pad_num, pad_pt, actual_mm):
            fixed += 1
    print(f"fixed {fixed}/{len(VIOLATIONS)}")

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
