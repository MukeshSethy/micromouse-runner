# 2-layer board — GUI finalization punch-list

The board is **routed and committed** (`micromouse-pcb.kicad_pcb`, Freerouting
score 994, 1187 tracks + 138 vias + 174 GND stitch vias). Placement DRC-clean,
schematic parity 0. Two items remain and are fastest to close in the KiCad 10
PCB Editor (~10 min total). After each step, `Edit → Fill All Zones` (**B**) so
the ratsnest updates.

Open: `pcb/JLCPCB_2layers/design/micromouse-pcb.kicad_pcb`

---

## Step 1 — reroute BATT_RAW out of the rear pinch  (1 DRC error)

**Symptom:** `copper_edge_clearance` — BATT_RAW is **0.180 mm** from the antenna
notch (rule 0.3 mm), at **(40.1, 113.5)** on **B.Cu**.

**Why it can't be nudged:** the long B.Cu segment `(26.6, 113.52) → (65.0,
113.52)` runs the rear in the ~0.3 mm gap between the ESP module (body ends at
y113.5) and the notch edge (y113.8), and U6's pad at x62.6 pinches it further.
No single y clears both the notch (0.3 mm) *and* U6 (0.127 mm).

**Fix (≈1 min):**
1. Select that horizontal BATT_RAW segment on **B.Cu** and **Delete** it (also
   delete the two short jogs into it near x26.6 and x65.0 if needed).
2. Interactive-route BATT_RAW between its two rear anchors (hotkey **X**):
   route it **below U6** (dip to y ≲ 110 around x59–66) or push U6's neighbours
   with KiCad's shove router, keeping **≥ 0.3 mm from the notch edge (y113.8)**.
   The battery feed is not timing-critical, so a slightly longer path is fine.
   *Alternative:* nudge **U6** ~0.4 mm toward the board centre (−x) first, which
   opens the pinch, then re-route.
3. **B** to refill.

---

## Step 2 — close the GND pour (22 ratsnest)

On a 2-layer board the twin GND pours fragment where signals cross; 174 stitch
vias are already placed, leaving **22** isolated GND clusters. KiCad draws them
as **22 white ratsnest lines** on GND — close each with a via.

**Fastest method:**
1. `View`: make sure **Ratsnest** is on. The 22 lines cluster in the dense
   mid-board region (roughly **x40–65, y50–90**) plus a few rear (**x45–65,
   y100–114**).
2. For each ratsnest line: `Place → Add Free Via` (**Ctrl+Shift+V**, or drop a
   via mid-route) at a point on the line where **both** F.Cu and B.Cu show GND
   copper. Use the same 0.6/0.3 mm via as the existing stitches.
3. **B** to refill after every few vias; the ratsnest count drops as clusters
   merge. Repeat until the ratsnest shows **0**.
4. If a fragment is a tiny pad-less sliver with no room for a via, it's floating
   copper — `Zone Properties → Remove islands: Always` on the two GND zones and
   refill removes those; only pad/via-anchored clusters then remain.

---

## Step 3 — silk + dangling copper (36 warnings) — scripted

Once **ratsnest = 0**, run the project's finalizer (moves every refdes/value to
the fab layer and prunes redundant fan-out stubs — this clears the
`silk_overlap` / `silk_over_copper` / `silk_edge_clearance` warnings):

```
"C:\Program Files\KiCad\10.0\bin\python.exe" tools/finalize.py
```

(Do **not** run it before ratsnest 0 — its dangling-copper pass assumes full
connectivity.)

---

## Step 4 — verify 0 / 0 / 0

```
"C:\Program Files\KiCad\10.0\bin\python.exe" tools/verify_drc.py
```

Expect: **0 errors / 0 warnings / 0 unconnected / 0 parity / ratsnest 0.**

## Step 5 — production package

```
"C:\Program Files\KiCad\10.0\bin\python.exe" tools/export_jlcpcb.py
```

Emits the JLCPCB gerbers + BOM_JLC-assembly + CPL_JLC-assembly under
`production/`. The BOM already maps all 45 MPNs to in-stock LCSC parts
(`tools/jlcpcb_lcsc_map.py`); reserve the BNO055 (C93216) at order time.
