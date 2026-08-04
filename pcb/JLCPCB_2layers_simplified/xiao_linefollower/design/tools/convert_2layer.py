"""2-LAYER CONVERSION for the xiao_linefollower board -- built on the pipeline
that closed the main micromouse 2-layer board (Freerouting was never tried on
this board's 2-layer; only the in-house A* was, before the 4-layer escape).

Works on a COPY (micromouse-pcb-simplified-2l.kicad_pcb); the finalized
4-layer board is untouched.

Steps here (routing itself runs separately):
  1. copy the board, strip ALL tracks + vias, SetCopperLayerCount(2)
  2. relax any F.Cu track-blocking keepouts over the motor bays (motors sit on
     standoffs; top copper under them is fine -- proven on the main board)
  3. save the TRUE-edge 2L board (SES imports onto this)
  4. inset Edge.Cuts 0.15mm on a scratch copy of the outline (DSN only) so
     Freerouting's 0.15mm boundary clearance = 0.30mm from the real edge
  5. ExportSpecctraDSN + power-class surgery:
       power    (BATT_RAW VM_BATT VM_6V SW_6V)          500um
       power3v3 (PLUS3V3 SW_3V3)                        400um
       motor    (MOTA_P MOTA_N MOTB_P MOTB_N)           400um
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
DST = os.path.join(BASE, "micromouse-pcb-simplified-2l.kicad_pcb")
DSN = os.path.join(BASE, "micromouse-pcb-simplified-2l.dsn")

# Phase split (SWIG heap degrades after bulk Remove -- crash-isolate): run
#   convert_2layer.py strip   -> copy + strip + 2-layer + save + hard-exit
#   convert_2layer.py dsn     -> fresh load: keepouts + inset DSN + classes
PHASE = sys.argv[1] if len(sys.argv) > 1 else "strip"

if PHASE == "strip":
    import shutil
    shutil.copyfile(SRC, DST)
    b = pcbnew.LoadBoard(DST)
    n_t = n_v = 0
    for t in list(b.GetTracks()):
        if t.GetClass() == "PCB_VIA":
            n_v += 1
        else:
            n_t += 1
        b.Remove(t)
    b.SetCopperLayerCount(2)
    pcbnew.SaveBoard(DST, b)
    print("stripped %d track segments + %d vias; copper layers -> 2" % (n_t, n_v), flush=True)
    os._exit(0)

b = pcbnew.LoadBoard(DST)

# 2. motor-bay keepouts: permit tracks+vias (keep them as component keepouts)
relaxed = 0
for z in b.Zones():
    if z.GetIsRuleArea() and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
        bb = z.GetBoundingBox()
        cy = (pcbnew.ToMM(bb.GetTop()) + pcbnew.ToMM(bb.GetBottom())) / 2
        cx = (pcbnew.ToMM(bb.GetLeft()) + pcbnew.ToMM(bb.GetRight())) / 2
        w = pcbnew.ToMM(bb.GetWidth())
        # motor bays sit mid-board (y ~70-100, wide); keep any small strip
        # keepouts (antenna etc.) intact
        if 65 < cy < 105 and w > 15:
            z.SetDoNotAllowTracks(False)
            z.SetDoNotAllowVias(False)
            relaxed += 1
print("relaxed %d motor-bay keepouts (tracks/vias allowed; parts still barred)" % relaxed, flush=True)

# 3. save the true-edge board
pcbnew.SaveBoard(DST, b)

# 4. inset Edge.Cuts for the DSN only. Extract the inset chains to PLAIN
# int coordinates BEFORE any board mutation -- SHAPE_POLY_SET proxies degrade
# to method-less SwigPyObjects once the board is touched (observed here on
# Outline() right after Remove(); same corruption family as the bulk-strip).
outl = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outl, True)
outl.Inflate(pcbnew.FromMM(-0.15), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, pcbnew.FromMM(0.005))
chains = []
for oi in range(outl.OutlineCount()):
    ch = outl.Outline(oi)
    chains.append([(ch.CPoint(i).x, ch.CPoint(i).y) for i in range(ch.PointCount())])
for d in list(b.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        b.Remove(d)
for pts in chains:
    n = len(pts)
    for i in range(n):
        a, c = pts[i], pts[(i + 1) % n]
        seg = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I(a[0], a[1]))
        seg.SetEnd(pcbnew.VECTOR2I(c[0], c[1]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        b.Add(seg)
ok = pcbnew.ExportSpecctraDSN(b, DSN)
# inject DSN keepouts at KiCad-vs-Freerouting marginal spots (r8: BIN1 routed
# 0.15-0.2 from L1 pad 2 -- legal per DSN pad shape, illegal per KiCad DRC).
# DSN frame: um, y negated. 0.65mm half-box on both copper layers.
_spots_mm = [(35.2, 95.4)]                     # L1 pad 2 flank
_ktxt = ""
for (_sx, _sy) in _spots_mm:
    x0, x1 = int((_sx - 0.65) * 1000), int((_sx + 0.65) * 1000)
    y0, y1 = int(-(_sy - 0.65) * 1000), int(-(_sy + 0.65) * 1000)
    for _lay in ("F.Cu", "B.Cu"):
        _ktxt += ("
    (keepout \"ko_%s_%d_%d\" (polygon %s 0  %d %d  %d %d  %d %d  %d %d))"
                  % (_lay.replace(".", ""), x0, -y0, _lay, x0, y0, x1, y0, x1, y1, x0, y1))
_d = open(DSN, encoding="utf-8").read()
_i = _d.index("(structure")
# find the end of the (structure ...) block and insert keepouts before it
_depth = 0; _j = _i
while True:
    if _d[_j] == "(": _depth += 1
    elif _d[_j] == ")":
        _depth -= 1
        if _depth == 0: break
    _j += 1
_d = _d[:_j] + _ktxt + "
  " + _d[_j:]
open(DSN, "w", encoding="utf-8", newline="
").write(_d)
print("injected %d DSN keepouts" % (2 * len(_spots_mm)), flush=True)
print("DSN export (inset boundary):", ok, flush=True)

# 5. power-class surgery on the DSN
POWER = ["BATT_RAW", "VM_BATT", "VM_6V", "SW_6V"]
POWER3 = ["PLUS3V3", "SW_3V3"]
MOTOR = ["MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"]
s = open(DSN, encoding="utf-8").read()
# board DRC min clearance is 0.2mm but KiCad exports the 0.15mm netclass into
# the DSN rule -- Freerouting then routes legally-per-DSN but DRC-illegal.
# Raise the routing rule to 200um (the smd_smd sub-rule may stay tighter).
s = re.sub(r"\(clearance 15\d(\.\d+)?", "(clearance 200", s)  # incl type-scoped subrules
i = s.index("(class kicad_default")
depth = 0
j = i
while True:
    if s[j] == "(":
        depth += 1
    elif s[j] == ")":
        depth -= 1
        if depth == 0:
            break
    j += 1
block = s[i:j + 1]
inner_at = block.index("(circuit")
header, inner = block[:inner_at], block[inner_at:-1]
for net in POWER + POWER3 + MOTOR:
    header = re.sub(r'(?<=[\s])%s(?=[\s])' % re.escape(net), " ", header)
header = re.sub(r"[ \t]+", " ", header)


def mkclass(name, nets, width):
    rule_inner = re.sub(r"\(width [0-9.]+\)", "(width %d)" % width, inner.strip())
    return "(class %s %s\n      %s\n    )" % (name, " ".join(nets), rule_inner)


s = (s[:i] + header + "\n      " + inner.strip() + "\n    )"
     + "\n    " + mkclass("power", POWER, 500)
     + "\n    " + mkclass("power3v3", POWER3, 400)
     + "\n    " + mkclass("motor", MOTOR, 400)
     + s[j + 1:])
open(DSN, "w", encoding="utf-8", newline="\n").write(s)
chk = open(DSN, encoding="utf-8").read()
print("power classes in DSN:",
      bool(re.search(r"\(class power .*?\(width 500\)", chk, re.S)),
      bool(re.search(r"\(class power3v3 .*?\(width 400\)", chk, re.S)),
      bool(re.search(r"\(class motor .*?\(width 400\)", chk, re.S)), flush=True)
os._exit(0)
