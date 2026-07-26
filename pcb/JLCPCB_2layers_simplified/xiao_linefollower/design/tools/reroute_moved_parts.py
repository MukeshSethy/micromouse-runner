"""Re-route the nets touching the components the user manually repositioned
(L2, C16, U7-area, Q34, R81, D29, BZ1, R63/Q17) after both placement and
GND were confirmed clean. Nets already stripped from disk by a prior step.
WALL_EMIT_DIAG goes first (empty corridor advantage), then longest-span-first.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from complete_routing import load, BOARD

NETS = [
    "WALL_EMIT_DIAG",
    "VM_6V", "VM_BATT",
    "BUZZ_CTRL", "BUZZ_DRV", "EMIT_DIAG_K", "FB_6V", "MOT_EN",
    "Net-(Q34-B)", "Net-(U7-BOOT)", "SW_6V",
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
    ok = g.route_net(net, width_mm=0.25, clearance_mm=0.18, max_expansions=budgets[0])
    if ok and not g._unrouted:
        return True
    retry_list = list(g._unrouted)
    g._unrouted = []
    all_ok = True
    for (n, p1, p2, reason) in retry_list:
        recovered = False
        for b in budgets[1:]:
            if g.retry_edge(n, p1, p2, width_mm=0.25, clearance_mm=0.15, max_expansions=b):
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
        # power nets get the wider 0.5mm trace width, signals stay 0.25mm
        width = 0.5 if net in ("VM_6V", "VM_BATT") else 0.25
        g._unrouted = []
        ok = g.route_net(net, width_mm=width, clearance_mm=0.18, max_expansions=300000)
        if not (ok and not g._unrouted):
            retry_list = list(g._unrouted)
            g._unrouted = []
            ok = True
            for (n, p1, p2, reason) in retry_list:
                recovered = False
                for b in (500000, 800000):
                    if g.retry_edge(n, p1, p2, width_mm=width, clearance_mm=0.15, max_expansions=b):
                        recovered = True
                        break
                    if g.retry_edge(n, p1, p2, width_mm=width, clearance_mm=0.13, grid_mm=0.15, max_expansions=b):
                        recovered = True
                        break
                if not recovered:
                    ok = False
                    print(f"    still unrouted edge: {n} {p1}->{p2}", flush=True)
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
