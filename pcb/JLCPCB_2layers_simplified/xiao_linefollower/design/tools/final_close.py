"""Fast, bounded final pass on the exact 24 remaining unconnected pairs from
the last real DRC run (0 violations otherwise -- no shorts, no clearance
errors). Modest max_expansions per attempt (fast), one retry tier, then
stop and save regardless -- no open-ended retrying.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")

PAIRS = [
    ("WALL_FR_SENSE", (58.255, 114.6025), (69.0875, 23.0)),
    ("BIN1", (41.745, 104.4425), (53.5, 72.975)),
    ("PLUS3V3", (54.825, 71.025), (53.5, 69.075)),
    ("ENC1_A", (21.9125, 50.0), (36.0, 70.199999)),
    ("ENC1_B", (37.5, 69.1), (25.9125, 50.0)),
    ("WALL_EMIT_DIAG", (54.912499, 37.5), (58.655, 103.1725)),
    ("WALL_EMIT_SIDE", (44.9125, 42.0), (41.345, 103.1725)),
    ("SDA", (23.9125, 102.0), (35.875, 105.1375)),
    ("SDA", (35.875, 105.1375), (41.345, 105.7125)),
    ("LINE5_ADC", (38.475, 110.8625), (70.9, 6.099999)),
    ("Net-(Q46-Pin_1)", (15.9125, 112.3), (69.1, 9.65)),
    ("Net-(Q43-Pin_1)", (15.9125, 105.1), (45.1, 9.65)),
    ("LINE3_ADC", (37.175, 110.8625), (54.9, 6.099999)),
    ("LINE1_ADC", (35.875, 110.8625), (38.9, 6.35)),
    ("LINE2_ADC", (36.525, 110.8625), (46.9, 6.35)),
    ("LINE4_ADC", (37.825, 110.8625), (62.9, 6.35)),
    ("Net-(D1-A)", (21.43, 13.73), (23.0875, 20.0)),
    ("Net-(Q44-Pin_1)", (15.9125, 107.5), (53.1, 9.65)),
    ("MOTA_P", (33.0, 69.1), (46.5, 69.075)),
    ("Net-(SW7-B)", (16.25, 114.97), (78.0875, 45.0)),
    ("Net-(Q45-Pin_1)", (15.9125, 109.899999), (61.1, 9.65)),
    ("Net-(Q42-Pin_1)", (15.9125, 102.7), (37.1, 9.65)),
    ("Net-(D2-A)", (75.0875, 20.0), (78.57, 13.73)),
    ("PWR_EN", (60.6, 54.0), (73.75, 114.97)),
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
    g._unrouted = []
    return g


def main():
    g = load()
    ok_count = 0
    fail = []
    for name, a, b in PAIRS:
        success = False
        for (w, clr, grid, maxexp) in ((0.2, 0.15, 0.12, 200000), (0.2, 0.13, 0.1, 350000)):
            if g.retry_edge(name, a, b, width_mm=w, clearance_mm=clr, grid_mm=grid, max_expansions=maxexp):
                success = True
                break
        if success:
            ok_count += 1
            print(f"OK {name} {a} -> {b}", flush=True)
        else:
            fail.append(name)
            print(f"FAIL {name} {a} -> {b}", flush=True)
    g.fill_zones()
    pcbnew.SaveBoard(BOARD, g.board)
    print(f"Closed {ok_count}/{len(PAIRS)}. Still open: {fail}")


if __name__ == "__main__":
    main()
