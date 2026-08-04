"""Production export for the 2-LAYER variant (micromouse-pcb-simplified-2l).

Builds xiao_linefollower/production_2layer/{jlcpcb,lioncircuits}/ -- a sibling
of production/ (which remains the 4-layer snapshot) -- by re-driving the
existing exporters with their module constants repointed:

  1. fresh BOM from the (simplified) schematic -- same kicad-cli flags +
     (Footprint,MPN) re-merge as export_fab.py
  2. kicad-cli gerbers (9 2-layer layers) + Excellon drill into design/fab_2l/
     with the same content gates as export_fab (layer count, NPTH tools)
  3. gen_jlc_positions / gen_lion_positions on the -2l board (body-center +
     JLC rotation corrections)
  4. export_jlcpcb.main() / export_lion.main() with FAB/OUT repointed
  5. zips renamed -2L- so they can never be confused with the 4-layer package

Run with KiCad's bundled python (pcbnew needed by the position generators).
"""
import csv
import os
import re
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
BASE = os.path.normpath(os.path.join(TOOLS, ".."))
ROOT = os.path.normpath(os.path.join(BASE, ".."))          # xiao_linefollower/
PCB2L = os.path.join(BASE, "micromouse-pcb-simplified-2l.kicad_pcb")
SCH = os.path.join(BASE, "micromouse-pcb-simplified.kicad_sch")
FAB2 = os.path.join(BASE, "fab_2l")
OUT2 = os.path.join(ROOT, "production_2layer")
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
LAYERS = ("F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,"
          "F.Mask,B.Mask,Edge.Cuts")

fails = []


def run(args, what):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        fails.append("%s: exit %d: %s" % (what, r.returncode,
                                          ((r.stdout or "") + (r.stderr or ""))[-300:]))
    return r


import shutil
shutil.rmtree(FAB2, ignore_errors=True)
os.makedirs(os.path.join(FAB2, "gerbers"))
os.makedirs(os.path.join(FAB2, "drill"))

# ---- 1. BOM (fresh, from the simplified schematic) ---------------------------
bom_path = os.path.join(BASE, "BOM.csv")
run([CLI, "sch", "export", "bom",
     "--fields", "Reference,Value,Footprint,${QUANTITY},MPN,Manufacturer",
     "--labels", "Reference,Value,Footprint,Qty,MPN,Manufacturer",
     "--group-by", "Value,Footprint,MPN",
     "--exclude-dnp", "--output", bom_path, SCH], "bom")


def _expand(s):
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        m = re.match(r"([A-Za-z]+)(\d+)-([A-Za-z]*)(\d+)$", tok)
        if m:
            out += ["%s%d" % (m.group(1), n)
                    for n in range(int(m.group(2)), int(m.group(4)) + 1)]
        else:
            out.append(tok)
    return out


rows = list(csv.DictReader(open(bom_path, newline="", encoding="utf-8-sig")))
groups, order = {}, []
for r in rows:
    key = (r["Footprint"].strip(), r["MPN"].strip())
    refs = _expand(r["Reference"])
    if key not in groups:
        groups[key] = dict(r)
        groups[key]["_refs"] = list(refs)
        order.append(key)
    else:
        groups[key]["_refs"] += refs
with open(bom_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Reference", "Value", "Footprint", "Qty", "MPN", "Manufacturer"])
    n_refs = 0
    for k in order:
        g = groups[k]
        rs = sorted(set(g["_refs"]), key=lambda x: (re.match(r"[A-Za-z]+", x).group(0),
                                                    int(re.search(r"\d+", x).group(0))))
        n_refs += len(rs)
        w.writerow([",".join(rs), g["Value"], g["Footprint"], len(rs),
                    g["MPN"], g["Manufacturer"]])
print("BOM: %d lines, %d designators (2-layer variant)" % (len(order), n_refs), flush=True)

# ---- 2. gerbers + drill on the 2L board --------------------------------------
run([CLI, "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask",
     "--output", os.path.join(FAB2, "gerbers") + os.sep, PCB2L], "gerbers")
g = [f for f in os.listdir(os.path.join(FAB2, "gerbers")) if not f.endswith(".gbrjob")]
if len(g) != len(LAYERS.split(",")):
    fails.append("gerbers: expected %d files, got %d" % (len(LAYERS.split(",")), len(g)))
run([CLI, "pcb", "export", "drill", "--format", "excellon", "--generate-map",
     "--map-format", "pdf", "--output", os.path.join(FAB2, "drill") + os.sep, PCB2L], "drill")
drl = ""
for f in os.listdir(os.path.join(FAB2, "drill")):
    if f.endswith(".drl"):
        drl += open(os.path.join(FAB2, "drill", f)).read()
for tool in ("3.2", "3.0"):
    if not re.search(r"C0?%s0*\b" % tool.replace(".", r"\."), drl):
        fails.append("drill: %smm NPTH tool missing" % tool)
print("gerbers: %d layers | drill: NPTH tools verified" % len(g), flush=True)

# ---- 3. positions (JLC + Lion conventions) on the 2L board -------------------
import gen_jlc_positions, gen_lion_positions
gen_jlc_positions.PCB = PCB2L
gen_jlc_positions.OUT = os.path.join(FAB2, "micromouse-pcb-simplified.jlc-positions.csv")
gen_jlc_positions.main()
gen_lion_positions.PCB = PCB2L
gen_lion_positions.OUT = os.path.join(FAB2, "micromouse-pcb-simplified.lion-positions.csv")
gen_lion_positions.main()

# ---- 4. vendor packages -------------------------------------------------------
import export_jlcpcb, export_lion
export_jlcpcb.FAB = FAB2
export_jlcpcb.OUT = os.path.join(OUT2, "jlcpcb")
export_jlcpcb.main()
export_lion.FAB = FAB2
export_lion.OUT = os.path.join(OUT2, "lioncircuits")
export_lion.main()

# ---- 5. rename zips so the 2L package is unmistakable -------------------------
for sub, old in (("jlcpcb", "micromouse-pcb-simplified-2layer-jlcpcb-gerbers.zip"),
                 ("lioncircuits", "micromouse-pcb-simplified-2layer-lion-gerbers.zip")):
    p = os.path.join(OUT2, sub, old)
    if os.path.exists(p):
        new = p.replace("-2layer-", "-2L-")
        if os.path.exists(new):
            os.remove(new)
        os.rename(p, new)
        print("zip -> %s" % os.path.basename(new), flush=True)

if fails:
    print("\n2L PRODUCTION EXPORT FAILED (%d):" % len(fails))
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("\nexport_production_2l: ALL GATES PASSED ->", OUT2)
