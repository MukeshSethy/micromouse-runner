"""Build the THT board's Lion Circuits production folder (bare-PCB fab +
parts kit -- NO assembly service; the THT board is hand-soldered).
Run export_fab.py first (it owns the DRC/gerber gates)."""
import csv
import os
import shutil
import zipfile

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FAB = os.path.join(BASE, "fab")
REL = os.path.join(BASE, "fab_release")

if not os.path.isdir(FAB):
    raise SystemExit("run export_fab.py first (tht-assembly/pcb/fab missing)")

lion = os.path.join(REL, "lion-circuits")
shutil.rmtree(lion, ignore_errors=True)
os.makedirs(lion)

# full gerber zip (bare-board fab order)
zpath = os.path.join(lion, "micromouse-tht-gerbers.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(FAB):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, FAB))

for f in ("BOM.csv",):
    src = os.path.join(BASE, f)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(lion, f))
for f in ("assembly-top.pdf", "assembly-bottom.pdf", "micromouse-tht.pos.csv"):
    src = os.path.join(FAB, f)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(lion, f))

open(os.path.join(lion, "ORDERING.md"), "w", encoding="utf-8").write("""# THT carrier -- Lion Circuits ordering (bare board + parts kit, self-assembly)

This is the SELF-SOLDERED edition: order the bare PCB (no assembly service)
plus the parts, and hand-solder. The whole build -- including the three
plug-in modules -- is Lion-stocked, so it can be one Lion order.

## 1. Bare board
Upload `micromouse-tht-gerbers.zip` as a FAB-ONLY order. 4-layer, 100x120mm,
1.6mm, HASL is fine for hand soldering (no assembly = rotations/CPL not
needed).

## 2. Parts kit (Lion BOM tool, from BOM.csv)
- `CD74HC4067E` DIP mux: catalog page 404s on the bare slug -- jellybean,
  Lion procures; any distributor stocks it.
- `RLB0914-330KL` 33uH inductor + `1N5822` schottky: confirm the exact slugs
  in the BOM tool (families verified In Stock).

## 3. Plug-in modules (all In Stock at Lion, verified 2026-07-20)
- ESP32-S3-DevKitC-1-N8R2 (2x 1x22 sockets)
- Adafruit/Pololu TB6612 breakout #2448 (2x 1x8 sockets) -- robu clone is a
  ~Rs.150 budget alt (dry-fit the row spacing before soldering sockets)
- Adafruit BNO055 breakout #4646 (J15 IMU header) -- GY-BNO055 (robu) is a
  budget alt via jumper wires. VERIFY your module's pin order against the
  J15 silk before soldering the socket; ADR must be tied for 0x28.

## 4. Solder order (flat board, low to tall)
bottom-face axial resistors + TO-92 + diodes + piezo (do the whole bottom
first) -> flip -> DIP mux (flat, no socket) -> ceramics -> LEDs -> tact
switches -> slide switches -> electrolytics -> TO-220 bucks + inductors ->
PPTC -> connectors (XH/ZH/XT60/JTAG) -> the three module sockets last.
Then the rev-7.2 bring-up order (fw/README.md): SW5, meter rails, flash via
the DevKit USB-C, sensors, then SW6 wheels-up.
""")
print("lion-circuits (THT) folder:", sorted(os.listdir(lion)))
print("export_release_tht: DONE")
