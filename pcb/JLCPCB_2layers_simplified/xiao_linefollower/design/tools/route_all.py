"""Full from-scratch routing pass for the line-follower board (freshly placed,
0 traces). Loads the board build_pcb.py just saved, routes every net via
route_net()'s MST+A* router, retrying failed nets with escalating
width/clearance/grid relaxation and, if still stuck, a re-shuffled net order
(routing a net first vs last changes what copper is already in its way).
Fills + reports the GND zone at the end. heal_all.py is the follow-up
convergence pass for any leftover fragments/gaps.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
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
    g = load()
    names = net_names(g)
    # Priority ordering (round 1): route power/GND-adjacent short nets and
    # the new line-follower nets FIRST (small, local, easy to block if
    # something else claims their tight space first), then everything else
    # by ascending pad count (fewer pads = fewer MST edges = less to route
    # and less likely to block later nets).
    def pad_count(n):
        return sum(1 for v in g.pad_to_net.values() if v == n)
    # Restart, different priority (per user's explicit "keep retrying with
    # different initial routes and priorities" instruction): the FIRST full
    # pass left these 20 nets stuck after every escalation tier AND after 5
    # reordered retries -- diagnosis showed real topology congestion (e.g.
    # U4/ADS7830's courtyard pinching off a pre-existing PWRLED_A corridor),
    # not a search-budget issue, so simply retrying them LAST (after 52
    # other nets already claimed the board's easy corridors) never had a
    # fair shot. This time they go FIRST, while the board is still empty.
    HARDEST_FIRST = ['GND', 'PWRLED_A', 'WALL_DL_SENSE', 'Net-(D46-K)', 'VM_6V',
                     'Net-(D42-K)', 'Net-(Q46-Pin_1)', 'BIN1', 'WALL_FL_SENSE',
                     'Net-(Q45-Pin_1)', 'WALL_EMIT_SIDE', 'Net-(D45-K)', 'Net-(SW7-B)',
                     'WALL_EMIT_FRONT', 'Net-(U4-REFin{slash}REFout)', 'Net-(D44-K)',
                     'Net-(Q44-Pin_1)', 'Net-(D43-K)', 'Net-(D2-A)', 'WALL_DR_SENSE']
    priority = [n for n in names if n.startswith(("LINE", "SDA", "SCL")) or n in ("GND", "PLUS3V3")]
    rest = sorted((n for n in names if n not in priority and n not in HARDEST_FIRST), key=pad_count)
    order1 = [n for n in HARDEST_FIRST if n in names] + [n for n in priority if n not in HARDEST_FIRST] + rest

    remaining = order1
    for round_no, params in enumerate(ATTEMPTS, start=1):
        if not remaining:
            break
        print(f"=== round {round_no}: {len(remaining)} nets, params={params}")
        remaining = route_round(g, remaining, params)
        print(f"    {len(remaining)} still unrouted: {remaining}")
        g.fill_zones()
        pcbnew.SaveBoard(BOARD, g.board)   # incremental save -- never lose a round's progress again
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
