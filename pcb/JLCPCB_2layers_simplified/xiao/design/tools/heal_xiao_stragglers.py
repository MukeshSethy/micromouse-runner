"""Targeted micro-route pass for the specific handful of nets Freerouting
consistently left unrouted on the XIAO board (same ~11 nets across multiple
runs -- verified deterministic, not routing-seed noise). Faster than the
generic heal_all.py loop (which re-runs a full kicad-cli DRC each round and
tries every unconnected item, including zone-fill/ratsnest artifacts) because
it goes straight at the known pad pairs with retry_edge(), same as heal_all.py
uses internally.

Pad pairs sourced directly from the Freerouting session log's own
"could not be routed" report.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")

# (net_name, ref1, pad1, ref2, pad2) -- straight from the freerouting log.
# Round 1 (smaller budgets) already healed AIN1/ENC2_B/PLUS3V3 -- this round
# targets only the 7 still-failing long nets (50-85mm span) with a much
# bigger per-attempt expansion budget, since there are fewer of them left.
TARGETS = [
    ("WALL_EMIT_FRONT", "R62", "1", "U3", "19"),
    ("WALL_EMIT_DIAG",  "U3", "20", "R63", "1"),
    ("WALL_EMIT_SIDE",  "U3", "21", "R64", "1"),
    ("MOT_EN",          "SW6", "2", "R70", "2"),
    ("AIN2",            "U3", "8", "U2", "22"),
    ("BUZZ_CTRL",       "R81", "1", "U3", "11"),
    ("USER_BTN2",       "SW2", "1", "U3", "23"),
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


def pad_pos(g, ref, padnum):
    fp = g._placed.get(ref)
    if fp is None:
        return None
    for pad in fp.Pads():
        if pad.GetNumber() == padnum:
            p = pad.GetPosition()
            return (round(pcbnew.ToMM(p.x), 3), round(pcbnew.ToMM(p.y), 3))
    return None


def main():
    g = load()
    ok, fail = [], []
    for (net, r1, p1n, r2, p2n) in TARGETS:
        a = pad_pos(g, r1, p1n)
        b = pad_pos(g, r2, p2n)
        if a is None or b is None:
            fail.append((net, f"{r1}.{p1n}/{r2}.{p2n}", "pad lookup failed"))
            continue
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        routed = False
        for (width, clr, grid, maxexp) in (
            (0.25, 0.18, 0.2, 300000),
            (0.25, 0.15, 0.15, 500000),
            (0.2, 0.15, 0.1, 700000),
        ):
            if g.retry_edge(net, a, b, width_mm=width, clearance_mm=clr,
                             grid_mm=grid, max_expansions=maxexp):
                routed = True
                break
        if routed:
            print(f"  OK {net}: {r1}.{p1n}({a}) <-> {r2}.{p2n}({b})  d={d:.1f}mm")
            ok.append(net)
        else:
            print(f"  FAIL {net}: {r1}.{p1n}({a}) <-> {r2}.{p2n}({b})  d={d:.1f}mm")
            fail.append((net, f"{r1}.{p1n}/{r2}.{p2n}", "no path found"))

    print(f"\nhealed {len(ok)}/{len(TARGETS)}: {ok}")
    if fail:
        print("still failing:")
        for (net, pair, why) in fail:
            print(f"  {net} ({pair}): {why}")
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
