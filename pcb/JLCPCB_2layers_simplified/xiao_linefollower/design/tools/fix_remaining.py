"""Targeted retry for the specific nets route_all.py could not close after 4
escalating rounds + 5 reorder retries (52/72 nets succeeded there). Loads the
board AS-IS (route_all.py's own save, ~4100 tracks/242 vias already placed --
never re-runs build_pcb.py, which would discard that work). Uses much larger
max_expansions/smaller grid on just the known-stuck nets, since "far apart"
is a search-budget problem, not necessarily an impossibility. GND gets a
dedicated zone-fill + largest-fragment-bridge pass (it's poured, not routed
point-to-point).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")

STUCK_NETS = ['PWRLED_A', 'WALL_DL_SENSE', 'Net-(D46-K)', 'VM_6V', 'GND', 'Net-(D42-K)',
              'Net-(Q46-Pin_1)', 'BIN1', 'WALL_FL_SENSE', 'Net-(Q45-Pin_1)', 'WALL_EMIT_SIDE',
              'Net-(D45-K)', 'Net-(SW7-B)', 'WALL_EMIT_FRONT', 'Net-(U4-REFin{slash}REFout)',
              'Net-(D44-K)', 'Net-(Q44-Pin_1)', 'Net-(D43-K)', 'Net-(D2-A)', 'WALL_DR_SENSE']


def load():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
    g.setup_design_rules()
    # This script deliberately routes a handful of stuck nets at 0.15mm
    # width / 0.127mm clearance -- both still within JLCPCB's documented
    # real fab minimum (0.127mm track/clearance), so the board-wide minimum
    # rules must be relaxed to match or these tracks would be DRC
    # violations despite routing successfully. Everything else on the board
    # stays at the wider 0.2/0.3mm the rest of the design already uses.
    bds = g.board.GetDesignSettings()
    bds.m_TrackMinWidth = pcbnew.FromMM(0.127)
    try:
        bds.m_NetSettings.GetDefaultNetclass().SetClearance(pcbnew.FromMM(0.127))
    except Exception:
        pass
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


def bridge_gnd_fragments(g):
    """Same-net via bridge between the largest GND fill fragment and every
    smaller one, on each copper layer -- standard fix for a poured net that
    DRC/route_net reports as one unconnected item (zone fragments = islands
    the router can't join by definition, since it isn't a 2-pad route)."""
    n_bridged = 0
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = None
        for z in g.board.Zones():
            if z.GetNetname() == "GND" and z.GetLayer() == layer:
                zone = z
        if zone is None:
            continue
        poly = zone.GetFilledPolysList(layer)
        if poly.OutlineCount() <= 1:
            continue
        areas = [(abs(poly.Outline(i).Area()), i) for i in range(poly.OutlineCount())]
        main = max(areas)[1]
        main_chain = poly.Outline(main)
        for (_, fi) in areas:
            if fi == main:
                continue
            chain = poly.Outline(fi)
            bb = chain.BBox()
            cx = (pcbnew.ToMM(bb.GetLeft()) + pcbnew.ToMM(bb.GetRight())) / 2
            cy = (pcbnew.ToMM(bb.GetTop()) + pcbnew.ToMM(bb.GetBottom())) / 2
            # nearest point on the MAIN outline to this fragment's centroid
            best = None
            for j in range(main_chain.PointCount()):
                pt = main_chain.CPoint(j)
                mx, my = pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y)
                d = math.hypot(mx - cx, my - cy)
                if best is None or d < best[0]:
                    best = (d, (mx, my))
            if best is None:
                continue
            target = best[1]
            placed_frag = placed_main = None
            for ddx in (0.0, 0.5, -0.5, 1.0, -1.0):
                for ddy in (0.0, 0.5, -0.5, 1.0, -1.0):
                    v = (round(cx + ddx, 3), round(cy + ddy, 3))
                    pv = pcbnew.VECTOR2I(pcbnew.FromMM(v[0]), pcbnew.FromMM(v[1]))
                    if chain.PointInside(pv, 0, True) and g._verify_geo([], [v], "GND", 0.125) is None:
                        placed_frag = v
                        break
                if placed_frag:
                    break
            if placed_frag and g.retry_edge("GND", placed_frag, target, width_mm=0.3,
                                             clearance_mm=0.15, grid_mm=0.15, max_expansions=500000):
                print(f"  GND fragment bridge ({pcbnew.LayerName(layer)}) {placed_frag} -> {target}")
                n_bridged += 1
    return n_bridged


def main():
    g = load()
    remaining = []
    for name in STUCK_NETS:
        if name == "GND":
            continue
        ok = False
        # These parameter tiers are DELIBERATELY at/near JLCPCB's absolute
        # fab minimum (0.127mm track/clearance) -- route_all.py already
        # exhausted every tier down to (0.2, 0.13) on these specific nets
        # with "no path found"/"too close to X" (an exhaustive search
        # result, not a budget cutoff -- more max_expansions would not have
        # helped), so repeating similar values is pointless. Going tighter
        # is the only lever left short of moving placement.
        for (w, clr, grid, maxexp) in (
            (0.15, 0.127, 0.1, 600000),
            (0.15, 0.127, 0.08, 900000),
        ):
            g._unrouted = []
            ok = g.route_net(name, width_mm=w, clearance_mm=clr, grid_mm=grid, max_expansions=maxexp)
            if ok:
                print(f"OK {name} width={w} clr={clr} grid={grid}", flush=True)
                break
            else:
                print(f"  {name} attempt width={w} clr={clr} grid={grid}: FAILED "
                      f"({g._unrouted[-1][3] if g._unrouted else '?'})", flush=True)
        if not ok:
            remaining.append(name)
        else:
            pcbnew.SaveBoard(BOARD, g.board)   # incremental save after every success

    print("fill_zones:", g.fill_zones(), flush=True)
    n = bridge_gnd_fragments(g)
    print(f"GND fragments bridged: {n}", flush=True)
    print("fill_zones (post-bridge):", g.fill_zones(), flush=True)

    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD, flush=True)
    print("STILL UNROUTED (non-GND):", remaining, flush=True)


if __name__ == "__main__":
    main()
