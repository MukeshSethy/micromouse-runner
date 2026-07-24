"""Part 2 of reroute_u3_field.py, split into its own process: the strip step
already ran and saved (pcbnew corrupts internal state if you LoadBoard twice
in one process after a heavy removal -- confirmed empirically, same class of
issue as the earlier widen_tht_clearance.py crash). This script assumes the
20 target nets are ALREADY stripped from disk, and does the routing only:
WALL_EMIT_DIAG first (empty corridor), then the rest longest-span-first.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from complete_routing import load, BOARD

NETS = [
    "WALL_EMIT_DIAG",
    "AIN1", "AIN2", "BIN1", "BIN2", "BUZZ_CTRL",
    "ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B",
    "USER_BTN", "USER_BTN2",
    "WALL_DL_SENSE", "WALL_DR_SENSE", "WALL_EMIT_FRONT", "WALL_EMIT_SIDE",
    "WALL_FL_SENSE", "WALL_FR_SENSE", "WALL_SL_SENSE", "WALL_SR_SENSE",
]


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
    g = load()
    order = ["WALL_EMIT_DIAG"] + sorted(
        [n for n in NETS if n != "WALL_EMIT_DIAG"],
        key=lambda n: net_span(g, n), reverse=True)
    print("route order:", order, flush=True)

    results = {}
    for net in order:
        ok = route_with_retries(g, net, budgets=[300000, 500000, 800000])
        results[net] = ok
        print(f"  {'OK' if ok else 'FAIL'}  {net}  (span {net_span(g, net):.1f}mm)", flush=True)

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
