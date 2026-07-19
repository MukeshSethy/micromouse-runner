# Micromouse PCB — Requirements Specification
### IBM DOORS-style requirements module (formal, reviewable, traceable)

| Document control | |
|---|---|
| **Module** | MMSE — Micromouse Sensor/Control PCB |
| **Baseline** | Rev 6.2 (as-built) → Rev 7 (in remediation) |
| **Date** | 2026-07-19 |
| **Owner** | Mukesh Sethy |
| **Prepared by** | Claude (autonomous engineering session) |
| **Fabricator (intended)** | Lion Circuits (lioncircuits.com) |
| **Repository** | github.com/MukeshSethy/micromouse-runner |
| **Governing standards** | IPC-2221B (generic PCB design), IPC-7351C (land patterns / courtyards), IPC-A-610 (acceptability), USB 2.0 (full-speed), Espressif ESP32-S3 Hardware Design Guidelines, Bosch BNO055 datasheet, IEC 61000 (EMC intent) |

---

## 1. How to read this module

Each requirement is an **object** with a stable **Object ID** (`MMSE-<area>-<n>`).
The columns follow IBM DOORS conventions:

| Attribute | Meaning |
|---|---|
| **ID** | Stable identifier; never reused. |
| **Requirement (Object Text)** | The shall-statement. |
| **Type** | `H` heading · `R` requirement · `I` information. |
| **Pri** | Priority: `M` mandatory · `S` should · `C` could. |
| **VM** | Verification Method: **T** test · **A** analysis · **I** inspection · **D** demonstration. |
| **Status** | `VERIFIED` · `PARTIAL` · `OPEN` · `FAILED` · `N/A`. Reflects the **as-built rev 6.2 board** verified with the *correct* KiCad DRC severity (error+warning) on 2026-07-19. |
| **Evidence / Notes** | Where the verification comes from, and caveats. |

**Verification-status honesty note (READ THIS FIRST).** Every "0 errors / 0 warnings"
claim made before 2026-07-19 was produced with `kicad-cli pcb drc --severity-warning`,
which on **KiCad 10.0.4 reports only warning-severity items and silently omits every
error** (`included_severities == ["warning"]`). Re-running DRC at the default
(error+warning) severity revealed **32 error-severity violations** that had been
invisible for the whole project history. All statuses below use the corrected
command. See `MMSE-PCB-3` and the Remediation Register (§13).

---

## 2. Mechanical (MMSE-MECH)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-MECH-0 | **Mechanical envelope & keep-outs** | H | — | — | — | Board geometry defined in `pcb/tools/board_geom.py`. |
| MMSE-MECH-1 | The board outline shall be a UKMARS-class micromouse形-factor with wheel-notch cut-outs at the axle line and a rear antenna U-notch. | R | M | I | VERIFIED | `board_geom.BOARD_OUTLINE`; bbox 100 × 120 mm; Edge.Cuts matches source to 0.000 mm (audit R8). |
| MMSE-MECH-2 | No part of any component shall extend outside the board outline, **except** the two motor shafts (and the WROOM antenna over its notch). | R | M | A | PARTIAL | Audit R8: all footprint courtyards inside; **exception:** indicator LED **D25** F.Fab body nicks the left chamfer by ~0.22 mm (0.024 mm²). Motor bodies overhang the wheel notches by design (allowed). → tracked `MMSE-REM-7`. |
| MMSE-MECH-3 | Space shall be cut for the ESP32 module antenna (copper + board keep-out at the antenna projection). | R | M | I | VERIFIED | Rear U-notch `ANT_NOTCH` 24.9–45.6 × 113.8–120 mm; WROOM at (35.25, 106.7) rot 180; antenna tip y≈119.66 (inside y=120). Embedded keepout zone retained. |
| MMSE-MECH-4 | Four UKMARS motor-bracket mounting holes + one castor/front hole shall be present as NPTH. | R | M | I | VERIFIED | `MOUNT_HOLES` → H1–H4 (bracket, r 1.6) + H5 (front, r 1.5), all NPTH (drilled, in drill file). |
| MMSE-MECH-5 | Board thickness / stack-up shall be a standard 4-layer 1.6 mm process. | R | S | I | VERIFIED | 4 copper layers F.Cu / In1.Cu / In2.Cu / B.Cu. |

---

## 3. PCB / Fabrication quality (MMSE-PCB)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-PCB-0 | **Manufacturability & DRC** | H | — | — | — | Verified with `pcb/tools/verify_drc.py` (error+warning severity + pcbnew ratsnest). |
| MMSE-PCB-1 | The board shall be a **4-layer** design (2 signal/GND outer, 2 inner planes). | R | M | I | VERIFIED | Gerbers: `.gtl / .g1 / .g2 / .gbl`. |
| MMSE-PCB-2 | All copper and hole clearances shall meet the fabricator's capability (≥0.127 mm copper, drill in range). | R | M | A | VERIFIED | Default-severity DRC: **0 `clearance`, 0 `hole_clearance`, 0 `copper_edge_clearance` errors** on the as-built board → board is **electrically/physically manufacturable**. |
| MMSE-PCB-3 | KiCad DRC shall report **0 errors and 0 warnings** (schematic-parity included). | R | M | T | **FAILED (12, ↓ from 32)** | After `tighten_courtyards.py` (MMSE-REM-1 DONE): **12 error-severity violations** remain — 10 `pth_inside_courtyard` (wall-sensor pads ~0.27 mm under opposite-side line-sensor bodies) + 2 `courtyards_overlap` (rotated diagonal LED pairs). 0 warnings / 0 unconnected / 0 parity, ratsnest 0. NOT copper collisions (MMSE-PCB-2). Residual fix: §13 `MMSE-REM-2`. |
| MMSE-PCB-4 | Connectivity shall be complete (0 unrouted). | R | M | A | VERIFIED | pcbnew ratsnest (pours filled) = **0**. kicad-cli "unconnected" is unreliable headless and must NOT be used (project lore). |
| MMSE-PCB-5 | Schematic ↔ board parity shall be 0 mismatches. | R | M | T | VERIFIED | `sync_board_meta.py`; parity 0 at default severity. Ignored rules limited to the custom-footprint family (`lib_footprint_mismatch`, `lib_footprint_issues`, `footprint_filters_mismatch`) — same documented root cause, zero fab impact. |
| MMSE-PCB-6 | The DRC gate in tooling shall use error-inclusive severity (guards against the `--severity-warning` masking defect). | R | M | I | VERIFIED | Fixed rev 6.2: `verify_drc.py` (canonical), `export_fab.py` DRC gate, `finalize.py` at default severity. |

---

## 4. Power (MMSE-PWR)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-PWR-0 | **Power architecture** | H | — | — | — | 2S LiPo → protection → regulated 3.3 V logic + 6.0 V motor. |
| MMSE-PWR-1 | Input shall be a **2S LiPo** (nom 7.4 V, max 8.4 V). | R | M | I | VERIFIED | J-BATT 2-pin; silk "BATT 2S 8.4V MAX". |
| MMSE-PWR-2 | Motors shall run from a **regulated fixed 6.0 V** rail, steady over battery discharge. | R | M | A | VERIFIED | TPS54302 buck, FB 100 k/11 k → **6.01 V** set-point (audit R4). Regulation independent of pack V down to dropout. |
| MMSE-PWR-3 | The 6 V rail shall supply the motor stall current with margin. | R | M | A | PARTIAL | 3 A buck limit; 2×1.6 A stall = 3.2 A exceeds rating only in the simultaneous double-hard-stall fault corner; firmware PWM-limits + PPTC guard. Acceptable transient (audit R4). → note `MMSE-REM-8`. |
| MMSE-PWR-4 | Logic shall run from a **regulated 3.3 V** rail. | R | M | A | VERIFIED | AP63203WU 3.3 V/2 A buck. |
| MMSE-PWR-5 | Input protection: reverse-polarity + over-current. | R | M | A | VERIFIED | F1 MINISMDC260F (2.6 A/16 V PPTC) + Q1 DMP3098L reverse P-FET (Vgs ±20 V, 2S-safe). |
| MMSE-PWR-6 | All bulk/decoupling on 2S-referenced rails shall be rated ≥16 V (25 V-class preferred). | R | M | I | VERIFIED | 25 V-class caps on VM_BATT/VM_6V; C30 220 µF/16 V alu at TB6612 VM. |
| MMSE-PWR-7 | **Two switches:** SW-A enables everything **except** motors; SW-B additionally enables the motor rail. | R | M | A | VERIFIED | SW5 = PWR_EN (all logic rails), SW6 = MOT_EN (gates TPS54302 EN). EN divider R69/R70/R71 = 100 k/220 k/110 k reaches the 1.21 V threshold (audit R7; the 1 MΩ bug is fixed). |

---

## 5. Sensors — line array (MMSE-LINE)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-LINE-1 | An 8-element downward line-sensor array (TCRT5000, bottom face) shall span the front at even pitch. | R | M | I | VERIFIED | LS1–LS8, 9.525 mm pitch, y=19, bottom (flipped). |
| MMSE-LINE-2 | The line array shall be multiplexed through the analog MUX (CD74HC4067); wall sensors shall NOT use the MUX. | R | M | A | PARTIAL | Line channels on U4 MUX confirmed; wall sensors go direct to ADC1 (VERIFIED). **Caveat:** U4 also carries 3 housekeeping analog signals (VBUS/BAT_MID/VBUS_SENSE) on spare channels — "MUX only for line array" is violated in the literal sense (audit R9). Functionally intended; flagged for wording. |
| MMSE-LINE-3 | Each line sensor shall have a top-side indicator LED placed clear of its bottom-side solder access. | R | S | I | VERIFIED | D14–D21 indicators; placement gate `LINE_Y` lead-field logic. |

---

## 6. Sensors — wall optics geometry (MMSE-WALL)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-WALL-1 | Side-wall IR sensor pairs shall aim **exactly 90°** (perpendicular to side walls). | R | M | A | VERIFIED | SIDE-L/R measured **90.000°** from board pad midpoints (audit R2). |
| MMSE-WALL-2 | Diagonal IR sensor pairs shall aim **exactly 45°**, with the angle **shown precisely** on silk. | R | M | A/I | VERIFIED | DIAG-L/R = **45.000°**; silk "45°" callouts at both diagonal detectors (audit R2). |
| MMSE-WALL-3 | Front IR sensor pairs shall aim **completely straight (0°)**. | R | M | A | VERIFIED | FRONT-L/R = **0.000°** (both pads y=15) (audit R2). |
| MMSE-WALL-4 | LED (optic) silk outlines shall lie inside the board with a **3–5 mm** gap from the boundary. | R | M | A | VERIFIED | Bent-body silk U-outlines: min gap **3.24 mm** (DIAG-L to side edge) … 4.70 mm — inside the 3–5 mm window (audit R1). |
| MMSE-WALL-5 | The wall IR-sensor **indicator LEDs** shall be placed **behind** the wall sensors (toward the rear), not in front of them. | R | M | I | **OPEN** | *New frozen requirement (2026-07-19).* Current `WALL_IND_LED`: front pair D23/D24 at y=9 (**in front** of sensors at y=15); diagonal D25/D26 at y=12; side D27/D28 at y=35.5. Must move to y > sensor. → `MMSE-REM-5`. |

---

## 7. IMU (MMSE-IMU)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-IMU-1 | A **9-axis IMU** shall be fitted on the **centre line** of the PCB. | R | M | I | VERIFIED | BNO055 (U8) at x=50.0 (board centre), y≈59 (audit R5). 3.3 V-native LGA-28. |
| MMSE-IMU-2 | The IMU shall use its internal oscillator (external 32 kHz crystal dropped for routability). | R | S | A | VERIFIED | X1/C21/C22 absent; XIN32/XOUT32 = NC; SYS_TRIGGER CLK_SEL=0 (spec-supported). |

---

## 8. Controller & I/O (MMSE-CTRL)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-CTRL-1 | The controller shall be an ESP32-S3-WROOM-1 (N8R2) module. | R | M | I | VERIFIED | U3. |
| MMSE-CTRL-2 | USB-C connector shall be at the **rear** of the board. | R | M | I | VERIFIED | J7 (GCT USB4105) at rear edge. |
| MMSE-CTRL-3 | A JTAG header shall be placed **near** the ESP32. | R | S | I | VERIFIED | JTAG header ~16 mm edge-to-edge from U3, wired to the JTAG pins (audit R9 — "near" satisfied regionally). |
| MMSE-CTRL-4 | Buttons A / B / C + RST shall be present and **lettered** on silk. | R | M | I | VERIFIED | Silk letters A/B/C + RST; per-button reset near U3. |
| MMSE-CTRL-5 | GPIO assignment shall match the locked pin map and be firmware-gated. | R | M | T | VERIFIED | `fw/check_pins.py` — 29/29 pins verified against the netlist. |

---

## 9. Signal integrity / EMC / standards (MMSE-SI)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-SI-0 | **Impedance / grounding / standards compliance** | H | — | — | — | `pcb/STANDARDS.md`; audit R6. |
| MMSE-SI-1 | USB D+/D− shall be routed as a matched differential pair (full-speed). | R | M | A | PARTIAL | Routed as a pair; **intra-pair skew 5.76 mm** (functionally OK for FS; documented target ≤2.5 mm is not met). → `MMSE-REM-9`. |
| MMSE-SI-2 | Trace widths/clearances shall follow IPC-2221 class with controlled impedance where relevant. | R | S | A | PARTIAL | IPC clearance margin met (0.127 mm floor); doc claims (0.16 mm) don't match board; motor-phase traces 0.25 mm. Doc-accuracy issue, not a fab issue. |
| MMSE-SI-3 | The ESP32 module shall have **local decoupling (10 µF + 100 nF)** at its 3V3 pin per Espressif guidelines. | R | M | I | **FAILED (placement only)** | The caps **exist** (C10 10 µF + C8 100 nF, "Module decoupling") but are placed **51 mm** from U3 pin 2 (at (28,58)/(23.5,58)). Fix = MOVE them adjacent to U3 pin 2 (44, 110.7); NO schematic/netlist change. → `MMSE-REM-6`. |
| MMSE-SI-4 | **Ground shall be poured on the top layer and every other layer possible** (maximise ground plane / return path). | R | M | I | **OPEN** | *New frozen requirement (2026-07-19).* Current: F.Cu = mixed GND/3V3/VM pours; In1 = GND; In2 = 3V3; B.Cu = VM. Target: GND on F.Cu + In1 + B.Cu (In2 stays power plane) → `MMSE-REM-3`. |
| MMSE-SI-5 | ESD protection on the USB port. | R | S | I | VERIFIED | ESD array on D±. |
| MMSE-SI-6 | EN pins shall have RC de-bounce/pull networks per regulator datasheets. | R | S | A | VERIFIED | EN RC networks present (audit R6). |

---

## 10. Sourcing / BOM (MMSE-BOM)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-BOM-1 | Every component shall be orderable at **Lion Circuits** (turnkey from Digi-Key/Mouser/Element14/Arrow/Avnet/RS — not LCSC). | R | M | I | VERIFIED* | All 43 MPNs individually verified in-stock (2026-07); OOS JST-PH → B6B-XH-A. *Live stock is time-varying — re-check at order time.* |
| MMSE-BOM-2 | Every real BOM line shall carry a populated MPN + Manufacturer. | R | M | I | VERIFIED | `pcb/BOM.csv` — 49 lines, no blank MPN on real parts (motors are board-only). |
| MMSE-BOM-3 | Any decoupling/parts added by remediation shall also be Lion-orderable generic parts. | R | M | I | OPEN | Applies to the WROOM decoupling caps (`MMSE-REM-6`) — use standard 0402/0603 ceramics. |

---

## 11. Firmware (MMSE-FW)

| ID | Requirement | Type | Pri | VM | Status | Evidence / Notes |
|---|---|---|---|---|---|---|
| MMSE-FW-1 | Firmware pin map shall match hardware and be gated. | R | M | T | VERIFIED | `fw/check_pins.py` 29/29. |
| MMSE-FW-2 | A host-side control-core simulation shall pass its tracking scenarios. | R | S | T | VERIFIED | `fw/sim/sim_linefollow.c` — ALL SCENARIOS PASS. |
| MMSE-FW-3 | Analytical circuit tests shall pass with full net/component coverage. | R | S | T | VERIFIED | `circuit_tests.py` 41/41, 100 %/100 %. |

---

## 12. Verification method summary

| Method | Count | Where |
|---|---|---|
| **Test (T)** | DRC, ERC, check_pins, circuit_tests, sim | `verify_drc.py`, `circuit_tests.py`, `fw/*` |
| **Analysis (A)** | power tree, aim angles, clearances, connectivity | audit workflow, `trace_report.py`, `verify_netlist.py` |
| **Inspection (I)** | placement, silk, BOM, layers | renders, `BOARD_STATE.md`, `BOM.csv` |
| **Demonstration (D)** | (bring-up, physical) | deferred to first article |

**As-built rev 6.2 status roll-up:** VERIFIED 33 · PARTIAL 6 · OPEN 3 · FAILED 2 (of 44 leaf requirements).
The 2 FAILED (`MMSE-PCB-3` DRC, `MMSE-SI-3` decoupling) + 3 OPEN (`MMSE-WALL-5` indicators,
`MMSE-SI-4` GND pour, `MMSE-BOM-3`) are the rev-7 remediation scope below.

---

## 13. Remediation Register (rev 7 — the path to full compliance)

Each item is a tracked change with root cause, action, affected requirements, and
verification. These are the ONLY blockers to a fully error/warning-free, standards-
validated board.

| Rem ID | Root cause | Action | Satisfies | Verify by | Risk |
|---|---|---|---|---|---|
| **MMSE-REM-1** ✅ DONE | Custom optical/R-Q footprints carried ~0.7 mm courtyard margin → 20 of 32 errors. | **`pcb/tools/tighten_courtyards.py`** (text-level, robust vs SWIG flakiness) shrinks the courtyard rects to body+pad+0.13 mm (IPC-7351C "Least"). Applied: **32 → 12 errors**, ratsnest still 0, 0 warnings. Run after `build_pcb.py` in the pipeline. | MMSE-PCB-3 | `verify_drc.py`: confirmed 12 errors (was 32). | Low — no part moved; IPC-compliant. |
| **MMSE-REM-2** | ~10 residual `pth_inside_courtyard`: top-side wall-sensor through-hole pads sit within a bottom-side line-sensor body outline (opposite sides). Copper clearance IS met (0 `clearance` errors) — courtyard-convention only. | Either (a) shift the front wall sensors into the line-array gaps / rotate leads vertical, or (b) mark as reviewed KiCad exclusions justified by measured ≥0.25 mm clearance meeting IPC-2221. Prefer (a). | MMSE-PCB-3 | `verify_drc.py` → 0 errors. | Med (placement + local reroute). |
| **MMSE-REM-3** | GND pour not maximised (F.Cu mixed; B.Cu = VM). | Re-pour: GND on F.Cu + In1 + B.Cu; In2 stays 3V3 power plane; VM as localised islands/traces. Requires reroute (pour-fed connectivity changes). | MMSE-SI-4 | ratsnest 0 after re-pour; `verify_drc.py`. | Med-High (connectivity). |
| **MMSE-REM-4** ✅ tooling done | Project routed/gated with `--severity-warning` for its whole history. | Tooling now error-inclusive (`verify_drc.py` / `export_fab` gate / `finalize`). Since ALL remaining changes (REM-2/3/5/6/7) are **placement/pour only — no netlist change** — they are done **in-place on the routed board** with LOCAL reroutes of the moved parts' nets; a full 2 h regenerate+reroute is NOT required. | MMSE-PCB-3/6 | `verify_drc.py`. | Low-Med. |
| **MMSE-REM-5** | Wall indicator LEDs placed in front of their sensors. | Move D23–D28 to y > their sensor y (behind); reroute their nets. | MMSE-WALL-5 | inspection + ratsnest 0. | Med. |
| **MMSE-REM-6** | C10/C8 decoupling caps exist but sit 51 mm from U3 pin 2. | **MOVE** C10 (10 µF) + C8 (100 nF) adjacent to U3 pin 2 (44, 110.7); reroute their 2 PLUS3V3 + 2 GND nets (pour-fed, local). No schematic/BOM change. | MMSE-SI-3 | inspection; distance < 5 mm. | Low — placement + local reroute. |
| **MMSE-REM-7** | D25 F.Fab nicks the left chamfer (~0.22 mm). | Nudge D25 inward ≥0.3 mm. | MMSE-MECH-2 | DRC `copper_edge_clearance` / body-inside gate. | Low. |
| **MMSE-REM-8** | Double-stall current corner exceeds buck rating. | (Accept) firmware PWM current-limit + PPTC; document as operating constraint. | MMSE-PWR-3 | analysis. | Low. |
| **MMSE-REM-9** | USB intra-pair skew 5.76 mm vs 2.5 mm doc target. | Length-match D± during reroute, or correct the doc target (FS-USB tolerant). | MMSE-SI-1 | trace-length report. | Low. |

**Execution order (rev 7 — all IN-PLACE, no regenerate):**
REM-1 (courtyards) ✅ → REM-6 (move C10/C8 to U3) → REM-5 (indicators behind) →
REM-7 (D25 nudge) → REM-3 (GND-everywhere pours) → REM-2 (front 10: IPC-2221
exclusions or ~0.5 mm moves) + 2 diagonal-LED nudges → local reroute of moved
nets → `verify_drc.py` = 0 errors / 0 warnings + ratsnest 0 → full battery →
regenerate fab package → set statuses VERIFIED → fab.
Because nothing changes the netlist, the routed board (and its hard-won USB/
closure work) is preserved; only moved parts' nets are re-routed.

---

## 14. Traceability (requirement → verifying artifact)

| Requirement group | Verifying artifact(s) |
|---|---|
| MECH | `board_geom.py`, renders, audit R1/R8 |
| PCB/DRC | `verify_drc.py`, `export_fab.py` gate, `BOARD_STATE.md` |
| PWR | `circuit_tests.py`, `trace_report.py`, audit R4/R7 |
| LINE/WALL | `build_pcb.py` WALL_GEOM, audit R1/R2, silk callouts |
| IMU | audit R5, `verify_netlist.py` |
| CTRL | `check_pins.py`, audit R9 |
| SI/EMC | `STANDARDS.md`, audit R6 |
| BOM | `BOM.csv`, HANDOFF §10 |
| FW | `check_pins.py`, `circuit_tests.py`, `fw/sim` |

---

## 15. Change log

| Date | Change |
|---|---|
| 2026-07-19 | Module created. Baselined rev 6.2 as-built; recorded the `--severity-warning` DRC-masking defect and the true 32-error state; added frozen requirements MMSE-WALL-5 (indicators behind) and MMSE-SI-4 (GND everywhere); opened Remediation Register for rev 7. |
