"""Route the user's hand-edited board IN PLACE with the in-house router
(gen_pcb.py), preserving every component position. Used because Freerouting's
SES writer hangs on this board's interior wheel-slot geometry. Routes at 0.3mm
clearance so no trace fits between through-hole pins (hand-solder safety).
GND is left to the pours; everything else gets copper tracks."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math
import pcbnew
from gen_pcb import PcbGen

BOARD = r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb"
NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"

# PcbGen gives us the router methods + netlist map; swap in the USER's board
# so we route their exact placement (never regenerate it).
g = PcbGen(NETLIST)
g.board = pcbnew.LoadBoard(BOARD)
g.setup_design_rules()   # 0.3mm default-netclass clearance (no inter-pin traces)

# Populate the router's placement view from the loaded footprints.
g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
# Register existing nets so add_track/add_via reuse them (don't create dupes).
g._nets = {}
for code, ni in g.board.GetNetsByNetcode().items():
    nm = ni.GetNetname()
    if nm:
        g._nets[nm] = ni

# Outer board outline (chamfered 150x185). Interior wheel slots + motor
# keep-outs are handled as obstacles via _keepout_rects (board zones) + here.
g._outline_pts = [(25, 0), (125, 0), (150, 25), (150, 185), (0, 185), (0, 25)]
# Interior wheel slots (wheels inside the envelope) as router obstacles.
AXLE_Y = 78
g._extra_keepouts = [
    (4, AXLE_Y - 16, 13, AXLE_Y + 16),            # left wheel slot
    (137, AXLE_Y - 16, 146, AXLE_Y + 16),         # right wheel slot
]

# Strip any leftover tracks first (finalize already did, but be safe).
for t in list(g.board.GetTracks()):
    g.board.Remove(t)
g._track_segs = []
g._vias = []
g._pads_geo_cache = None

all_nets = sorted(set(g.pad_to_net.values()))
skip = {"GND"}

def span(net):
    pads = [p for p in g._pads_geo() if p["net"] == net]
    if len(pads) < 2:
        return 0
    xs = [p["cx"] for p in pads]; ys = [p["cy"] for p in pads]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))

POWER = {"VM_BATT", "PLUS3V3", "Net-(J1-Pin_1)", "Net-(J2-Pin_2)", "Net-(F1-Pad2)",
         "MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N", "Net-(U1-SW)"}
sig = [n for n in all_nets if n not in skip and n not in POWER]
sig.sort(key=span, reverse=True)

t0 = time.time()
CLR = 0.3   # no-inter-pin
EXP = 30000   # bounded so the whole board finishes in a few minutes
# micro-bridges first (adjacent same-net pins), then long signals, then power.
for n in all_nets:
    if n not in skip:
        g.route_net(n, width_mm=0.3, clearance_mm=CLR, max_edge_mm=2.2, max_expansions=EXP)
print(f"[{time.time()-t0:.0f}s] micro-bridges done, {len(g._unrouted)} fails")
for n in sig:
    g.route_net(n, width_mm=0.3, clearance_mm=CLR, min_edge_mm=2.2, max_expansions=EXP)
print(f"[{time.time()-t0:.0f}s] signals done, {len(g._unrouted)} fails")
for n in POWER:
    if n in all_nets:
        g.route_net(n, width_mm=0.5, clearance_mm=CLR, min_edge_mm=2.2, max_expansions=EXP)
print(f"[{time.time()-t0:.0f}s] power done, {len(g._unrouted)} fails")

# ONE retry pass, bounded (no finer grid -- keeps total time sane).
retry = list(g._unrouted); g._unrouted = []
still = []
for (net, p1, p2, reason) in retry:
    w = 0.5 if net in POWER else 0.3
    ok = g.retry_edge(net, p1, p2, width_mm=w, clearance_mm=CLR, max_expansions=120000)
    if not ok:
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] retry done")

pcbnew.SaveBoard(BOARD, g.board)
tr = sum(1 for t in g.board.GetTracks() if t.GetClass() == "PCB_TRACK")
vi = sum(1 for t in g.board.GetTracks() if t.GetClass() == "PCB_VIA")
print(f"Routed in {time.time()-t0:.0f}s. Board now has {tr} tracks, {vi} vias.")
print(f"Unrouted edges remaining: {len(still)}")
for (net, p1, p2, reason) in still[:40]:
    print(f"   {net}: {reason}")
