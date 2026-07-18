# HANDOFF — micromouse-pcb rev 6.1 (continue on another machine)

**Purpose:** everything needed to finish this board on a fresh machine with
Claude Code, adding nothing from the human. Read this top to bottom first,
then `pcb/PROJECT_NOTES.md` (full design log) and `pcb/CONNECTIONS.md`
(every net, every pin, why).

**Status in one line:** design + firmware + verification are COMPLETE and
passing; the PCB is routed to **5 remaining unconnected edges** (exact list
in §6). Finishing = close those 5, run `finalize.py` + `sync_board_meta.py`,
regenerate fab + docs. Est. 1–3 h of routing-closure work.

---

## 0. HARD CONSTRAINTS (identity / security — never violate)

- **Never** use the Rapyuta work email (`Mukesh@rapyuta-robotics.com`) for
  anything in this repo. Commits are authored as
  `Mukesh Sethy <43363581+MukeshSethy@users.noreply.github.com>` (set
  repo-locally: `git config user.email` already returns the noreply address —
  verify before committing).
- Push through the existing MukeshSethy GitHub login via Git Credential
  Manager (transparent). **Never** run `git credential fill` or otherwise
  extract/materialize cached credentials (a guardrail blocks it).
- End commit messages with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` (or the current
  model's noreply, matching prior commits).
- Repo: `github.com/MukeshSethy/micromouse-runner`, branch `main`.

## 1. TOOLCHAIN (Windows, this machine's paths — adjust on a new box)

- KiCad 10.0.4. **kicad python** (pcbnew, board mutation):
  `C:\Program Files\KiCad\10.0\bin\python.exe`
- **kicad-cli** (ERC/DRC/netlist/gerbers/render/step/bom):
  `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
- **msys python** (pure text work, S-expression surgery, no pcbnew):
  `C:\msys64\ucrt64\bin\python3.exe`
- gcc (host firmware sim): msys/ucrt64 gcc.
- **Always** set `TEMP=D:\tmp TMP=D:\tmp` before kicad tools (they need a
  writable temp; the default was read-only here). Adjust to a writable dir.
- Filter kicad noise in shells: `2>&1 | grep -viE "memory leak|duplicate image"`.

## 2. THE #1 GOTCHA — connectivity is measured by the RATSNEST, not kicad-cli

`kicad-cli pcb drc` **under-reports "unconnected" headless** — it does not
rebuild the ratsnest the way the GUI does, and has reported "0 unconnected"
on a board that actually had 51. **NEVER trust its unconnected number.** The
truth is the pcbnew ratsnest after a zone fill:

```python
import pcbnew
b = pcbnew.LoadBoard(BOARD)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
print(b.GetConnectivity().GetUnconnectedCount(True))   # <-- the real count
```

The exact-unconnected-nets helper is
`C:\...\scratchpad\find_unconn2.py` (copy its body — it compares pad cluster
membership by POSITION, because SWIG wrappers make `id()` comparison useless).
A copy is inlined in §6. **`finalize.py` is ratsnest-gated** and will abort if
the board is not already ratsnest-0, so run the closure BEFORE finalize.

## 3. SWIG TRAPS (KiCad pcbnew Python — will waste hours if unknown)

1. `board.GetTracks()` / `GetDrawings()` return a non-iterable SwigPyObject
   **after** you call `GetFootprints()` (or iterate pads) in the same process.
   **Fix:** snapshot the collection you need FIRST (`tracks = list(board.GetTracks())`
   and cache each track's geometry into plain tuples) before touching
   footprints. `finalize.py` does this correctly — copy its pattern.
2. `board.Remove(item)` mid-loop corrupts `fp.Zones()` used by
   `_verify_geo`'s keepout check. **Do track/via removal TEXT-LEVEL**
   (S-expression walk of `.kicad_pcb`) — see the strip snippet in §6.3, or do
   all `Remove`s at the very end.
3. `fp.Models()` returns a SWIG copy — repoint 3D models text-level.
4. Heredoc `\n`/`\` corruption in bash: **never** inline Python with
   backslashes via heredoc; use the Write tool to a `.py` file then run it.
5. `Date.now()`/`random` are fine here (plain python), only banned inside the
   Workflow sandbox.

## 3a. HOW THE USER WANTS HARDWARE WORK DONE (standing working-style)

- ERC/DRC validate netlists, not physical reality. Every bug that mattered on
  this project (header shape, header pin order, PMOS orientation, sensor
  facing, the motor-EN divider) was invisible to ERC/DRC and only caught by
  comparing against datasheets / manufacturer photos / reference designs, or
  by writing per-connection justifications. So: **verify footprints & pinouts
  against datasheets/photos before trusting library defaults; when you find
  one instance of an error class, sweep the WHOLE design for it; keep
  `CONNECTIONS.md` coverage-enforced.**
- The user works long offline stretches — **keep going autonomously** through
  token/time limits, make reasonable calls, and document flagged risks in
  `PROJECT_NOTES.md` rather than stopping to ask.

## 4. THE DESIGN (rev 6.1) — what this board is

100×120 mm, 4-layer (F.Cu sig / In1 GND plane / In2 +3V3 plane / B.Cu
sig+pours). Fully SCRIPT-GENERATED — the schematic and PCB are emitted by
Python, so everything is auditable and regeneratable.

**All 10 rev-6 user requirements — 8 DONE, 2 (marked ⏳) finished by the §6
closure:**
1. ✅ Sensor silk outlines fully INSIDE the board, 3–5 mm edge gap
   (`_outline_gap_check` gate in build_pcb.py; enforces ≥3.0, actual 4.2–4.7).
2. ✅ Exact wall-sensor aims: front **0°**, diagonal **45.0°**, side **90.0°**,
   with silk angle-number callouts.
3. ⏳ DRC **0 errors AND 0 warnings** — the mechanism is in place (full
   `--severity-warning` incl. parity; `finalize.py` + `sync_board_meta.py`
   produced 0/0/0 on the rev-6.0 board). NOT yet true on the current board:
   it has 5 unconnected + ~220 pre-finalize silk/dangling warnings. Achieved
   after §6 closure → finalize → sync_board_meta.
4. ✅ **2S LiPo**, motors on a **regulated 6.0 V** rail (TPS54302 buck, steady
   V + 3 A current limit + C30 220 µF bulk).
5. ✅ **BNO055 9-axis IMU** on the board centerline (x=CX; I2C IO18/21, INT IO37).
6. ✅ Impedance / IPC / Espressif standards — `pcb/STANDARDS.md`.
7. ✅ **Two switches**: SW5 = PWR ALL (3V3 EN, everything-except-motors),
   SW6 = PWR MOTORS (6V EN); motors require both on.
8. ✅ Nothing outside the board outline except the motor shafts; the WROOM
   antenna spans a rear-edge U-notch (Espressif fallback), tip inside.
9. ⏳/✅ All prior (rev ≤5) requirements retained (buttons A/B/C+RST lettered,
   rear USB-C, JTAG, wall+line indicator LEDs with "wall LED ON = wall seen",
   mux for the line array only + walls direct to ADC1, 0.3 mm THT clearance,
   UKMARS bracket + STL link, exact WROOM-1/N20 libs). The one rev-5 rule
   still pending is "all lines routed, nothing left behind" = the same §6
   5-edge closure as #3.
10. ✅ BOM only from **Lion Circuits** in-stock parts (turnkey: Digi-Key/Mouser/
    Element14/Arrow/Avnet/RS — **NOT LCSC**). `pcb/BOM.csv` regenerated with
    the rev-6 parts (49 rows).

**Power tree:** 2S pack (JST-XH) → F1 (MINISMDC260F/16, 2.6A/16V PPTC) → Q1
(DMP3098L reverse P-FET, Vgs ±20V) → VM_BATT → **AP63203** (3.3V/2A logic) +
**TPS54302** (6.0V/3A motors, FB 100k/11k). Balance tap J9 → per-cell monitor
via mux. IN/IN motor drive (PWMA/PWMB/STBY tied high). USB direct D± (no
series R). External IMU crystal was DROPPED (§5).

**Key part numbers (all Lion-Circuits In-Stock, verified 2026-07):**
U1 AP63203WU-7, U7 TPS54302DDCR, U2 TB6612FNG, U3 ESP32-S3-WROOM-1-N8R2,
U4 CD74HC4067M96, U6 USBLC6-2SC6, U8 BNO055, Q1 DMP3098L-7, L1/L2
SRP4020TA-4R7M, F1 MINISMDC260F/16-2, J1/J9 JST-XH, J7 USB4105-GF-A,
SW5/SW6 PCM12SMTR, SW1-4 PTS645VL582LFS, C30 EEE-FT1C221AP, wall emitters
IR333-A, wall PT PT334-6B, line TCRT5000.

## 5. DESIGN DECISIONS the next machine must NOT undo

- **IMU external crystal dropped (rev 6.1).** X1/C21/C22 removed; BNO055 runs
  its internal oscillator (Adafruit default, spec-supported; firmware leaves
  SYS_TRIGGER.CLK_SEL=0). Reason: XIN32/XOUT32 are north-row LGA-28 pads and
  were genuinely unroutable at 3.2 mm from a 0.5 mm-pitch part; hand paths +
  A* to 8M expansions + crystal relocation all failed. Do NOT re-add it.
- **Motor-rail EN bug (caught by circuit_tests P10, fixed).** R69 was 1M and
  in series with the R70/R71 MOT_EN divider it sagged TPS54302 EN to 0.64V
  (< 1.21V threshold) — motors could never enable. Fixed R69→100k, R70→220k.
  Do NOT revert.
- **`lib_footprint_mismatch` is set to `ignore`** in the `.kicad_pro` DRC
  severities — footprints are DELIBERATELY customized (refdes moved to F.Fab
  for a clean silk). Every other check stays at error/warning.

## 6. THE REMAINING WORK — close these 5 unconnected, then finish

Board state: `pcb/micromouse-pcb.kicad_pcb`, **1674 tracks / 373 vias,
5 unconnected edges** (pcbnew ratsnest). This is the raw route_loaded+heal
output and matches the source exactly. The 5 (with EXACT coordinates, mm):

| Net | Pad A | Pad B | Difficulty | Approach |
|---|---|---|---|---|
| `Net-(Q28-D)` | R49.1 (26.09, 38.0) | Q28.3 (25.94, 43.0) | EASY | `retry_edge(w=0.25, clr=0.18, grid=0.1, 800k)` — routed cleanly in testing |
| `PLUS3V3` | C13.1 (15.85, 49.0) | U2.23 (67.5, 63.08) | EASY | both are on separate plane islands — drop a via near each into the In2 plane: `scan_via` box (16.4,48.2,18.0,50.5) and (68.4,62.4,70.0,64.4) |
| `Net-(Q1-G)` | Q1.1 (25.06, 53.05) | R1.1 (26.91, 54.0) | MED | gate pad boxed (open-set-empty) — place a hand escape via off Q1.1 (try (24.5,52.6),(25.06,52.3),(24.4,53.05)), then `retry_edge` via→R1.1 |
| `USB_DM_C` | J7.A7 (54.25, 112.0) | J7.B7 (53.25, 112.0) | HARD | see USB note below |
| `USB_VBUS` | J7.A4 (51.6, 112.0) | J7.A9/B4 (56.4, 112.0) | HARD | see USB note below |

### 6.1 The USB-C fanout (the genuinely hard part)

J7 (USB4105 16-pin) interleaves the A/B rows: along +x the pads are
B7(53.25,DM) A6(53.75,DP) A7(54.25,DM) B6(54.75,DP) — so a same-net pair (A7/B7
= D-) is separated by the D+ pads and must bridge UNDER them on an inner layer.
The **root blocker** is that the CC pull-down resistors **R56 (CC2) and R12
(CC1)** sit in the connector's south escape zone (R56.1 at 52.91,110.5),
boxing every dive. **Proven fix (do this in build_pcb.py source + reroute, OR
as a board hand-edit):**
1. Move R56 and R12 SOUTH out of the escape zone, e.g. R56→(60,108.5),
   R12→(64.5,108.5) (verify clear of ENC2/R67/R68 first — dump the area).
2. Route CC1 (J7.A5 52.75,112 → R12.1) and CC2 (J7.B5 55.75,112 → R56.1)
   diving to an inner layer immediately (they were rerouted OK once R56/R12
   moved — but match the ACTUAL moved pad coords, which I got wrong once).
3. Bridge D- A7↔B7: F stub → via → **B.Cu** hop under the D+ pads → via → F
   (depth y≈110.6 worked: `[(54.25,112)→(54.25,110.6)F, →(53.25,110.6)B.Cu,
   →(53.25,112)F]` with vias at both dive points — this SUCCEEDED once R56
   was moved).
4. Bridge VBUS A4↔A9/B4 similarly but on a DIFFERENT layer (In2) so it does
   not clash with the D- vias (the failure once was "too close to via of
   USB_DM_C" — separate the dive x or layer).
5. R56/R12 pad-2 (GND) → via to the In1 GND plane.

`route_loaded.py` already has a generic `_bridge()`/`_jpad()` USB stage
(stage 1) — it currently fails because R56 boxes it; moving R56/R12 in
build_pcb should let that stage succeed on a fresh reroute. **Preferred path:
put the R56/R12 relocation into build_pcb.py, rebuild, reroute** (clean +
reproducible) rather than hand-editing the board.

### 6.2 Closure loop + the escape-via technique (self-contained; memory does NOT travel)

**Boilerplate:** the committed `pcb/tools/heal_all.py` function `load()` is the
exact PcbGen setup you need — it loads the board and populates
`g._nets/_placed/_outline_pts/_extra_keepouts/_track_segs/_vias/_pads_geo_cache`.
Import/copy it, then route with `g.retry_edge(net, a, b, width_mm=, clearance_mm=,
grid_mm=, max_expansions=)` and/or hand copper:
`g._verify_geo(segs, vias, net, 0.125)` returns `None` if clear (else the exact
reason string), then `g.add_track(a,b,layer,net,0.25)` /
`g.add_via((x,y),net)` and append to `g._track_segs`/`g._vias`. Finish with
`g.fill_zones()` / `pcbnew.SaveBoard`, then **re-check the ratsnest (§2)**.
Cap `max_expansions` at ≤1M — higher budgets STALL for hours in dense areas;
kill and hand-route instead.

**Escape-via technique (the proven method for a boxed pad — "open-set-empty"):**
1. Dump copper in a ~2 mm box around the pad using SEGMENT-BOX SAMPLING (walk
   each track and sample points along it — endpoint-only filters miss
   pass-through tracks), plus every nearby pad rect with its size.
2. Ask `g._verify_geo([(pad, via, F_Cu)], [via], net, 0.125)` for the exact
   rejection, then GRID-SCAN candidate via positions (step 0.05–0.12) against
   the verifier and build a reason HISTOGRAM — the scan finds the legal spot
   when hand geometry is wrong (it was wrong twice, the scan never was).
3. Order matters when a sibling net's track blocks you: strip that track,
   commit YOUR crossing FIRST, machine-reroute the sibling LAST.

**Verifier clearance floors** (track half-width 0.125, obstacle clr 0.16):
via↔other-net-pad-edge ≥0.46; via↔other-net-track ≥0.725 (LAYER-BLIND — an
inner-layer track still blocks a via!); via↔via ≥0.76; track↔track same-layer
≥0.41; track↔pad-edge ≥0.285. SSOP-24 tails are 1.75 mm — escape BETWEEN pad
rows under the body, not outside.

### 6.3 Text-level track strip (safe; use instead of board.Remove)

```python
P = r"...\micromouse-pcb.kicad_pcb"; s = open(P,encoding="utf-8",newline="").read()
out=[]; i=0; n=len(s); rem=0
while i<n:
    j=s.find("\t(segment",i); k=s.find("\t(via",i)
    nxt=min(x for x in (j,k,n) if x!=-1)
    if nxt==n: out.append(s[i:]); break
    out.append(s[i:nxt]); depth=0; e=nxt
    while e<n:
        if s[e]=="(":depth+=1
        elif s[e]==")":
            depth-=1
            if depth==0: e+=1; break
        e+=1
    if e<n and s[e]=="\n": e+=1
    blk=s[nxt:e]
    if '(net "NETNAME")' in blk: rem+=1     # <-- match by net NAME
    else: out.append(blk)
    i=e
open(P,"w",encoding="utf-8",newline="").write("".join(out)); print("stripped",rem)
```

## 7. FINISH SEQUENCE (once ratsnest == 0)

Run in order (all from repo root, with `TEMP/TMP` set):

```bash
KPY="C:/Program Files/KiCad/10.0/bin/python.exe"
CLI="C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"

# 1. finalize: silk→fab, drop angle rays, relocate labels, ratsnest-gated stub
#    strip + hole de-stack. Run REPEATEDLY until "violations=0" (it converges
#    over ~8 passes; the copper strip cascades). It ABORTS if ratsnest≠0.
for i in $(seq 8); do "$KPY" pcb/tools/finalize.py; done

# 2. schematic-parity metadata (FPID + Value + Datasheet + MPN + board_only)
"C:/msys64/ucrt64/bin/python3.exe" pcb/tools/sync_board_meta.py

# 3. full DRC — target 0/0/0 (violations / unconnected / parity)
"$CLI" pcb drc --schematic-parity --severity-warning --format json \
  --output pcb_drc.json pcb/micromouse-pcb.kicad_pcb
# check: violations==0, unconnected==0 (BUT re-confirm with the pcbnew ratsnest!), parity==0

# 4. verification battery (all currently PASS)
"$CLI" sch erc --severity-error pcb/micromouse-pcb.kicad_sch          # 0
"$KPY" pcb/tools/verify_netlist.py                                    # ALL PASSED
"$KPY" pcb/tools/circuit_tests.py                                     # 41/41, 100%/100%
"$KPY" fw/check_pins.py                                               # 29 pins
gcc -O2 -I fw/micromouse -o /d/tmp/sim fw/sim/sim_linefollow.c fw/micromouse/control_core.c -lm && /d/tmp/sim   # ALL SCENARIOS PASS
"$KPY" pcb/tools/trace_report.py                                     # TRACE_REPORT.md
"$KPY" pcb/tools/export_fab.py                                       # gerbers/drill/pos/step/BOM, ALL GATES PASSED

# 5. renders
"$CLI" pcb render --side top    --quality high -o renders/rev6-top.png    pcb/micromouse-pcb.kicad_pcb
"$CLI" pcb render --side bottom --quality high -o renders/rev6-bottom.png pcb/micromouse-pcb.kicad_pcb
```

## 8. FULL REGENERATE-FROM-SOURCE ORDER (if rebuilding the board)

```
build_schematic.py  → kicad-cli sch erc → kicad-cli sch export netlist
  → verify_netlist.py → gen_connections.py → build_pcb.py
  → route_loaded.py (≈1.7 h) → heal_all.py → [close remaining, §6]
  → finalize.py (×8) → sync_board_meta.py → export_fab.py
```
`board_geom.py` is the single source of mechanical truth (outline, notches,
mount holes, antenna notch) — never duplicate its numbers.

## 9. WHAT IS ALREADY DONE (do not redo)

- Schematic: ERC 0, 147 nets, `verify_netlist.py` ALL PASSED.
- `circuit_tests.py`: **41 PASS / 0 FAIL, 100% net + 100% component coverage**
  (caught + fixed the motor-EN bug). → `pcb/TEST_REPORT.md`.
- `pcb/CONNECTIONS.md`: 147 nets documented, 0 missing (coverage-enforced).
- Firmware `fw/micromouse/` (IN/IN drive, 4-sel mux + battery telemetry,
  BNO055 internal-osc driver, 2S per-cell cutoffs); `check_pins.py` 29/29;
  host sim ALL SCENARIOS PASS.
- `pcb/STANDARDS.md` (impedance/IPC/Espressif), `pcb/PROJECT_NOTES.md`
  (full rev-6 log incl. the connectivity trap + crystal-drop story).
- README updated for rev 6.
- Board: placed clean (all build gates pass: outline-gap, body-inside,
  silk-vs-pad, ring-clearance, THT-margin, 530 pins mapped), routed to 5
  unconnected.
- `pcb/BOM.csv` regenerated with the rev-6 parts (49 rows, no rev-5 leftovers).
- Renders `renders/rev6-{top,bottom}.png` + `images/render_{top,bottom}.png`
  regenerated from the crystal-free board (pre-finalize state).
- `finalize.py` (ratsnest-gated) + `sync_board_meta.py` are written & tested
  (they produced 0/0/0 on the rev-6.0 board before the crystal-drop rework).
  NOTE: finalize's `ANGLE_POS`/`LETTER_POS` silk targets were scanned on the
  rev-6.0 layout; sensor positions are unchanged in 6.1, but if silk_over_copper
  warnings persist after finalize, re-scan clear spots (see the scanner idea in
  PROJECT_NOTES) and update those two lists in `finalize.py`.

## 10. FILE INVENTORY

- `pcb/tools/build_schematic.py` — schematic generator (single source).
- `pcb/tools/build_pcb.py` — placement + build gates. **The R56/R12 escape-zone
  relocation (§6.1) should be added here.**
- `pcb/tools/gen_pcb.py` — the in-house 4-layer A* router core (`retry_edge`,
  `_verify_geo`, `route_net`, `add_track/add_via`, `fill_zones`, keepouts).
- `pcb/tools/route_loaded.py` — routing pipeline (has the USB `_bridge` stage).
- `pcb/tools/heal_all.py` — DRC-driven micro-route/via healer (note: it reads
  kicad-cli unconnected, which is unreliable — trust the ratsnest after).
- `pcb/tools/finalize.py` — silk→fab + ratsnest-gated copper cleanup.
- `pcb/tools/sync_board_meta.py` — board↔schematic metadata (parity=0).
- `pcb/tools/board_geom.py` — mechanical truth. `verify_netlist.py`,
  `gen_connections.py`, `circuit_tests.py`, `trace_report.py`, `export_fab.py`.
- `fw/` — firmware + host sim + `check_pins.py`.
- `pcb/{PROJECT_NOTES,CONNECTIONS,STANDARDS,TEST_REPORT,TRACE_REPORT}.md`.
