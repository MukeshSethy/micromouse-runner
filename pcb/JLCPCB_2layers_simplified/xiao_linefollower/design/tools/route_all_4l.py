"""Full from-scratch 4-layer routing pass on the CURRENT (already manually
placed) board -- never re-runs build_pcb.py, so the extensive manual
placement work this session (motor-bay cleanup, 9mm-pitch sensor row, PCF8574
cluster, etc.) is preserved exactly.

Adapted from route_all.py, which pre-dates the 4-layer stackup conversion and
still had `g.LAYERS = [F_Cu, B_Cu]` (a 2-layer default) -- fixed here to the
board's real 4 copper layers (F.Cu/In1.Cu/In2.Cu/B.Cu). Strips ALL existing
tracks/vias first: the board carries a patchwork of partial routes from many
placement-round copper removals this session, not a coherent single pass, so
route_net()'s from-scratch MST (which does not de-duplicate against
pre-existing same-net copper) would otherwise draw redundant parallel traces
over stale routing. A clean-slate route matches this project's own documented
pipeline ("routing from a clean placement lets the router solve the whole
board at once").
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")


def strip_copper():
    board = pcbnew.LoadBoard(BOARD)
    tracks = list(board.GetTracks())
    for t in tracks:
        board.Remove(t)
    print(f"stripped {len(tracks)} track/via items")
    pcbnew.SaveBoard(BOARD, board)


def load():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
    g.setup_design_rules()
    g.LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
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
    g._unrouted = []
    return g


def net_names(g):
    names = sorted(set(g.pad_to_net.values()))
    return [n for n in names if n and not n.startswith("unconnected-")]


ATTEMPTS = [
    dict(width_mm=0.3, clearance_mm=0.18, grid_mm=0.2, max_expansions=150000),
    dict(width_mm=0.25, clearance_mm=0.15, grid_mm=0.15, max_expansions=250000),
    dict(width_mm=0.2, clearance_mm=0.15, grid_mm=0.1, max_expansions=400000),
    dict(width_mm=0.2, clearance_mm=0.13, grid_mm=0.1, max_expansions=600000),
]


def route_round(g, names, params):
    still_bad = []
    for name in names:
        g._unrouted = []
        ok = g.route_net(name, **params)
        if not ok:
            still_bad.append(name)
    return still_bad


def main():
    # SWIG note: board.Remove() calls in strip_copper() degrade every
    # pcbnew proxy for the rest of THIS process (established pattern on this
    # environment) -- strip_copper() must run in a separate process from the
    # routing that follows, even though both start with a fresh LoadBoard().
    if len(sys.argv) > 1 and sys.argv[1] == "strip":
        strip_copper()
        return
    g = load()
    names = net_names(g)

    def pad_count(n):
        return sum(1 for v in g.pad_to_net.values() if v == n)

    # GND and power rails first (large fanout, want first pick of corridors),
    # then the 8-channel line-sensor ADC nets (new this session, tight
    # spacing), then everything else by ascending pad count.
    priority = [n for n in names if n.startswith(("LINE", "SDA", "SCL")) or n in ("GND", "PLUS3V3")]
    rest = sorted((n for n in names if n not in priority), key=pad_count)
    order1 = priority + rest

    remaining = order1
    for round_no, params in enumerate(ATTEMPTS, start=1):
        if not remaining:
            break
        print(f"=== round {round_no}: {len(remaining)} nets, params={params}")
        remaining = route_round(g, remaining, params)
        print(f"    {len(remaining)} still unrouted: {remaining}")
        g.fill_zones()
        pcbnew.SaveBoard(BOARD, g.board)
        print(f"    (incremental save after round {round_no})")

    print("fill_zones:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)
    if remaining:
        print("FINAL UNROUTED NETS:", remaining)
    else:
        print("ALL NETS ROUTED")


if __name__ == "__main__":
    main()
