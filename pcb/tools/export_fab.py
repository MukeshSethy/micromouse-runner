"""Fab-output pass with assertions. Exits 1 on any gate failure.

Produces in pcb/fab/ (gitignored, regenerable):
  gerbers/  11 fab layers          drill/  Excellon PTH+NPTH + PDF maps
  micromouse-pcb.pos.csv           micromouse-pcb.step (--subst-models)
and writes the orderable BOM to pcb/BOM.csv (committed).

Gates (each would have caught a shipped rev-5 defect class):
  - drill data MUST contain the 3.2mm bracket + 3.0mm castor NPTH tools
    (rev 5 shipped them as routed Edge.Cuts circles, absent from the drill
    file, while the docs promised drilled NPTH)
  - STEP export must load EVERY 3D model (rev 5's fit-check STEP silently
    omitted both motors and U1/L1)
  - every gerber layer file must exist and be non-trivial
  - BOM rows missing an MPN are listed (warning, not failure: some passives
    are generic by design)
"""
import csv
import os
import shutil
import subprocess
import sys

CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PCB = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
SCH = os.path.join(BASE, "micromouse-pcb.kicad_sch")
FAB = os.path.join(BASE, "fab")
LAYERS = ("F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,"
          "F.Mask,B.Mask,Edge.Cuts")

fails = []


def run(args, what):
    r = subprocess.run(args, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        fails.append(f"{what}: exit {r.returncode}: {out[-300:]}")
    return out


shutil.rmtree(FAB, ignore_errors=True)
os.makedirs(os.path.join(FAB, "gerbers"))
os.makedirs(os.path.join(FAB, "drill"))

# --- gerbers -----------------------------------------------------------------
run([CLI, "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask",
     "--output", os.path.join(FAB, "gerbers") + os.sep, PCB], "gerbers")
gfiles = [f for f in os.listdir(os.path.join(FAB, "gerbers")) if not f.endswith(".gbrjob")]
if len(gfiles) != len(LAYERS.split(",")):
    fails.append(f"gerbers: expected {len(LAYERS.split(','))} layer files, got {len(gfiles)}: {sorted(gfiles)}")
for f in gfiles:
    if os.path.getsize(os.path.join(FAB, "gerbers", f)) < 500:
        fails.append(f"gerbers: {f} suspiciously small")

# --- drill -------------------------------------------------------------------
run([CLI, "pcb", "export", "drill", "--format", "excellon", "--generate-map",
     "--map-format", "pdf", "--output", os.path.join(FAB, "drill") + os.sep, PCB], "drill")
drl_text = ""
for f in os.listdir(os.path.join(FAB, "drill")):
    if f.endswith(".drl"):
        drl_text += open(os.path.join(FAB, "drill", f)).read()
for tool_mm, what in (("3.2", "bracket NPTH"), ("3.0", "castor NPTH")):
    if f"C{tool_mm}" not in drl_text.replace("C0", "C"):
        # Excellon tool lines look like T4C3.200 (leading fmt varies) -- search loosely
        import re
        if not re.search(rf"C0?{tool_mm.replace('.', chr(92) + '.')}0*\b", drl_text):
            fails.append(f"drill: no {tool_mm}mm tool ({what} holes missing from drill data)")

# --- placement ---------------------------------------------------------------
run([CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--use-drill-file-origin",
     "--output", os.path.join(FAB, "micromouse-pcb.pos.csv"), PCB], "pos")
if not os.path.exists(os.path.join(FAB, "micromouse-pcb.pos.csv")):
    fails.append("pos: file not produced")

# --- STEP (fit-check) ----------------------------------------------------------
out = run([CLI, "pcb", "export", "step", "--subst-models",
           "--output", os.path.join(FAB, "micromouse-pcb.step"), PCB], "step")
for bad in ("Could not add", "Cannot use"):
    if bad in out:
        lines = [l for l in out.splitlines() if bad in l]
        fails.append(f"step: {len(lines)} model(s) missing from the fit-check export: {lines[:4]}")

# --- BOM ----------------------------------------------------------------------
bom_path = os.path.join(BASE, "BOM.csv")
run([CLI, "sch", "export", "bom",
     "--fields", "Reference,Value,Footprint,${QUANTITY},MPN,Manufacturer",
     "--labels", "Reference,Value,Footprint,Qty,MPN,Manufacturer",
     "--group-by", "Value,Footprint,MPN",
     "--exclude-dnp", "--output", bom_path, SCH], "bom")
no_mpn = []
n_rows = 0
with open(bom_path, newline="", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        n_rows += 1
        if not row.get("MPN", "").strip():
            no_mpn.append(f"{row.get('Reference','?')} ({row.get('Value','?')[:40]})")
print(f"BOM: {n_rows} line items -> {bom_path}")
if no_mpn:
    print(f"BOM rows without MPN ({len(no_mpn)}):")
    for r in no_mpn:
        print("   -", r)

if fails:
    print(f"\nFAB EXPORT GATES FAILED ({len(fails)}):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("\nexport_fab: ALL GATES PASSED --", FAB)
