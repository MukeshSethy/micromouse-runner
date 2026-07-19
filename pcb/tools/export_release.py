"""Build fabricator-specific production folders from pcb/fab/ (run export_fab
first -- it owns the gates). Two targets (rev 7.2, user request 2026-07-20):

  pcb/fab_release/lion-circuits/   Lion's turnkey flow: full gerber zip +
                                   BOM.csv + pos + assembly PDFs + ORDERING.md
  pcb/fab_release/jlcpcb/          JLCPCB flow: flat gerber+drill zip (their
                                   uploader wants ONLY fab layers at zip root),
                                   BOM in JLC column format, CPL (pos) in JLC
                                   column format, ORDERING.md with the caveats
                                   (LCSC matching, rotations, THT parts)
"""
import csv
import os
import shutil
import zipfile

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FAB = os.path.join(BASE, "fab")
REL = os.path.join(BASE, "fab_release")

if not os.path.isdir(FAB):
    raise SystemExit("run export_fab.py first (pcb/fab missing)")

# ---------------- lion-circuits ------------------------------------------------
lion = os.path.join(REL, "lion-circuits")
shutil.rmtree(lion, ignore_errors=True)
os.makedirs(lion)
zpath = os.path.join(lion, "micromouse-pcb-rev7.2-gerbers.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(FAB):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, FAB))
shutil.copy(os.path.join(BASE, "BOM.csv"), os.path.join(lion, "BOM.csv"))
shutil.copy(os.path.join(FAB, "micromouse-pcb.pos.csv"), os.path.join(lion, "micromouse-pcb.pos.csv"))
for f in ("assembly-top.pdf", "assembly-bottom.pdf"):
    shutil.copy(os.path.join(FAB, f), os.path.join(lion, f))
open(os.path.join(lion, "ORDERING.md"), "w", encoding="utf-8").write("""# Lion Circuits ordering notes (rev 7.2)

1. Upload `micromouse-pcb-rev7.2-gerbers.zip` + `BOM.csv` + the pos file in
   Lion's turnkey flow. 4-layer, 1.6 mm, 1 oz outer / 0.5 oz inner is fine.
2. F1 (`MINISMDC350F/16-2`): Lion's part-page URL cannot encode the slashed
   MPN -- confirm the line in their BOM tool; approved equivalent:
   Bourns MF-MSMF350-2 (1812, 3.5 A hold / 7 A trip).
3. J10 (AMASS XT60-M): catalog page may show Out of Stock -- Lion sources
   turnkey and can usually procure. If not: leave unpopulated; it is a
   one-minute THT hand-fit (polarity + ONE PACK ONLY silk on board).
4. Assembly PDFs carry every refdes (the board silk carries the
   debug-critical subset).
""")
print("lion-circuits folder:", sorted(os.listdir(lion)))

# ---------------- jlcpcb -------------------------------------------------------
jlc = os.path.join(REL, "jlcpcb")
shutil.rmtree(jlc, ignore_errors=True)
os.makedirs(jlc)
# flat gerber+drill zip
zpath = os.path.join(jlc, "micromouse-pcb-rev7.2-jlcpcb.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    gdir = os.path.join(FAB, "gerbers")
    for f in os.listdir(gdir):
        z.write(os.path.join(gdir, f), f)
    ddir = os.path.join(FAB, "drill")
    for f in os.listdir(ddir):
        if f.endswith((".drl", ".pdf")):
            z.write(os.path.join(ddir, f), f)
# BOM in JLC columns: Comment, Designator, Footprint, LCSC Part #
rows = list(csv.DictReader(open(os.path.join(BASE, "BOM.csv"), newline="", encoding="utf-8-sig")))
with open(os.path.join(jlc, "bom_jlcpcb.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "MPN", "Manufacturer"])
    for r in rows:
        w.writerow([r.get("Value", ""), r.get("Reference", ""),
                    (r.get("Footprint", "") or "").rsplit(":", 1)[-1],
                    "",                       # LCSC numbers: match by MPN in their tool
                    r.get("MPN", ""), r.get("Manufacturer", "")])
# CPL in JLC columns from the KiCad pos csv
pos = list(csv.DictReader(open(os.path.join(FAB, "micromouse-pcb.pos.csv"), newline="", encoding="utf-8-sig")))
with open(os.path.join(jlc, "cpl_jlcpcb.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in pos:
        w.writerow([r.get("Ref", r.get("ref", "")),
                    f'{r.get("PosX", r.get("posx", ""))}mm',
                    f'{r.get("PosY", r.get("posy", ""))}mm',
                    ("Top" if r.get("Side", r.get("side", "")).lower().startswith("top") else "Bottom"),
                    r.get("Rot", r.get("rot", ""))])
open(os.path.join(jlc, "ORDERING.md"), "w", encoding="utf-8").write("""# JLCPCB ordering notes (rev 7.2)

1. Upload `micromouse-pcb-rev7.2-jlcpcb.zip` (gerbers + Excellon drill, flat).
   Board: 4-layer, 100 x 120 mm, 1.6 mm; the default JLC 4-layer stackup is
   fine (no controlled impedance required -- USB is full-speed).
2. For SMT assembly add `bom_jlcpcb.csv` + `cpl_jlcpcb.csv`. LCSC part
   numbers are intentionally blank: use JLC's "match by MPN" in the BOM
   review step (all MPNs are major-distributor parts; some may be
   Global-Sourcing lines with longer lead).
3. CHECK ROTATIONS in JLC's assembly preview -- KiCad and JLC rotation
   conventions differ per package; fix any flipped polarized part
   (U1/U2/U3/U6/U7/U8, D29, Q-parts) in their editor before confirming.
4. THT parts (J1/J5/J6/J7-J10, SW1-SW6, sensors, motors' connectors) are NOT
   in JLC economic SMT -- order them loose and hand-fit, or use JLC Standard
   PCBA. J10 (XT60) is optional: fit only if your pack lead is XT60.
5. The exact robu motor plugs straight into J5/J6 (JST ZH) -- meter-check
   the cable's VCC/GND (positions 2/5) once before first plug-in.
""")
print("jlcpcb folder:", sorted(os.listdir(jlc)))
print("export_release: DONE")
