"""Route the THT carrier (v2 -- fast-fail + bounded ladder + per-net log).

Lesson from v1 (ran 165 min, saved nothing): on a THT board every one of the
481 pad barrels blocks all 4 layers, so a net that can't route at 300k
expansions will NOT route at 2.5M -- the huge ladder just burns hours. v2:
  - first pass 150k (fast fail), log every slow/failed net
  - per-net ladder = 3 SHORT rungs (loosen clearance / finer grid / relief), <=700k
  - power nets first at 0.8mm; signals 0.4mm
  - stragglers left for heal_all.py + hand-routing (logged explicitly)
GND rides F/B/In1 pours and PLUS3V3 the In2 plane -- every THT pad connects
to its plane at zone fill, so those two nets are never routed.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
import board_geom

# KiCad's Python block-buffers stdout when it's redirected to a file (not a
# TTY); reconfigure to line-buffered so the progress log is actually watchable.
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
LOG = open(os.path.join(r"D:\tmp", "route_tht.log"), "w", buffering=1)

def say(m):
    print(m, flush=True)
    LOG.write(m + "\n"); LOG.flush()

BASE = r"D:\Projects\micromouse-pcb\tht-assembly\pcb"
BOARD = os.path.join(BASE, "micromouse-tht.kicad_pcb")

g = PcbGen(os.path.join(BASE, "netlist.net"))
g.board = pcbnew.LoadBoard(BOARD)
try:
    _ = [fp.GetReference() for fp in g.board.GetFootprints()]
except TypeError:
    raise SystemExit("DEGRADED LOAD -- retry")
g.setup_design_rules()
# CRITICAL: route signals ONLY on the two OUTER layers. In1 = GND plane and
# In2 = PLUS3V3 plane -- laying signal tracks on them fragments the plane fill
# and produces hundreds of phantom-unconnected items (v1 THT route bug: 455
# ratsnest from MOTA_P etc. tracks stranded on In2). THT barrels reach the
# inner planes directly, so GND/3V3 need no routing.
g.LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
g._nets = {}
for code, ni in g.board.GetNetsByNetcode().items():
    if ni.GetNetname():
        g._nets[ni.GetNetname()] = ni

# outline polygon (router inside-test)
segs = []
for d in g.board.GetDrawings():
    if d.GetLayerName() == "Edge.Cuts" and d.GetClass() == "PCB_SHAPE":
        try:
            s_, e_ = d.GetStart(), d.GetEnd()
            segs.append(((pcbnew.ToMM(s_.x), pcbnew.ToMM(s_.y)),
                         (pcbnew.ToMM(e_.x), pcbnew.ToMM(e_.y))))
        except Exception:
            pass
poly = [segs[0][0], segs[0][1]]
used = {0}
while len(used) < len(segs):
    for i, (a, b) in enumerate(segs):
        if i in used:
            continue
        if abs(a[0]-poly[-1][0]) < 0.01 and abs(a[1]-poly[-1][1]) < 0.01:
            poly.append(b); used.add(i); break
        if abs(b[0]-poly[-1][0]) < 0.01 and abs(b[1]-poly[-1][1]) < 0.01:
            poly.append(a); used.add(i); break
    else:
        break
g._outline_pts = poly
g._extra_keepouts = []
for (hx, hy, hr) in board_geom.MOUNT_HOLES:
    m = hr + 0.75
    g._extra_keepouts.append((hx - m, hy - m, hx + m, hy + m))
g._pads_geo_cache = None
g._track_segs, g._vias = [], []
g._unrouted = []

POUR = {"GND", "PLUS3V3", ""}
POWER = {"BATT_RAW", "VM_BATT", "VM_6V", "SW_3V3", "SW_6V", "F1_OUT",
         "MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"}
CLR = 0.3
all_nets = sorted(set(g.pad_to_net.values()) - POUR,
                  key=lambda n: (n not in POWER, n))

def width_for(n):
    # 0.5mm power: a 0.8mm trace + 2x0.3 clearance (1.4mm) cannot thread the
    # 0.94mm gap between adjacent THT pins, but 0.5mm can detour more freely.
    # Electrically ample -- robu GA12-N20 stalls at 0.23A; 0.5mm 1oz ~= 1.3A,
    # and VM_BATT's ~1.4A board draw runs a short compact span.
    return 0.5 if n in POWER else 0.4

t0 = time.time()
routed = failed = 0
say(f"routing {len(all_nets)} signal nets (GND/3V3 = planes)")
for i, n in enumerate(all_nets):
    tn = time.time()
    before = len(g._unrouted)
    # single bounded pass per net; NO huge ladder -- a THT net with no path
    # at 200k won't find one at 2M, it just burns time. Stragglers -> heal.
    g.route_net(n, width_mm=width_for(n), clearance_mm=CLR, max_expansions=200000)
    if len(g._unrouted) == before:
        routed += 1; tag = "ok"
    else:
        prev = [u for u in g._unrouted if u[0] == n]
        g._unrouted[:] = [u for u in g._unrouted if u[0] != n]
        fixed = True
        for (net, p1, p2, reason) in prev:
            w = width_for(net)
            # rung 1: same width, relaxed clearance/finer grid; rung 2 (power
            # only): 0.3mm can thread between adjacent THT pins where 0.5 can't
            if not (g.retry_edge(net, p1, p2, width_mm=w, clearance_mm=0.18,
                                 grid_mm=0.2, max_expansions=350000)
                    or (net in POWER
                        and g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=0.18,
                                         grid_mm=0.15, max_expansions=500000))):
                g._unrouted.append((net, p1, p2, reason))
                fixed = False
        routed += fixed; failed += (not fixed)
        tag = "ok(retry)" if fixed else "FAIL"
    dt = time.time() - tn
    say(f"[{time.time()-t0:5.0f}s] {i+1:3d}/{len(all_nets)} {n:<18} {tag} {dt:4.1f}s")
    if (i + 1) % 15 == 0:                        # incremental save (SWIG-safe)
        g.fill_zones()
        pcbnew.SaveBoard(BOARD, g.board)
        say(f"  -- checkpoint saved at net {i+1} ({routed} ok, {failed} fail)")

say(f"[{time.time()-t0:.0f}s] routing done: {routed} ok, {failed} fail")
say(f"zone fill: {g.fill_zones()}")
pcbnew.SaveBoard(BOARD, g.board)
g.board.BuildConnectivity()
rn = g.board.GetConnectivity().GetUnconnectedCount(True)
tr = sum(1 for t in g.board.GetTracks() if t.GetClass() == "PCB_TRACK")
say(f"SAVED: {tr} tracks, ratsnest {rn}, {failed} nets unrouted")
for (net, p1, p2, reason) in g._unrouted[:40]:
    say(f"   UNROUTED {net}: {p1}->{p2}")
