"""Pre-route the hard U3-escape nets on the EMPTY board, then export a DSN for
Freerouting to route everything else around them. These nets (AIN/BIN motor
control to U2, RGB_DATA to the front) all funnel out of U3's congested top edge
and are the recurring Freerouting residual; laying them first on a clear board
guarantees a path (same trick that fixed BATT_RAW)."""
import sys, os, runpy
DES = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design"
sys.path.insert(0, os.path.join(DES, "tools"))
import pcbnew
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES, MOTOR_KEEPOUTS

BOARD = os.path.join(DES, "micromouse-pcb.kicad_pcb")
DSN = os.path.join(DES, "micromouse-pcb.dsn")

ns = runpy.run_path(os.path.join(DES, "tools", "build_pcb.py"))
g = ns["g"]
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
g._track_segs, g._vias, g._pads_geo_cache = [], [], None

# antenna-notch strip keepout (same as the clean export)
g._extra_keepouts.append((38.0, 113.35, 62.0, 113.85))
g.add_keepout((38.0, 113.35, 62.0, 113.85), allow_tracks=False, allow_footprints=True)

# ---- USER: use the TOP layer + GND pour in the MOTOR BAYS. The motor keepout
# zones are F.Cu rule-areas (for component PLACEMENT only -- placement is fixed);
# Freerouting reads them as a top-layer block, so it routes only the bottom under
# the motors. Remove them so the top motor-bay space is used AND the top GND pour
# fills there (motors sit on standoffs -> top copper under them is fine). Keep the
# antenna-notch keepout (y~113). ----
_rm = 0
for _z in list(g.board.Zones()):
    if _z.GetIsRuleArea():
        _bb = _z.GetBoundingBox()
        _cy = (pcbnew.ToMM(_bb.GetTop()) + pcbnew.ToMM(_bb.GetBottom())) / 2
        if 70 < _cy < 100:                 # motor-bay keepouts (motors at y=84)
            g.board.Remove(_z); _rm += 1
g._extra_keepouts = [k for k in g._extra_keepouts if not (70 < (k[1] + k[3]) / 2 < 100)]
print("removed %d motor-bay keepout zones -> top routing + top pour enabled" % _rm, flush=True)

# ---- pre-route the hard U3-escape nets on the empty board ----
for _net in ("RGB_DATA", "BIN2", "BIN1", "AIN2", "AIN1"):   # longest first
    g._unrouted = []
    try:
        g.route_net(_net, width_mm=0.25, clearance_mm=0.2, max_expansions=400000)
        print("%s pre-route: unrouted-edges left = %d" % (_net, len(g._unrouted)), flush=True)
    except Exception as e:
        print("%s pre-route error: %s" % (_net, e), flush=True)

g.save(BOARD)   # true-edge board (for SES import)

# 0.15mm inset boundary for the DSN only
outl = pcbnew.SHAPE_POLY_SET()
g.board.GetBoardPolygonOutlines(outl, True)
outl.Inflate(pcbnew.FromMM(-0.15), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, pcbnew.FromMM(0.005))
for _d in list(g.board.GetDrawings()):
    if _d.GetLayer() == pcbnew.Edge_Cuts:
        g.board.Remove(_d)
for _oi in range(outl.OutlineCount()):
    _ch = outl.Outline(_oi); _n = _ch.PointCount()
    for _i in range(_n):
        _a = _ch.CPoint(_i); _c = _ch.CPoint((_i + 1) % _n)
        _seg = pcbnew.PCB_SHAPE(g.board, pcbnew.SHAPE_T_SEGMENT)
        _seg.SetStart(pcbnew.VECTOR2I(_a.x, _a.y)); _seg.SetEnd(pcbnew.VECTOR2I(_c.x, _c.y))
        _seg.SetLayer(pcbnew.Edge_Cuts); _seg.SetWidth(pcbnew.FromMM(0.1)); g.board.Add(_seg)
ok = pcbnew.ExportSpecctraDSN(g.board, DSN)
print("hard-preroute DSN export:", ok, flush=True)
os._exit(0)
