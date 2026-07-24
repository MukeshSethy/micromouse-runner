"""Per user request: start from scratch on the whole congested U3 pin-field
region rather than fighting WALL_EMIT_DIAG around everyone else's
already-committed copper. Rips up all 19 small/local nets landing on U3's
front-signal pins (excludes GND and PLUS3V3 -- too big/risky to blindly
rip-up-reroute unattended), then re-routes with WALL_EMIT_DIAG FIRST (the one
net that has repeatedly failed to find a path around other nets' copper) so
it gets first pick of the empty corridor, then everything else longest-span
first (same MST-ordering convention this project's route_pcb.py established).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")

NETS = [
    "WALL_EMIT_DIAG",  # FIRST: the net that's been failing, gets the empty board
    "AIN1", "AIN2", "BIN1", "BIN2", "BUZZ_CTRL",
    "ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B",
    "USER_BTN", "USER_BTN2",
    "WALL_DL_SENSE", "WALL_DR_SENSE", "WALL_EMIT_FRONT", "WALL_EMIT_SIDE",
    "WALL_FL_SENSE", "WALL_FR_SENSE", "WALL_SL_SENSE", "WALL_SR_SENSE",
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


def net_span(g, net):
    pads = [p for p in g._pads_geo() if p["net"] == net]
    if len(pads) < 2:
        return 0
    xs = [p["cx"] for p in pads]
    ys = [p["cy"] for p in pads]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def route_with_retries(g, net, budgets):
    g._unrouted = []
    ok = g.route_net(net, width_mm=0.2, clearance_mm=0.18, max_expansions=budgets[0])
    if ok and not g._unrouted:
        return True
    retry_list = list(g._unrouted)
    g._unrouted = []
    all_ok = True
    for (n, p1, p2, reason) in retry_list:
        recovered = False
        for b in budgets[1:]:
            if g.retry_edge(n, p1, p2, width_mm=0.2, clearance_mm=0.15, max_expansions=b):
                recovered = True
                break
            if g.retry_edge(n, p1, p2, width_mm=0.2, clearance_mm=0.13, grid_mm=0.15, max_expansions=b):
                recovered = True
                break
        if not recovered:
            all_ok = False
            print(f"    still unrouted edge: {n} {p1}->{p2}")
    return all_ok


def main():
    # Step 1: strip all target nets to bare board.
    strip_board = pcbnew.LoadBoard(BOARD)
    removed = 0
    for t in list(strip_board.GetTracks()):
        if t.GetNet().GetNetname() in NETS:
            strip_board.Remove(t)
            removed += 1
    pcbnew.SaveBoard(BOARD, strip_board)
    print(f"stripped {removed} track/via items across {len(NETS)} nets")

    # Step 2: fresh load, route WALL_EMIT_DIAG FIRST on the now-empty corridor,
    # then everything else longest-span-first.
    g = load()
    order = ["WALL_EMIT_DIAG"] + sorted(
        [n for n in NETS if n != "WALL_EMIT_DIAG"],
        key=lambda n: net_span(g, n), reverse=True)
    print("route order:", order)

    results = {}
    for net in order:
        ok = route_with_retries(g, net, budgets=[300000, 500000, 800000])
        results[net] = ok
        print(f"  {'OK' if ok else 'FAIL'}  {net}  (span {net_span(g, net):.1f}mm)")

    clean = sum(1 for v in results.values() if v)
    print(f"\n{clean}/{len(order)} nets fully routed")
    fails = [n for n, ok in results.items() if not ok]
    if fails:
        print("FAILED nets:", fails)

    filler = pcbnew.ZONE_FILLER(g.board)
    filler.Fill(g.board.Zones())
    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
