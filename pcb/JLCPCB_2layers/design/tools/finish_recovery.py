"""Recovery step 3: heal_all.py's 6-round loop reconnected most of what
ripup_damaged_nets.py removed, but (a) auto-dropped 5 GND stitch vias
inside a keepout area near J1/the battery connector, and (b) left a
handful of real gaps unclosed after 6 rounds (it got stuck spending most
of its cycles chasing pre-existing GND zone-fragment noise unrelated to
today's recovery). This removes the bad vias and micro-routes the
remaining real gaps directly with retry_edge.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")

BAD_VIA_POS_MM = [
    (49.446, 111.552), (50.646, 111.552), (51.246, 111.552),
    (51.846, 111.552), (50.046, 111.552),
]

GAPS = [
    ("ENC2_B", (59.1167, 58.8579), (52.3544, 55.3802)),
    ("ENC2_B", (59.1167, 68.5717), (62.5, 70.0)),
    ("ESP_EN", (69.7295, 101.2295), (70.5, 102.0)),
    ("WALL_EMIT_SIDE", (60.8173, 66.0605), (60.1665, 80.3831)),
    ("USB_DM_C", (63.2416, 111.05), (69.25, 111.995)),
    ("USB_DM_C", (69.25, 111.995), (70.25, 111.995)),
]


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


def step1_remove_bad_vias():
    board = pcbnew.LoadBoard(BOARD)
    removed = 0
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_VIA":
            continue
        if t.GetNet().GetNetname() != "GND":
            continue
        p = t.GetPosition()
        x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        if any(abs(x - bx) < 0.05 and abs(y - by) < 0.05 for (bx, by) in BAD_VIA_POS_MM):
            board.Remove(t)
            removed += 1
    print(f"removed {removed} keepout-violating GND vias")
    pcbnew.SaveBoard(BOARD, board)
    print("step1 saved", BOARD)


def step2_route_gaps():
    g = load()
    ok_count = 0
    for (net, A, B) in GAPS:
        ok = (g.retry_edge(net, A, B, width_mm=0.25, clearance_mm=0.2,
                           grid_mm=0.1, max_expansions=300000)
              or g.retry_edge(net, A, B, width_mm=0.25, clearance_mm=0.15,
                              grid_mm=0.1, max_expansions=300000)
              or g.retry_edge(net, A, B, width_mm=0.2, clearance_mm=0.13,
                              grid_mm=0.05, max_expansions=400000))
        print(f"  {net} {A}->{B}: {'OK' if ok else 'FAILED'}")
        if ok:
            ok_count += 1

    print(f"routed {ok_count}/{len(GAPS)} gaps")
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, g.board)
    print("step2 saved", BOARD)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "step2":
        step2_route_gaps()
    else:
        step1_remove_bad_vias()
