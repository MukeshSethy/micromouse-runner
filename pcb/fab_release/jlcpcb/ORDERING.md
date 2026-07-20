# JLCPCB ordering — micromouse PCB rev 7.2

Same board as the Lion package (identical gerbers + placement). Only the BOM
part numbers are JLCPCB/LCSC-specific. Files are in JLC's exact upload formats
(matched to JLCPCB's own `Sample-BOM_JLCSMT` / `JLCSMT_Sample_CPL`).

**JLC assembles the whole board — SMD *and* through-hole.** Every part (incl.
the JST/USB-C/XT60 connectors, the tact buttons, the 5 mm IR optics and the
TCRT5000s) is in JLC's library, so with **Standard PCBA** it's fully turnkey —
no hand-soldering. So there is ONE combined BOM and ONE combined CPL below.

## Files
| File | Use |
|---|---|
| `micromouse-pcb-rev7.2-jlcpcb-gerbers.zip` | **PCB** tab → upload (Gerber X2 + Excellon drill, flat) |
| `BOM_JLC-assembly.xlsx` | **Assembly** → BOM (all 54 lines). Columns: `Comment, Designator, Footprint, JLCPCB Part #（optional）` |
| `CPL_JLC-assembly.xlsx` | **Assembly** → CPL/placement (all 177 parts). Columns: `Designator, Mid X, Mid Y, Layer, Rotation` |
| `THT_parts_reference.csv` | info only — the 14 through-hole lines, so you can see the THT cost delta (or deselect them for the Economy route) |

## Pick the right assembly tier
- **Standard PCBA** (use this) — assembles SMD **and** through-hole. THT is
  wave/selective/hand-soldered: **~$3.50 flat + ~$0.017 per joint** (~$5–7 for
  this board's ~110 THT joints) and **+1 day**. Fully turnkey.
- **Economy PCBA** — *SMD only*, cheaper, ≤ some qty. If you choose this,
  deselect the 14 `THT_parts_reference.csv` lines in JLC's BOM step and
  hand-solder those yourself (order them loose — LCSC #s are in that file).

## Board options
4 layers · 100 × 120 mm · 1.6 mm · default JLC 4-layer stackup (no controlled
impedance — USB is full-speed) · 1 oz outer copper. HASL or ENIG both fine.

## Part changes vs the design MPNs (footprint- & value-compatible)
| Design part | JLCPCB part | Why |
|---|---|---|
| Passive R/C (Yageo RC0805, Samsung CL21) | JLC **Basic** UNI-ROYAL 0805W8F / Basic MLCC — value·size·1 %·dielectric identical | kills the per-part setup fee; always in stock |
| 39 k (R3) | Yageo `RC0805FR-0739KL` = **C113306** | the Basic 39 k was out of stock; kept the exact part |
| 10 µF/25 V & 22 µF/25 V **1210** (C1/4/11/18, C16/17) | Extended 1210 MLCC (**C39232**, **C307586**) | no Basic 1210 exists at these values; same footprint, ≥25 V |
| F1 fuse `MINISMDC350F/16-2` | BHFUSE `BSMD1812-300-16V` = **C883162** | exact Littelfuse MPN not on LCSC; same 1812/16 V, 3.0 A-hold (design intent 2.6 A) — **verify trip current** |
| J8 JTAG header, Wurth `61300611121` | generic 1×6 / 2.54 mm male header = **C124380** | Wurth MPN not on LCSC; same footprint |

Every other part — including all the through-hole optics and connectors —
keeps its exact design MPN (LCSC numbers are in the BOM). Tier: apart from the
Basic passives above, the ICs/discretes are "Economic & Standard" parts that
currently carry **no** per-part setup fee.

## Before you hit order — three checks
1. **Rotations.** Mid X/Y already match the gerber frame exactly (the CPL uses
   KiCad's native coordinates — the board sits at X 0–100, Y 0 to −120 mm, so
   **Mid Y is negative and that is correct**; do not "normalise" it or it
   desyncs from the fab data). But KiCad and JLC disagree on the *zero-rotation
   reference* for some packages. In JLC's placement preview, eyeball pin-1 /
   polarity on: **U1 U2 U3 U4 U6 U7 U8**, the electrolytic **C30**, diode
   **D29**, the SOT-23 transistors **Q1 / Q16–Q27 / Q28–Q33 / Q34**, the LEDs
   **D15–D28**, and the polarised connectors **J1 J5 J6 J9 J10** / USB-C **J7**.
2. **J10 (XT60).** It's a big high-current through-hole part and optional (the
   parallel-battery option, ONE PACK ONLY). JLC normally solders it under
   Standard PCBA, but if the review flags it as not-assemblable just set it to
   "Do Not Place" and hand-fit it — it's a one-minute job. The robu N20 motor
   cable plugs straight into J5/J6 (JST-ZH) — meter-check the cable's VCC/GND
   (positions 2/5) before first plug-in.
3. **Stock.** These read low/variable at time of writing — check live qty and
   order promptly (or pre-approve a substitute): **BNO055** (C93216, ~505),
   **SRP4020TA-4R7M** (C2041623, ~806), **110 k** (C17422).
