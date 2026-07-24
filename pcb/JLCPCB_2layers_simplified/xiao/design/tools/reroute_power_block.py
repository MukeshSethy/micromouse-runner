"""Re-route the power-block nets after discovering the user's manual moves
spanned the WHOLE power section (U1/C1-C5/L1/U7/C15-C18/L2/Q1/R1/F1/BZ1/
Q34/R81/D29/R69-R71/R73-R74/R85), not just the 5 components tracked earlier.
The narrower fix left stale dangling stubs at old pad positions that shorted
into other nets' copper (5 shorting_items + 5 solder_mask_bridge errors).
Strip already done and verified (0 remaining) as a separate process step;
this one just routes, longest-span first (no single net here is as
congested as the U3 pin field, so no special first-pick ordering needed).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from complete_routing import load, BOARD

NETS = [
    "BATT_RAW", "BUZZ_CTRL", "BUZZ_DRV", "FB_6V", "MOT_EN",
    "Net-(Q1-D)", "Net-(Q1-G)", "Net-(Q34-B)", "Net-(SW7-B)",
    "Net-(U1-BST)", "Net-(U7-BOOT)", "PLUS3V3", "PWR_EN",
    "SW_3V3", "SW_6V", "VM_6V", "VM_BATT",
]

POWER_WIDE = {"PLUS3V3", "VM_6V", "VM_BATT", "BATT_RAW"}


def net_span(g, net):
    pads = [p for p in g._pads_geo() if p["net"] == net]
    if len(pads) < 2:
        return 0
    xs = [p["cx"] for p in pads]
    ys = [p["cy"] for p in pads]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def main():
    g = load()
    order = sorted(NETS, key=lambda n: net_span(g, n), reverse=True)
    print("route order:", order, flush=True)

    results = {}
    for net in order:
        width = 0.5 if net in POWER_WIDE else 0.25
        g._unrouted = []
        ok = g.route_net(net, width_mm=width, clearance_mm=0.18, max_expansions=300000)
        if not (ok and not g._unrouted):
            retry_list = list(g._unrouted)
            g._unrouted = []
            ok = True
            for (n, p1, p2, reason) in retry_list:
                recovered = False
                for b in (500000, 800000, 1200000):
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
