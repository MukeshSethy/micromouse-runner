import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math
import runpy
import pcbnew

# Re-runs the placement (build_pcb.py) fresh, then routes every net on top of
# it. GND is deliberately NOT routed -- it is carried by the full-board GND
# pours on both copper layers (standard 2-layer practice; kicad's DRC/zone
# fill resolves pad-to-zone connectivity). Everything else gets real tracks.
#
# Pass structure (arrived at empirically across three full-board runs, see
# PROJECT_NOTES.md routing log):
#   0. micro-bridges: all MST edges < 2mm, across ALL nets, before anything
#      else. These are mostly the TB6612's doubled output pins (adjacent
#      0.65mm-pitch pads on the same net) whose only legal route hugs the pad
#      column -- if any other net passes there first they become unroutable.
#   1. signal nets, LONGEST span first: the long cross-board runs (sensor
#      LED/SENSE lines, GPIO fan-out) are the constrained ones; they get the
#      empty board. Short local nets can always squeeze in afterwards.
#   2. PLUS3V3 (the 52-pad web) -- big enough to fence the board, so it goes
#      after signals, but before the few fat motor/battery nets which have
#      the most detour freedom.
#   3. remaining power nets.
#   4. retry pass with a 400k-expansion budget for anything left.
#
# Net classes: power 0.5mm wide (motor stall + regulator input currents),
# signals 0.25mm. Clearance 0.15mm routed / 0.13mm verify floor / 0.127mm
# board DRC rule -- all above JLCPCB's standard 0.127mm capability.

ns = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_pcb.py"))
g = ns["g"]

POWER_NETS = [
    "VM_BATT",
    "Net-(J1-Pin_1)", "Net-(J2-Pin_2)", "Net-(F1-Pad2)",
    "Net-(J5-Pin_1)", "Net-(J5-Pin_2)",
    "Net-(J6-Pin_1)", "Net-(J6-Pin_2)",
    "Net-(U1-SW)",
]
SIG_W, PWR_W, CLR = 0.25, 0.5, 0.15

all_nets = sorted(set(g.pad_to_net.values()))
skip = {"GND"}

def net_span(net):
    pads = [p for p in g._pads_geo() if p["net"] == net]
    if len(pads) < 2:
        return 0
    xs = [p["cx"] for p in pads]
    ys = [p["cy"] for p in pads]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))

signal_nets = [n for n in all_nets if n not in skip and n not in POWER_NETS and n != "PLUS3V3"]
signal_nets.sort(key=net_span, reverse=True)

g.setup_design_rules()
t0 = time.time()

def width_of(net):
    return PWR_W if (net in POWER_NETS or net == "PLUS3V3") else SIG_W

# Pass 0: micro-bridges everywhere first.
for net in all_nets:
    if net in skip:
        continue
    g.route_net(net, width_mm=width_of(net), clearance_mm=CLR, max_edge_mm=2.0)
print(f"Micro-bridge pass done at {time.time()-t0:.0f}s, failed so far: {len(g._unrouted)}")

# Pass 1-3.
results = {}
for net in signal_nets:
    results[net] = g.route_net(net, width_mm=SIG_W, clearance_mm=CLR, min_edge_mm=2.0)
if "PLUS3V3" in all_nets:
    results["PLUS3V3"] = g.route_net("PLUS3V3", width_mm=PWR_W, clearance_mm=CLR, min_edge_mm=2.0)
for net in POWER_NETS:
    if net in all_nets:
        results[net] = g.route_net(net, width_mm=PWR_W, clearance_mm=CLR, min_edge_mm=2.0)

clean = sum(1 for ok in results.values() if ok)
print(f"Main pass finished at {time.time()-t0:.0f}s: {clean}/{len(results)} nets clean, "
      f"{len(g._unrouted)} failed edges")

# Pass 4: per-edge retry. First a big-budget pass on the 0.5mm grid, then a
# finer 0.3mm grid for anything still stuck (finds paths through gaps the
# coarse grid can't resolve, at the cost of a slower search -- only run on the
# few genuinely-hard edges, so total cost stays bounded).
retry_list = list(g._unrouted)
g._unrouted = []
still_failed = []
for (net, p1, p2, reason) in retry_list:
    ok = g.retry_edge(net, p1, p2, width_mm=width_of(net), clearance_mm=CLR,
                       max_expansions=400000)
    if not ok:
        ok = g.retry_edge(net, p1, p2, width_mm=width_of(net), clearance_mm=CLR,
                           grid_mm=0.3, max_expansions=500000)
    if not ok:
        still_failed.append((net, p1, p2, reason))
print(f"Retry pass: {len(retry_list) - len(still_failed)}/{len(retry_list)} recovered, "
      f"total {time.time()-t0:.0f}s")
for (net, p1, p2, reason) in still_failed:
    print(f"   STILL UNROUTED {net}: {p1} -> {p2}  [first-pass reason: {reason}]")

g.save(r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb")
print("Saved.")
