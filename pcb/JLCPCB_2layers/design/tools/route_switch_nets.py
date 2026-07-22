"""Targeted completion of the 4 switch nets left unrouted after the SW1-4
THT->SMD swap (rev 8, 2026-07-21). Unlike heal_all.py's whole-board healing
loop (which took ~2 hours on this board and still couldn't close these 4
specific gaps), this makes ONE direct retry_edge() attempt per net at the
exact endpoints DRC reports as unconnected, with a bounded expansion budget.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")

# (net, p1_mm, p2_mm, note)
JOBS = [
    ("USER_BTN", (40.5, 29.5), (42.4, 29.45), "SW1 last-mile via-drop stub -> pad"),
    ("ESP_EN", (58.75, 109.42), (65.2, 103.45), "U3 pad3 -> SW4 pad1"),
    ("USER_BTN2", (41.25, 96.72), (51.2, 29.45), "U3 pad28 -> SW2 pad1 (long cross-board run)"),
    ("USER_BTN3", (41.25, 97.99), (61.2, 29.45), "U3 pad29 -> SW3 pad1 (long cross-board run)"),
]


def main():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
    # NOTE: deliberately NOT calling g.setup_design_rules() here -- on an
    # already-configured, existing board (loaded from a project with its own
    # correct netclass/constraint settings), that call's writes to
    # board.GetDesignSettings() get persisted into the .kicad_pro on the next
    # SaveBoard(), silently overwriting this board's carefully-tuned rules
    # with generic defaults (discovered the hard way earlier this session --
    # see the design-rule-restore steps in this session's history). The
    # correct rules are already loaded natively from the project file; no
    # override needed.
    g.LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
    g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
    g._nets = {}
    for code, ni in g.board.GetNetsByNetcode().items():
        if ni.GetNetname():
            g._nets[ni.GetNetname()] = ni
    from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES
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
    g._unrouted = []

    for net, p1, p2, note in JOBS:
        print(f"routing {net} ({note}): {p1} -> {p2}")
        ok = (g.retry_edge(net, p1, p2, width_mm=0.25, clearance_mm=0.18,
                            grid_mm=0.15, max_expansions=80000)
              or g.retry_edge(net, p1, p2, width_mm=0.2, clearance_mm=0.15,
                               grid_mm=0.1, max_expansions=150000))
        print(f"  -> {'OK' if ok else 'FAILED'}")

    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
