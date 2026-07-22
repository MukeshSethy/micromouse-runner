"""Recovery step 1/2: fix_tht_clearance.py's jogs + the undo script's
over-aggressive cascading merge left these 13 (net, layer) groups with
unreliable geometry -- some segments are now long straight "shortcuts"
that likely overlap other copper the original routing detoured around.
Rip up every track on just these groups (pads/vias/other nets/other
layers of the same net are untouched) so ripup_damaged_nets can be
followed by heal_damaged_nets.py (retry_edge) to rebuild them cleanly.
"""
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


def main():
    board = pcbnew.LoadBoard(BOARD)
    removed = 0
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_TRACK":
            continue
        net = t.GetNet().GetNetname()
        layer = t.GetLayer()
        for (n, l) in TOUCHED_NET_LAYERS:
            if net == n and layer == layer_id(l):
                board.Remove(t)
                removed += 1
                break
    print(f"removed {removed} tracks across {len(TOUCHED_NET_LAYERS)} net/layer groups")
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
