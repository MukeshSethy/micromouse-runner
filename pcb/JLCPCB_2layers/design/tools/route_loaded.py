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
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BOARD = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\micromouse-pcb.kicad_pcb"
NETLIST = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\netlist.net"

g = PcbGen(NETLIST)
g.board = pcbnew.LoadBoard(BOARD)
ntr = len(list(g.board.GetTracks()))
if ntr:
    raise SystemExit(f"Board has {ntr} tracks -- run build_pcb.py first (track removal corrupts SWIG proxies).")
g.setup_design_rules()
g.LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]   # 2-layer: outer copper only (F horiz-pref, B vert-pref)

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

g._track_segs = []
g._vias = []
g._pads_geo_cache = None

CLR = 0.3            # no-inter-pin clearance (hand-solder rule)
# 2-layer: ONLY GND is poured (both outer faces). The 3V3 + motor/battery rails
# have no inner plane here, so they route as wide track trees (stage 3c below).
POUR_NETS = ("GND",)
# Power rails routed as wide tracks (IPC-2152 outer-layer, 20 degC rise):
#   VM_BATT 1.0mm (~3-4A pack feed to both bucks), VM_6V 0.9mm (3A motor rail),
#   PLUS3V3 0.6mm (2A logic), switch nodes/VBUS lighter.
RAIL_W = {"VM_BATT": 1.0, "VM_6V": 0.9, "PLUS3V3": 0.6,
          "SW_3V3": 0.4, "SW_6V": 0.4, "USB_VBUS": 0.5}
PRIORITY = ["VBAT_SENSE", "BAT_MID_SENSE", "BAT_MID", "PWR_EN", "MOT_EN",
            "USER_BTN2", "USER_BTN3", "MOTB_N",
            "MUX_S1", "MUX_S2", "MUX_S0", "MUX_S3",
            "WALL5_SENSE", "WALL6_SENSE", "WALL3_SENSE", "WALL4_SENSE",
            "WALL1_SENSE", "WALL2_SENSE",
            "LINE8_SENSE", "LINE7_SENSE", "MUX_SENSE", "LINE2_SENSE",
            "SW_3V3", "SW_6V", "FB_6V",
            "IMU_SDA", "IMU_SCL", "IMU_INT",
            "AIN1", "AIN2", "BIN1", "BIN2",
            "ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B",
            "MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N",
            "USB_DM", "USB_DP", "USB_DM_C", "USB_DP_C",
            "Net-(J7-CC1)", "Net-(J7-CC2)", "USB_VBUS", "VBUS_SENSE",
            "WALL_EMIT_FRONT", "WALL_EMIT_DIAG", "WALL_EMIT_SIDE", "LINE_EMIT"]
all_net_names = set(g.pad_to_net.values())
skip = set(POUR_NETS)

t0 = time.time()

def _ck(tag):
    pcbnew.SaveBoard(BOARD, g.board)
    print(f'  [checkpoint: {tag}]')

# ---- 1. USB-C same-signal pad-pair bridges (robust, layer-diverse) ---------
# The USB4105 interleaves the A/B rows: along +x the D-/D+/CC/VBUS pads
# alternate, so a same-net pair (D- A7&B7, D+ A6&B6, VBUS A4/B9 & A9/B4) is
# separated by the OTHER pair's pads and must bridge UNDER them. Strategy:
# 1a route CC1/CC2 on an inner layer FIRST (frees the F.Cu south of the pads),
# 1b then dive each pair on its own inner layer (D- on B.Cu, D+ on In2, VBUS
#    columns joined on In2) so no two bridges share a layer where they cross.
def _jpad(num):
    ps = [pp for pp in g._pads_geo() if pp["ref"] == "J7" and pp["num"] == num]
    return (ps[0]["cx"], ps[0]["cy"]) if ps else None

def _bridge(net, na, nb, layer, depths):
    p1, p2 = _jpad(na), _jpad(nb)
    if not p1 or not p2:
        print(f"bridge {net}: pads {na}/{nb} not found"); return False
    inward = -1 if (120 - max(p1[1], p2[1])) >= min(p1[1], p2[1]) else 1
    for d in depths:
        yd = round(min(p1[1], p2[1]) + inward * d if inward < 0 else max(p1[1], p2[1]) + d, 3)
        v1, v2 = (p1[0], yd), (p2[0], yd)
        segs = [(p1, v1, pcbnew.F_Cu), (v1, v2, layer), (v2, p2, pcbnew.F_Cu)]
        if g._verify_geo(segs, [v1, v2], net, 0.125) is None:
            for (a, b, l) in segs:
                g.add_track(a, b, l, net, 0.25)
                g._track_segs.append((a, b, net, 0.125, l))
            g.add_via(v1, net); g.add_via(v2, net)
            g._vias.append((v1[0], v1[1], net, 0.3)); g._vias.append((v2[0], v2[1], net, 0.3))
            print(f"bridge {net} ({na}<->{nb}): OK on {g.board.GetLayerName(layer)} @ d={d}")
            return True
    print(f"bridge {net}: all depths blocked")
    return False

# 1a. CC pads dive to In1... In1 is GND -> use B.Cu; run to the CC resistors.
for _ccnet, _ccpad in (("Net-(J7-CC1)", "A5"), ("Net-(J7-CC2)", "B5")):
    _p = _jpad(_ccpad)
    if _p:
        for _d in (0.9, 1.1, 1.3, 0.7):
            _v = (_p[0], round(_p[1] - _d if (120 - _p[1]) >= _p[1] else _p[1] + _d, 3))
            if g._verify_geo([(_p, _v, pcbnew.F_Cu)], [_v], _ccnet, 0.125) is None:
                g.add_track(_p, _v, pcbnew.F_Cu, _ccnet, 0.25)
                g._track_segs.append((_p, _v, _ccnet, 0.125, pcbnew.F_Cu))
                g.add_via(_v, _ccnet); g._vias.append((_v[0], _v[1], _ccnet, 0.3))
                print(f"CC escape {_ccnet}: via {_v}")
                break
# 1b. D-/D+/VBUS pair bridges. 2-layer: the only dive layer is B.Cu, so each
# bridge uses a DIFFERENT y-depth ladder to stagger under the pad field and not
# collide; anything blocked here falls to the JAILED ladder below and reroutes.
_bridge("USB_DM_C", "A7", "B7", pcbnew.B_Cu, (1.0, 1.2, 1.4, 0.8, 1.6))
_bridge("USB_DP_C", "A6", "B6", pcbnew.B_Cu, (1.1, 1.3, 1.5, 0.9, 1.7))
_bridge("USB_VBUS", "A4", "A9", pcbnew.B_Cu, (1.3, 1.5, 1.1, 1.7))
_bridge("USB_VBUS", "B9", "B4", pcbnew.B_Cu, (1.6, 1.8, 1.4, 2.0))

# ---- 2. fan-out stubs for fine-pitch signal pads ---------------------------
n_fan, fan_bad = 0, []
for _ref in ("U1", "U2", "U3", "U7", "U8"):
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
        _stub, _wid = (0.8, 0.2) if _ref == "U8" else (1.4, 0.25)
        _end = (round(_px + _dx * _stub, 3), round(_py + _dy * _stub, 3))
        _seg = [((_px, _py), _end, pcbnew.F_Cu)]
        if g._verify_geo(_seg, [], _pad["net"], _wid / 2) is None:
            g.add_track((_px, _py), _end, pcbnew.F_Cu, _pad["net"], _wid)
            g._track_segs.append(((_px, _py), _end, _pad["net"], _wid / 2, pcbnew.F_Cu))
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
          "USB_DM", "USB_DP",
          "USB_VBUS", "VBUS_SENSE",
          "AIN1", "AIN2", "BIN1", "BIN2",
          "WALL1_SENSE", "WALL2_SENSE", "WALL3_SENSE", "WALL4_SENSE",
          "WALL5_SENSE", "WALL6_SENSE",
          "Net-(D1-A)", "Net-(D2-A)", "Net-(D3-A)", "Net-(D4-A)",
          "Net-(D5-A)", "Net-(D6-A)",
          "Net-(LS1-Pad1)", "Net-(LS2-Pad1)", "Net-(LS3-Pad1)", "Net-(LS4-Pad1)",
          "Net-(LS5-Pad1)", "Net-(LS6-Pad1)", "Net-(LS7-Pad1)", "Net-(LS8-Pad1)",
          "EMIT_FRONT_K", "EMIT_DIAG_K", "EMIT_SIDE_K", "EMIT_LINE_K",
          "SW_3V3", "SW_6V", "FB_6V", "ENC1_B", "ENC1_A",
          "JTAG_TMS", "JTAG_TCK", "JTAG_TDO", "JTAG_TDI",
          "IMU_SDA", "IMU_SCL", "IMU_INT"]

def drain_jailed_ladder():
    # A jailed net that fails the cheap first try gets its FULL retry ladder
    # IMMEDIATELY, while the board is emptiest -- letting it wait for the
    # global ladders (board full by then) is what kept the two dense pockets
    # in whack-a-mole for seven iterations.
    prev, g._unrouted[:] = list(g._unrouted), []
    for (net, p1, p2, reason) in prev:
        _short = math.hypot(p2[0] - p1[0], p2[1] - p1[1]) < 24.0
        if (g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=CLR,
                         max_expansions=400000)
                # short edges (the front-band hole-picket hops) resolve at
                # 0.1 grid quickly -- try it SECOND, not sixth: this cut the
                # jailed stage from hours to minutes
                or (_short and g.retry_edge(net, p1, p2, width_mm=0.25,
                                            clearance_mm=0.18, grid_mm=0.1,
                                            max_expansions=800000))
                or g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=0.4,
                                grid_mm=0.25, max_expansions=500000)
                or g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=CLR,
                                grid_mm=0.25, max_expansions=500000)
                or g.retry_edge(net, p1, p2, width_mm=0.3, clearance_mm=0.18,
                                grid_mm=0.2, max_expansions=800000)
                or (math.hypot(p2[0] - p1[0], p2[1] - p1[1]) < 24.0
                    and g.retry_edge(net, p1, p2, width_mm=0.25, clearance_mm=0.18,
                                     grid_mm=0.1, max_expansions=600000))):
            continue
        g._unrouted.append((net, p1, p2, reason))

for _n in JAILED:
    if _n in all_net_names:
        _tn = time.time()
        _before = len(g._unrouted)
        g.route_net(_n, width_mm=0.3, clearance_mm=CLR, max_expansions=400000)
        _drained = ""
        if len(g._unrouted) > _before:
            drain_jailed_ladder()
            _drained = " (drained)"
        print(f"  jailed {_n}: {time.time()-_tn:.0f}s{_drained}, {len(g._unrouted)} fails so far")
print(f"[{time.time()-t0:.0f}s] jailed-first done, {len(g._unrouted)} fails")
_ck("jailed-first done")
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

# ---- 3b. power nets first at full width: the battery feed's only corridor
# past the wheel notch + bracket holes is ~1.4mm wide -- it must claim it
# before the signal crowd does.
POWER = {"BATT_RAW", "Net-(Q1-D)"}
for _n in sorted(POWER):
    if _n in all_net_names:
        g.route_net(_n, width_mm=0.8, clearance_mm=CLR, max_expansions=400000)
# motor phases at 0.8mm while the board is empty (IPC-2152: >=0.8 outer for
# the 1.6A stall peaks); ladder fallbacks may relax width later if jailed
for _n in ("MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"):
    if _n in all_net_names:
        g.route_net(_n, width_mm=0.8, clearance_mm=CLR, max_expansions=400000)
skip |= {"MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"}
print(f"[{time.time()-t0:.0f}s] early power done, {len(g._unrouted)} fails")
_ck("early power done")
skip |= POWER

# ---- 3c. 2-layer power rails as wide track trees (no inner plane) -----------
# Route the rails while the board is still mostly empty so their wide corridors
# get first claim. Widest first (VM_BATT), then VM_6V, 3V3, switch nodes/VBUS.
for _n in sorted(RAIL_W, key=lambda k: -RAIL_W[k]):
    if _n in all_net_names and _n not in skip:
        _before = len(g._unrouted)
        g.route_net(_n, width_mm=RAIL_W[_n], clearance_mm=CLR, max_expansions=600000)
        # a rail edge that missed at full width: retry narrower before moving on
        if len(g._unrouted) > _before:
            _pend, g._unrouted[:] = list(g._unrouted), []
            for (net, p1, p2, reason) in _pend:
                if net == _n and g.retry_edge(net, p1, p2, width_mm=max(0.4, RAIL_W[_n]-0.3),
                                              clearance_mm=CLR, grid_mm=0.25, max_expansions=800000):
                    continue
                g._unrouted.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] power rails done, {len(g._unrouted)} fails")
_ck("power rails done")
skip |= set(RAIL_W)

# ---- 4. priority nets (chip-attached, corridor-hungry) ---------------------
for _n in PRIORITY:
    if _n in all_net_names and _n not in skip:
        g.route_net(_n, width_mm=0.3, clearance_mm=CLR, max_expansions=200000)
print(f"[{time.time()-t0:.0f}s] priority done, {len(g._unrouted)} fails")
_ck("priority done")
skip |= set(PRIORITY)

# ---- 5-7. remaining nets ---------------------------------------------------

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
_ck("micro-bridges done")
for n in sorted(rest, key=span, reverse=True):
    g.route_net(n, width_mm=0.3, clearance_mm=CLR, min_edge_mm=2.2, max_expansions=80000)
print(f"[{time.time()-t0:.0f}s] signals done, {len(g._unrouted)} fails")
_ck("signals done")
print(f"[{time.time()-t0:.0f}s] power done earlier (stage 3b)")

# ---- 8. retry ladder -------------------------------------------------------
def width_for(net):
    if net in POWER:
        return 0.8
    if net in RAIL_W:
        return max(0.4, RAIL_W[net] - 0.3)   # rails may relax in the retry ladder
    if net in ("MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"):
        return 0.5
    return 0.3

still = []
for (net, p1, p2, reason) in g._unrouted:
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=CLR,
                        max_expansions=400000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] retry done, {len(still)} left")
_ck("retry done")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=0.4,
                        grid_mm=0.25, max_expansions=700000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] wide retry done, {len(still)} left")
_ck("wide retry done")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=CLR,
                        grid_mm=0.25, max_expansions=700000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] fine retry done, {len(still)} left")
_ck("fine retry done")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=CLR,
                        grid_mm=0.2, max_expansions=600000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] ultra retry done, {len(still)} left")
_ck("ultra retry done")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    # SMD-relief: obstacle clearance 0.18 (SMD-dense jails); THT pads keep
    # their 0.3 floor through _verify_geo's default -- the hand-solder rule
    # is untouched.
    if not g.retry_edge(net, p1, p2, width_mm=width_for(net), clearance_mm=0.18,
                        grid_mm=0.2, max_expansions=600000):
        still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] SMD-relief retry done, {len(still)} left")
_ck("SMD-relief retry done")
prev, still = still, []
for (net, p1, p2, reason) in prev:
    # 0.1-grid micro rung, short edges only (fine-pitch weaves need it; long
    # edges would blow the expansion budget)
    if (math.hypot(p2[0] - p1[0], p2[1] - p1[1]) < 24.0
            and g.retry_edge(net, p1, p2, width_mm=0.25, clearance_mm=0.18,
                             grid_mm=0.1, max_expansions=600000)):
        continue
    still.append((net, p1, p2, reason))
print(f"[{time.time()-t0:.0f}s] micro retry done, {len(still)} left")
_ck("micro retry done")

# ---- 9. fill + save + report -----------------------------------------------
print("zone fill:", g.fill_zones())
pcbnew.SaveBoard(BOARD, g.board)
tr = sum(1 for t in g.board.GetTracks() if t.GetClass() == "PCB_TRACK")
vi = sum(1 for t in g.board.GetTracks() if t.GetClass() == "PCB_VIA")
print(f"Routed in {time.time()-t0:.0f}s. Board now has {tr} tracks, {vi} vias.")
print(f"Unrouted edges remaining: {len(still)}")
for (net, p1, p2, reason) in still[:40]:
    print(f"   {net}: {reason}  [{p1[0]:.1f},{p1[1]:.1f} -> {p2[0]:.1f},{p2[1]:.1f}]")
