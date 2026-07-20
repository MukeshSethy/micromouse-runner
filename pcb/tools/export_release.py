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
# The JLCPCB folder is owned by export_jlcpcb.py (it fills real LCSC part
# numbers, emits JLC's exact .xlsx BOM/CPL formats, and splits SMT vs THT).
# Kept out of this script so a re-run can't clobber those files with the old
# blank-LCSC csv format.
print("jlcpcb: run tools/export_jlcpcb.py (owns pcb/fab_release/jlcpcb/)")
print("export_release: DONE")
