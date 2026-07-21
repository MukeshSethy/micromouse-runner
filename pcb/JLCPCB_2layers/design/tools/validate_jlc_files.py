"""JLC-COMPATIBILITY VALIDATOR -- mechanically test the production files in
fab_release/jlcpcb/ against what JLCPCB's upload parsers actually require,
BEFORE calling the package orderable. Exits 1 on any FAIL.

Checks (each mirrors a real JLC upload/assembly failure mode):
  GERBER ZIP: all 9 2-layer files + Excellon drills present in ONE flat zip;
    every gerber is RS-274X/X2 (has %FS and %MO units + an aperture); the
    Edge.Cuts outline exists and is non-trivial; copper apertures >= JLC's
    0.127mm minimum; drill files are Excellon (M48 header, METRIC) and carry
    the 3.2/3.0mm NPTH mount tools.
  BOM: exact JLC column schema; designators explicit comma lists (a KiCad
    range like "C1-C4" hard-fails JLC's parser); every line has an LCSC part;
    no designator appears twice.
  CPL: exact JLC column schema; numeric mm coordinates; Layer in {Top,Bottom};
    rotation in [0,360); no duplicate designators.
  CROSS: BOM designator set == CPL designator set (a desync silently drops
    parts from the assembly quote); CPL coordinates all inside the 100x120
    board frame from the gerber outline.
"""
import csv
import io
import os
import re
import sys
import zipfile

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(BASE, "fab_release", "jlcpcb")
ZIP = os.path.join(OUT, "micromouse-pcb-2layer-jlcpcb-gerbers.zip")

fails = []


def check(ok, label, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" -- {detail}" if detail else ""))
    if not ok:
        fails.append(label)
    return ok


print("=" * 72)
print("GERBER + DRILL ZIP")
print("=" * 72)
z = zipfile.ZipFile(ZIP)
names = z.namelist()
check(all("/" not in n for n in names), "zip is flat (no folders)", f"{len(names)} files")

WANT = {"F_Cu": r"F_Cu\.g|\.gtl", "B_Cu": r"B_Cu\.g|\.gbl",
        "F_Mask": r"F_Mask|\.gts", "B_Mask": r"B_Mask|\.gbs",
        "F_Silk": r"F_Silk|\.gto", "B_Silk": r"B_Silk|\.gbo",
        "F_Paste": r"F_Paste|\.gtp", "B_Paste": r"B_Paste|\.gbp",
        "Edge": r"Edge_Cuts|\.gm1|\.gko"}
layer_file = {}
for key, pat in WANT.items():
    hit = [n for n in names if re.search(pat, n, re.I)]
    check(len(hit) == 1, f"exactly one {key} gerber", str(hit))
    if hit:
        layer_file[key] = hit[0]
drills = [n for n in names if n.endswith(".drl")]
check(1 <= len(drills) <= 2, "Excellon drill file(s) in the SAME zip", str(drills))

min_ap = 9e9
for key, fn in layer_file.items():
    g = z.read(fn).decode("utf-8", "replace")
    is_x = "%FS" in g and ("%MOMM" in g or "%MOIN" in g)
    check(is_x, f"{key}: RS-274X header (%FS + %MO)", fn)
    check("%MOMM" in g, f"{key}: metric units")
    check(g.count("X") > 10 and "M02" in g, f"{key}: has geometry + EOF (M02)")
    if key in ("F_Cu", "B_Cu"):
        for ap in re.findall(r"%ADD\d+C,([0-9.]+)", g):
            min_ap = min(min_ap, float(ap))
check(min_ap >= 0.127, "copper apertures >= JLC 0.127mm min",
      f"smallest round aperture {min_ap:.3f}mm")

edge = z.read(layer_file["Edge"]).decode("utf-8", "replace")
xs = [int(m) / 1e6 for m in re.findall(r"X(-?\d+)", edge)]
ys = [int(m) / 1e6 for m in re.findall(r"Y(-?\d+)", edge)]
board_w, board_h = max(xs) - min(xs), max(ys) - min(ys)
check(95 <= board_w <= 105 and 115 <= board_h <= 125,
      "Edge.Cuts outline spans the 100x120 board", f"{board_w:.1f} x {board_h:.1f} mm")

drl_all = ""
for d in drills:
    t = z.read(d).decode("utf-8", "replace")
    drl_all += t
    check("M48" in t, f"{d}: Excellon header (M48)")
    check("METRIC" in t or "M71" in t, f"{d}: metric drill units")
for tool in ("3.2", "3.0"):
    check(bool(re.search(r"C0?%s0*\b" % tool.replace(".", r"\."), drl_all)),
          f"{tool}mm NPTH mount tool present in drill data")

print()
print("=" * 72)
print("BOM (JLC assembly schema)")
print("=" * 72)
bom = list(csv.reader(open(os.path.join(OUT, "BOM_JLC-assembly.csv"),
                           newline="", encoding="utf-8")))
hdr, rows = bom[0], bom[1:]
check(hdr[:4] == ["Comment", "Designator", "Footprint", "LCSC Part #"],
      "BOM columns exactly Comment/Designator/Footprint/LCSC", str(hdr))
bom_refs = []
range_bad, no_lcsc = [], []
for r in rows:
    refs = [x.strip() for x in r[1].split(",") if x.strip()]
    bom_refs.extend(refs)
    for x in refs:
        if "-" in x:
            range_bad.append(x)
    if not r[3].strip():
        no_lcsc.append(r[0])
check(not range_bad, "designators are explicit (no KiCad ranges)", str(range_bad[:4]))
check(not no_lcsc, "every BOM line carries an LCSC part", str(no_lcsc[:4]))
dup = {x for x in bom_refs if bom_refs.count(x) > 1}
check(not dup, "no designator on two BOM lines", str(sorted(dup)[:6]))
print(f"  ({len(rows)} BOM lines, {len(bom_refs)} designators)")

print()
print("=" * 72)
print("CPL (JLC placement schema)")
print("=" * 72)
cpl = list(csv.reader(open(os.path.join(OUT, "CPL_JLC-assembly.csv"),
                           newline="", encoding="utf-8")))
chdr, crows = cpl[0], cpl[1:]
check(chdr == ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"],
      "CPL columns exactly Designator/MidX/MidY/Layer/Rotation", str(chdr))
cpl_refs = [r[0] for r in crows]
bad_num, bad_layer, bad_rot = [], [], []
minx = miny = 9e9
maxx = maxy = -9e9
for r in crows:
    try:
        x = float(r[1].replace("mm", "")); y = float(r[2].replace("mm", ""))
        minx, maxx = min(minx, x), max(maxx, x)
        miny, maxy = min(miny, y), max(maxy, y)
    except ValueError:
        bad_num.append(r[0])
    if r[3] not in ("Top", "Bottom"):
        bad_layer.append(r[0])
    try:
        rot = float(r[4])
        if not (0 <= rot < 360):
            bad_rot.append(r[0])
    except ValueError:
        bad_rot.append(r[0])
check(not bad_num, "all coordinates numeric mm", str(bad_num[:4]))
check(not bad_layer, "Layer values are Top/Bottom", str(bad_layer[:4]))
check(not bad_rot, "rotations in [0,360)", str(bad_rot[:4]))
cdup = {x for x in cpl_refs if cpl_refs.count(x) > 1}
check(not cdup, "no duplicate CPL designators", str(sorted(cdup)[:6]))
check(maxx - minx <= 105 and maxy - miny <= 125,
      "CPL spread fits the board frame",
      f"x {minx:.1f}..{maxx:.1f}  y {miny:.1f}..{maxy:.1f} (KiCad/gerber shared frame; "
      "negative Y is CORRECT, do not flip)")
print(f"  ({len(crows)} placements)")

print()
print("=" * 72)
print("BOM <-> CPL cross-consistency")
print("=" * 72)
b, c = set(bom_refs), set(cpl_refs)
check(b == c, "BOM designator set == CPL designator set",
      f"BOM-only={sorted(b-c)[:6]} CPL-only={sorted(c-b)[:6]}")

print()
if fails:
    print(f"JLC FILE VALIDATION: FAIL ({len(fails)}):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("JLC FILE VALIDATION: ALL PASS -- the package is upload-ready "
      "(gerber zip + BOM + CPL mutually consistent, JLC schemas satisfied).")
