"""Rev-5 routing pipeline. Runs on the TRACKLESS board from build_pcb.py.

Definitive pass order (every stage earned its position by a failure class):
  1. hand-bridges   - J7's D+/D- pad pairs (jailed between edge + NPTH posts)
  2. fan-out stubs  - U1/U2 fine-pitch signal pads reserve their exit lanes
  3. plane stitch   - GND/3V3/VM SMD pads get via+stub to their pours
  4. priority nets  - chip-attached long nets claim corridors while empty
  5. micro-bridges  - remaining same-net adjacent-pin bridges
  6. signals        - remaining nets, longest span first
  7. power class    - 0.5mm coarse-pad nets
  8. retry ladder   - 400k -> 0.25mm/1.2M -> 0.2mm/2M
  9. zone fill      - planes become DRC-real connectivity
"""
import sys, os, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_SLOTS, MOUNT_HOLES

BOARD = r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb"
NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"

g = PcbGen(NETLIST)
g.board = pcbnew.LoadBoard(BOARD)
ntr = len(list(g.board.GetTracks()))
if ntr:
    raise SystemExit(f"Board has {ntr} tracks -- run build_pcb.py first (track removal corrupts SWIG proxies).")
g.setup_design_rules()
g.LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]

g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
g._nets = {}
for code, ni in g.board.GetNetsByNetcode().items():
    if ni.GetNetname():
        g._nets[ni.GetNetname()] = ni

g._outline_pts = list(BOARD_OUTLINE)
g._extra_keepouts = []
for (sx1, sy1, sx2, sy2) in WHEEL_SLOTS:
    g._extra_keepouts.append((sx1 - 0.6, sy1 - 0.6, sx2 + 0.6, sy2 + 0.6))
for (hx, hy, hr) in MOUNT_HOLES:
    m = hr + 0.75
    g._extra_keepouts.append((hx - m, hy - m, hx + m, hy + m))

g._track_segs = []
g._vias = []
g._pads_geo_cache = None

CLR = 0.3            # no-inter-pin clearance (hand-solder rule)
POUR_NETS = ("GND", "PLUS3V3", "VM_BATT")
PRIORITY = ["WALL5_SENSE", "WALL4_SENSE", "WALL2_SENSE", "WALL3_SENSE",
            "WALL0_SENSE", "WALL1_SENSE",
            "LINE8_SENSE", "LINE7_SENSE", "MUX_SENSE", "LINE2_SENSE", "Net-(U1-L1)", "Net-(U1-L2)",
            "STBY", "PWMA", "PWMB", "AIN1", "AIN2", "BIN1", "BIN2",
            "ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B",
            "MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N",
            "USB_DM", "USB_DP", "USB_DM_C", "USB_DP_C",
            "Net-(J7-CC1)", "Net-(J7-CC2)", "USB_VBUS", "VBUS_SENSE",
            "WALL_EMIT_FRONT", "WALL_EMIT_DIAG", "WALL_EMIT_SIDE", "LINE_EMIT",
            "MUX_S0", "MUX_S1", "MUX_S2"]
all_net_names = set(g.pad_to_net.values())
skip = set(POUR_NETS)

t0 = time.time()

# ---- 1. hand-bridges: J7 D pairs (D+ = outer pair -> deep loop) ------------
for _net, (_pa, _pb) in (("USB_DP_C", ("A6", "B6")),):
    _ps = [pp for pp in g._pads_geo() if pp["ref"] == "J7" and pp["num"] in (_pa, _pb)]
    if len(_ps) != 2:
        continue
    _p1 = (_ps[0]["cx"], _ps[0]["cy"]); _p2 = (_ps[1]["cx"], _ps[1]["cy"])
    _yl = min(_p1[1], _p2[1]) - 2.6
    _cand = [(_p1, (_p1[0], _yl), pcbnew.F_Cu),
             ((_p1[0], _yl), (_p2[0], _yl), pcbnew.F_Cu),
             ((_p2[0], _yl), _p2, pcbnew.F_Cu)]
    fail = g._verify_geo(_cand, [], _net, 0.125)
    if fail is None:
        for (_a, _b, _l) in _cand:
            g.add_track(_a, _b, _l, _net, 0.25)
            g._track_segs.append((_a, _b, _net, 0.125, _l))
        print(f"hand-bridge {_net}: OK")
    else:
        print(f"hand-bridge {_net}: verify failed -- {fail}")

# ---- 1b. VBUS stack bridge: the two VBUS pad stacks flank the D/CC field,
# so no F.Cu path can exist between them. Drop a via at each stack and run
# B.Cu past the pad row -- depth ladder, first verified geometry wins.
_jx = pcbnew.ToMM(g._placed["J7"].GetPosition().x)
_stk = []
for _nums in (("A4", "B9"), ("A9", "B4")):
    _ps = [pp for pp in g._pads_geo() if pp["ref"] == "J7" and pp["num"] in _nums]
    if len(_ps) == 2:
        _stk.append(min(_ps, key=lambda p: abs(p["cx"] - _jx)))  # inner pad of stack
if len(_stk) == 2:
    _done = _fail = None
    for _dy in (-1.1, -1.4, 0.85, 1.05):
        _y = round(_stk[0]["cy"] + _dy, 3)
        _c1 = (_stk[0]["cx"], _stk[0]["cy"]); _c2 = (_stk[1]["cx"], _stk[1]["cy"])
        _v1 = (_c1[0], _y); _v2 = (_c2[0], _y)
        _segs = [(_c1, _v1, pcbnew.F_Cu), (_v1, _v2, pcbnew.In1_Cu), (_v2, _c2, pcbnew.F_Cu)]
        _fail = g._verify_geo(_segs, [_v1, _v2], "USB_VBUS", 0.125)
        if _fail is None:
            for (_a, _b, _l) in _segs:
                g.add_track(_a, _b, _l, "USB_VBUS", 0.25)
                g._track_segs.append((_a, _b, "USB_VBUS", 0.125, _l))
            g.add_via(_v1, "USB_VBUS"); g.add_via(_v2, "USB_VBUS")
            _done = _dy
            break
    if _done is not None:
        print(f"hand-bridge USB_VBUS: OK (In1, dy={_done})")
    else:
        print(f"hand-bridge USB_VBUS: no depth verified -- {_fail}")

# ---- 2. fan-out stubs for fine-pitch signal pads ---------------------------
n_fan, fan_bad = 0, []
for _ref in ("U1", "U2", "U3"):
    _fp = g._placed[_ref]
    _cx, _cy = pcbnew.ToMM(_fp.GetPosition().x), pcbnew.ToMM(_fp.GetPosition().y)
    for _pad in g._pads_geo():
        if _pad["ref"] != _ref or _pad["net"] in POUR_NETS or not _pad["net"]:
            continue
        _px, _py = _pad["cx"], _pad["cy"]
        _dx, _dy = _px - _cx, _py - _cy
        if abs(_dx) > abs(_dy):
            _dx, _dy = (1 if _dx > 0 else -1), 0
        else:
            _dx, _dy = 0, (1 if _dy > 0 else -1)
        _end = (round(_px + _dx * 1.4, 3), round(_py + _dy * 1.4, 3))
        _seg = [((_px, _py), _end, pcbnew.F_Cu)]
        if g._verify_geo(_seg, [], _pad["net"], 0.125) is None:
            g.add_track((_px, _py), _end, pcbnew.F_Cu, _pad["net"], 0.25)
            g._track_segs.append(((_px, _py), _end, _pad["net"], 0.125, pcbnew.F_Cu))
            n_fan += 1
        else:
            fan_bad.append(f"{_ref}.{_pad['num']}")
print(f"fanout stubs: {n_fan} ok, failed: {fan_bad}")

# ---- 2a. pre-stitch U2's east-column pour pads: the jailed control cluster
# is about to wall in the ring; these two vias must exist first.
import math as _m2
for (_ref, _num, _pn) in (("U6", "2", "GND"),
                          ("U2", "18", "GND"), ("U2", "20", "PLUS3V3"),
                          ("U2", "9", "GND"), ("U2", "10", "GND")):
    _ps = [pp for pp in g._pads_geo() if pp["ref"] == _ref and pp["num"] == _num]
    _pc = (_ps[0]["cx"], _ps[0]["cy"]) if _ps else None
    _fp2 = g._placed[_ref]
    _lay = pcbnew.B_Cu if _fp2.IsFlipped() else pcbnew.F_Cu
    # direction ladder aims TOWARD the body first: under-body space is the
    # one resource the signal routes never fight over
    _th0 = _m2.atan2(pcbnew.ToMM(_fp2.GetPosition().y) - _pc[1],
                     pcbnew.ToMM(_fp2.GetPosition().x) - _pc[0]) if _pc else 0.0
    def _adist(k, _t=_th0):
        d = abs(k * _m2.pi / 8 - _t) % (2 * _m2.pi)
        return min(d, 2 * _m2.pi - d)
    _ok = False
    for _d in ((0.8, 1.0, 1.25, 1.5, 1.8, 2.2, 2.6) if _pc else ()):
        for _k in sorted(range(16), key=_adist):
            _th = _k * _m2.pi / 8
            _v = (round(_pc[0] + _d * _m2.cos(_th), 3), round(_pc[1] + _d * _m2.sin(_th), 3))
            if g._verify_geo([(_pc, _v, _lay)], [_v], _pn, 0.125) is None:
                g.add_track(_pc, _v, _lay, _pn, 0.25)
                g._track_segs.append((_pc, _v, _pn, 0.125, _lay))
                g.add_via(_v, _pn)
                _ok = True
                break
        if _ok:
            break
    print(f"pre-stitch {_ref}.{_num} -> {_pn}: {'OK' if _ok else 'FAILED'}")

# ---- 2b. jailed-first nets (most-constrained regions claim space first) ----
JAILED = ["Net-(J7-CC1)", "Net-(J7-CC2)", "USB_DM_C", "USB_DP_C",
          "USB_DM", "USB_DP", "Net-(R59-Pad1)", "Net-(R60-Pad1)",
          "USB_VBUS", "VBUS_SENSE",
          "AIN1", "AIN2", "BIN2", "BIN1", "STBY", "PWMB", "PWMA"]

def drain_jailed_ladder():
    # A jailed net that fails the cheap first try gets its FULL retry ladder
    # IMMEDIATELY, while the board is emptiest -- letting it wait for the
    # global ladders (board full by then) is what kept the two dense pockets
    # in whack-a-mole for seven iterations.
    prev, g._unrouted[:] = list(g._unrouted), []
    for (net, p1, p2, reason) in prev:
        if (g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=CLR,
                         max_expansions=400000)
                or g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=0.4,
                                grid_mm=0.25, max_expansions=1200000)
                or g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=CLR,
                                grid_mm=0.25, max_expansions=1200000)
                or g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=CLR,
                                grid_mm=0.2, max_expansions=2000000)
                or g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=0.18,
                                grid_mm=0.2, max_expansions=2000000)):
            continue
        g._unrouted.append((net, p1, p2, reason))

for _n in JAILED:
    if _n in all_net_names:
        _before = len(g._unrouted)
        g.route_net(_n, width_mm=0.3, clearance_mm=CLR, max_expansions=400000)
        if len(g._unrouted) > _before:
            drain_jailed_ladder()
print(f"[{time.time()-t0:.0f}s] jailed-first done, {len(g._unrouted)} fails")
skip |= set(JAILED)

# ---- 3. plane stitching (+ routed fallback) --------------------------------
for _pn in POUR_NETS:
    _fails = g.stitch_net_to_plane(_pn)
    if _fails:
        _still = []
        for _f in _fails:
            _ref, _num = _f.rsplit(".", 1)
            _pads = [pp for pp in g._pads_geo() if pp["ref"] == _ref and pp["num"] == _num]
            if not _pads:
                _still.append(_f); continue
            _pc = (_pads[0]["cx"], _pads[0]["cy"])
            _vias = [(vx, vy) for (vx, vy, vn, vr) in g._vias if vn == _pn]
            _vias.sort(key=lambda v: (v[0]-_pc[0])**2 + (v[1]-_pc[1])**2)
            if not any(g.retry_edge(_pn, _pc, _v, width_mm=0.3, clearance_mm=CLR,
                                    grid_mm=0.25, max_expansions=400000) for _v in _vias[:6]):
                _still.append(_f)
        _fails = _still
    print(f"stitch {_pn}: {'OK' if not _fails else 'FAILED for ' + ', '.join(_fails)}")

# ---- 4. priority nets (chip-attached, corridor-hungry) ---------------------
for _n in PRIORITY:
    if _n in all_net_names and _n not in skip:
        g.route_net(_n, width_mm=0.3, clearance_mm=CLR, max_expansions=200000)
print(f"[{time.time()-t0:.0f}s] priority done, {len(g._unrouted)} fails")
skip |= set(PRIORITY)

# ---- 5-7. remaining nets ---------------------------------------------------
POWER = {"Net-(J1-Pin_1)", "Net-(J2-Pin_2)", "Net-(F1-Pad2)"}
POWER |= {n for n in all_net_names if n.startswith("EMIT_")}

def span(net):
    pads = [p for p in g._pads_geo() if p["net"] == net]
    if len(pads) < 2:
        return 0
    xs = [p["cx"] for p in pads]; ys = [p["cy"] for p in pads]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))

rest = sorted(all_net_names - skip - POWER)
for n in sorted(all_net_names - skip):
    g.route_net(n, width_mm=0.3, clearance_mm=CLR, max_edge_mm=2.2, max_expansions=80000)
print(f"[{time.time()-t0:.0f}s] micro-bridges done, {len(g._unrouted)} fails")
for n in sorted(rest, key=span, reverse=True):
    g.route_net(n, width_mm=0.3, clearance_mm=CLR, min_edge_mm=2.2, max_expansions=80000)
print(f"[{time.time()-t0:.0f}s] signals done, {len(g._unrouted)} fails")
for n in POWER:
    if n in all_net_names:
        g.route_net(n, width_mm=0.5, clearance_mm=CLR, min_edge_mm=2.2, max_expansions=80000)
print(f"[{time.time()-t0:.0f}s] power done, {len(g._unrouted)} fails")

# ---- 8. retry ladder -------------------------------------------------------
def width_for(net):
    return 0.5 if net in POWER else 0.3

still = []
for (net, p1, p2, reason) in g._unrouted:
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=CLR,
                        max_expansions=400000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] retry done, {len(still)} left")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=0.4,
                        grid_mm=0.25, max_expansions=1200000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] wide retry done, {len(still)} left")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=CLR,
                        grid_mm=0.25, max_expansions=1200000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] fine retry done, {len(still)} left")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=CLR,
                        grid_mm=0.2, max_expansions=2000000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] ultra retry done, {len(still)} left")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    # SMD-relief: obstacle clearance 0.18 (SMD-dense jails); THT pads keep
    # their 0.3 floor through _verify_geo's default -- the hand-solder rule
    # is untouched.
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=0.18,
                        grid_mm=0.2, max_expansions=2000000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] SMD-relief retry done, {len(still)} left")

# ---- 9. fill + save + report -----------------------------------------------
print("zone fill:", g.fill_zones())
pcbnew.SaveBoard(BOARD, g.board)
tr = sum(1 for t in g.board.GetTracks() if t.GetClass() == "PCB_TRACK")
vi = sum(1 for t in g.board.GetTracks() if t.GetClass() == "PCB_VIA")
print(f"Routed in {time.time()-t0:.0f}s. Board now has {tr} tracks, {vi} vias.")
print(f"Unrouted edges remaining: {len(still)}")
for (net, p1, p2, reason) in still[:40]:
    print(f"   {net}: {reason}  [{p1[0]:.1f},{p1[1]:.1f} -> {p2[0]:.1f},{p2[1]:.1f}]")
