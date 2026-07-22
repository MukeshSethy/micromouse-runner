"""Second pass: fix the LED-clearance/via-clearance spots that persisted
after the first jog attempt, matching the offending segment by its exact
reported length (more reliable than closest-point search when several
short jog-chain pieces sit near the same pad)."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(BASE), "micromouse-pcb-test", "micromouse-pcb.kicad_pcb")

MM = pcbnew.FromMM
TOMM = pcbnew.ToMM

# (net, layer, exact_length_mm, away_from_point, actual_mm, target_mm)
TARGETS = [
    ("EMIT_SIDE_K", "B.Cu", 1.0387, (85.0, 45.47), 0.1695, 0.2),
    ("WALL3_SENSE", "F.Cu", 7.2536, (16.972, 28.668), 0.1517, 0.2),  # will re-derive length below
    ("EMIT_FRONT_K", "B.Cu", 39.4026, (78.57, 13.73), 0.1941, 0.2),
    ("Net-(D1-A)", "B.Cu", 2.4569, (21.43, 16.27), 0.1517, 0.2),
]

VIA_TARGET = ("Net-(D4-A)", "B.Cu", (80.7999, 28.9911), 0.1253, 0.15)  # via-to-track


def layer_id(name):
    return pcbnew.F_Cu if name == "F.Cu" else pcbnew.B_Cu


def find_by_length(board, net_name, layer_name, target_len, tol=0.01):
    layer = layer_id(layer_name)
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != layer or t.GetNet().GetNetname() != net_name:
            continue
        s, e = t.GetStart(), t.GetEnd()
        L = math.hypot(TOMM(e.x - s.x), TOMM(e.y - s.y))
        if abs(L - target_len) < tol:
            return t
    return None


def seg_closest_param(px, py, sx, sy, ex, ey):
    dx, dy = ex - sx, ey - sy
    length2 = dx * dx + dy * dy
    if length2 < 1e-9:
        return 0.0
    t = ((px - sx) * dx + (py - sy) * dy) / length2
    return max(0.0, min(1.0, t))


def jog_track(board, track, away_from, actual_mm, target_mm):
    s, e = track.GetStart(), track.GetEnd()
    sx, sy = TOMM(s.x), TOMM(s.y)
    ex, ey = TOMM(e.x), TOMM(e.y)
    awx, awy = away_from
    tt = seg_closest_param(awx, awy, sx, sy, ex, ey)
    cx, cy = sx + tt * (ex - sx), sy + tt * (ey - sy)

    away_x, away_y = cx - awx, cy - awy
    norm = math.hypot(away_x, away_y)
    if norm < 1e-6:
        print("  SKIP: coincident closest point")
        return False
    away_x, away_y = away_x / norm, away_y / norm

    needed = max(target_mm - actual_mm + 0.05, 0.06)
    dlen = math.hypot(ex - sx, ey - sy)
    along_x, along_y = (ex - sx) / dlen, (ey - sy) / dlen
    half_len = min(0.3, tt * dlen * 0.9, (1 - tt) * dlen * 0.9)
    if half_len < 0.02:
        half_len = min(0.3, dlen * 0.3)

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
    print(f"  jogged {needed:.3f}mm at t={tt:.3f}")
    return True


def main():
    board = pcbnew.LoadBoard(BOARD)
    ok_count = 0
    for (net, layer, length, away, actual, target) in TARGETS:
        t = find_by_length(board, net, layer, length)
        if t is None:
            print(f"  SKIP: no length match for {net}/{layer} len={length}")
            continue
        print(f"{net}/{layer} len={length}:")
        if jog_track(board, t, away, actual, target):
            ok_count += 1

    print(f"fixed {ok_count}/{len(TARGETS)}")
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
