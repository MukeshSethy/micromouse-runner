"""Recovery step 6: fix two real regressions from finish_recovery3.py's
last-resort fallback tiers.
  1. The RESET gap only routed successfully at its narrowest fallback
     (width_mm=0.15), which is below the board's configured 0.2mm min
     track width -- a genuine new DRC violation. Rip up that whole path
     and reroute at width_mm=0.2 (the actual floor), accepting it may not
     find a path at that width (better to leave the pre-existing gap
     open than commit an under-width track).
  2. The manually-placed ESP_EN via at (70.5,102.0) shorts a nearby
     USB_DM_C track -- placed blind, no clearance check. Remove it and
     use a small radial clearance-verified search (same pattern as
     heal_all.py's via_stitch) to place a safe one nearby instead.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")


def load():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
    g.setup_design_rules()
    g.LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
    g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
    g._nets = {}
    for code, ni in g.board.GetNetsByNetcode().items():
        if ni.GetNetname():
            g._nets[ni.GetNetname()] = ni
    g._outline_pts = list(BOARD_OUTLINE)
    g._extra_keepouts = []
    for (sx1, sy1, sx2, sy2) in WHEEL_NOTCHES:
        g._extra_keepouts.append((sx1 - 0.6, sy1 - 0.6, sx2 + 0.6, sy2 + 0.6))
    for (hx, hy, hr) in MOUNT_HOLES:
        m = hr + 0.75
        g._extra_keepouts.append((hx - m, hy - m, hx + m, hy + m))
    g._pads_geo_cache = None
    g._track_segs, g._vias = [], []
    for t in g.board.GetTracks():
        net = t.GetNet().GetNetname()
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            g._vias.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), net,
                            pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        elif t.GetClass() == "PCB_TRACK":
            a, b = t.GetStart(), t.GetEnd()
            g._track_segs.append(((pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)),
                                  (pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)), net,
                                  pcbnew.ToMM(t.GetWidth()) / 2, t.GetLayer()))
    return g


def step1a_remove_tracks():
    board = pcbnew.LoadBoard(BOARD)
    removed_tracks = 0
    for t in list(board.GetTracks()):
        if t.GetClass() == "PCB_TRACK" and t.GetNet().GetNetname() == "Net-(U8-~{RESET})":
            if pcbnew.ToMM(t.GetWidth()) < 0.19:
                board.Remove(t)
                removed_tracks += 1
    print(f"removed {removed_tracks} under-width RESET track segments")
    pcbnew.SaveBoard(BOARD, board)
    print("step1a saved", BOARD)


def step1b_remove_via():
    board = pcbnew.LoadBoard(BOARD)
    removed_via = 0
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_VIA":
            continue
        if t.GetNet().GetNetname() != "ESP_EN":
            continue
        p = t.GetPosition()
        x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        if abs(x - 70.5) < 0.05 and abs(y - 102.0) < 0.05:
            board.Remove(t)
            removed_via += 1
    print(f"removed {removed_via} shorting ESP_EN via(s)")
    pcbnew.SaveBoard(BOARD, board)
    print("step1b saved", BOARD)


def step2_refix():
    g = load()
    board = g.board

    ok = (g.retry_edge("Net-(U8-~{RESET})", (53.1483, 61.0484), (54.3408, 59.3505),
                       width_mm=0.2, clearance_mm=0.15, grid_mm=0.1, max_expansions=300000)
          or g.retry_edge("Net-(U8-~{RESET})", (53.1483, 61.0484), (54.3408, 59.3505),
                          width_mm=0.2, clearance_mm=0.127, grid_mm=0.05, max_expansions=800000))
    print(f"RESET regap at width>=0.2mm: {'OK' if ok else 'FAILED (left open, matches pre-existing state)'}")

    # radial clearance-verified via placement near (70.5, 102.0) on ESP_EN
    net = "ESP_EN"
    placed = None
    for d in (0.0, 0.3, 0.5, 0.7, 1.0, 1.3, 1.6):
        for k in range(16 if d else 1):
            th = k * math.pi / 8
            v = (round(70.5 + d * math.cos(th), 3), round(102.0 + d * math.sin(th), 3))
            if g._verify_geo([], [v], net, 0.13) is None:
                g.add_via(v, net)
                placed = v
                break
        if placed:
            break
    print(f"ESP_EN via re-placed at: {placed}")
    if placed and (abs(placed[0] - 70.5) > 0.01 or abs(placed[1] - 102.0) > 0.01):
        # the via moved off the exact junction point -- stitch it in with a
        # short track back to (70.5, 102.0) on whichever layer already has
        # copper there
        ok2 = g.retry_edge(net, placed, (70.5, 102.0), width_mm=0.25,
                           clearance_mm=0.15, grid_mm=0.05, max_expansions=150000)
        print(f"  stitch back to junction: {'OK' if ok2 else 'FAILED'}")

    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, board)
    print("step2 saved", BOARD)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "step1a"
    if arg == "step1b":
        step1b_remove_via()
    elif arg == "step2":
        step2_refix()
    else:
        step1a_remove_tracks()
