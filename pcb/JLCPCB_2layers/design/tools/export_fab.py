"""Fab-output pass with assertions. Exits 1 on any gate failure.

Produces in pcb/fab/ (gitignored, regenerable):
  gerbers/  9 fab layers (2-layer)          drill/  Excellon PTH+NPTH + PDF maps
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
LAYERS = ("F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,"
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

# --- assembly drawings (rev 7.2: the component-ID debug map) -------------------
# F.Fab/B.Fab carry EVERY refdes (finalize moves them off silk); these PDFs are
# the readable per-part map the user debugs from, alongside the selective silk
# refs on the board itself.
for (side, layers, mirror) in (("top", "F.Fab,Edge.Cuts", []),
                               ("bottom", "B.Fab,Edge.Cuts", ["--mirror"])):
    _pdf = os.path.join(FAB, f"assembly-{side}.pdf")
    run([CLI, "pcb", "export", "pdf", "--layers", layers, "--black-and-white",
         *mirror, "--output", _pdf, PCB], f"assembly-{side}")
    if not os.path.exists(_pdf) or os.path.getsize(_pdf) < 5000:
        fails.append(f"assembly: {side} PDF missing or trivially small")

# --- STEP (fit-check) ----------------------------------------------------------
out = run([CLI, "pcb", "export", "step", "--subst-models",
           "--output", os.path.join(FAB, "micromouse-pcb.step"), PCB], "step")
for bad in ("Could not add", "Cannot use"):
    if bad in out:
        lines = [l for l in out.splitlines() if bad in l]
        # Cosmetic-model waiver (2-layer, 2026-07-21): KiCad 10 ships NO step
        # for the JST-ZH header (J5/J6) or the CMT-8504 buzzer (BZ1); no local
        # model authored. Their heights are verified numerically instead
        # (ZH 6.0mm, buzzer 4.0mm -- nothing above them on this board). Any
        # OTHER missing model (motors, ICs, fuse) still fails the gate.
        hard = [l for l in lines
                if not any(f"for {r}." in l for r in ("J5", "J6", "BZ1"))]
        if hard:
            fails.append(f"step: {len(hard)} model(s) missing from the fit-check export: {hard[:4]}")
        else:
            print(f"step: {len(lines)} cosmetic models waived (J5/J6/BZ1 -- no vendor step exists)")

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

# --- DRC gate (rev 6.2 FIX) ---------------------------------------------------
# CRITICAL: `kicad-cli pcb drc --severity-warning` on KiCad 10.0.4 reports ONLY
# warning-severity items (included_severities:["warning"]) -- it HIDES every
# error. This masked 32 real courtyard/placement errors for many revs. The fab
# gate now runs DRC at the DEFAULT severity (error+warning) with schematic
# parity, and FAILS on any error, any unconnected item, or any parity mismatch.
import json as _json
_drc = os.path.join(BASE, "_export_drc.json")
run([CLI, "pcb", "drc", "--schematic-parity", "--format", "json",
     "--output", _drc, PCB], "drc")
try:
    _d = _json.load(open(_drc))
    _errs = [v for v in _d.get("violations", []) if v.get("severity") == "error"]
    _warns = [v for v in _d.get("violations", []) if v.get("severity") == "warning"]
    _unc = _d.get("unconnected_items", [])
    _par = _d.get("schematic_parity", [])
    print(f"DRC: {len(_errs)} errors, {len(_warns)} warnings, "
          f"{len(_unc)} unconnected, {len(_par)} parity")
    if _errs:
        import collections as _c
        _cc = _c.Counter(v["type"] for v in _errs)
        for _t, _n in _cc.most_common():
            print(f"   ERROR x{_n}: {_t}")
        fails.append(f"drc: {len(_errs)} error-severity violations (see above)")
    if _unc:
        # 2-layer WAIVER (user-accepted 2026-07-21): GND pour fragments that no
        # via/track can reach (walled by 0.15mm routing on both faces) are
        # non-critical -- every functional ground connects through the main
        # pour (the only pad items are U8's REDUNDANT GND pads 2/25; the IMU
        # is grounded via pads 5/6/17/18). Anything else still FAILS.
        _waived, _hard = [], []
        for _u in _unc:
            _ds = " ".join(x.get("description", "") for x in _u.get("items", []))
            _gnd_only = "[GND]" in _ds
            _pad_ok = ("pad" not in _ds.lower()) or ("of U8" in _ds)
            (_waived if (_gnd_only and _pad_ok) else _hard).append(_ds[:70])
        print(f"   unconnected: {len(_hard)} hard, {len(_waived)} waived "
              f"(GND pour fragments / redundant U8 GND pads)")
        if _hard:
            for _h in _hard[:6]:
                print("   HARD:", _h)
            fails.append(f"drc: {len(_hard)} non-waivable unconnected items")
    if _par:
        fails.append(f"drc: {len(_par)} schematic-parity mismatches")
except Exception as _e:
    fails.append(f"drc: could not parse report ({_e})")

if fails:
    print(f"\nFAB EXPORT GATES FAILED ({len(fails)}):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("\nexport_fab: ALL GATES PASSED --", FAB)
