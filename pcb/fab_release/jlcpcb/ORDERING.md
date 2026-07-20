# JLCPCB ordering — micromouse PCB rev 7.2

Same board as the Lion package (identical gerbers + placement). Only the BOM
part numbers are JLCPCB/LCSC-specific. Files here are in JLC's exact upload
formats (matched to JLCPCB's own `Sample-BOM_JLCSMT` / `JLCSMT_Sample_CPL`).

## Files
| File | Use |
|---|---|
| `micromouse-pcb-rev7.2-jlcpcb-gerbers.zip` | **PCB** tab → upload (Gerber X2 + Excellon drill, flat) |
| `BOM_JLCSMT.xlsx` | **Assembly** → BOM. Columns: `Comment, Designator, Footprint, JLCPCB Part #（optional）` |
| `CPL_JLCSMT.xlsx` | **Assembly** → CPL/placement. Columns: `Designator, Mid X, Mid Y, Layer, Rotation` |
| `THT_hand-solder_parts.csv` | NOT a JLC upload — the through-hole parts to order loose and hand-solder |

## Board options
4 layers · 100 × 120 mm · 1.6 mm · default JLC 4-layer stackup (no controlled
impedance — USB is full-speed) · 1 oz outer copper. HASL or ENIG both fine.

## What SMT assembly covers (and what it doesn't)
`BOM_JLCSMT.xlsx` + `CPL_JLCSMT.xlsx` describe the **146 SMD placements** JLC's
line assembles: the ESP32 module, all ICs, every 0805/1210 R & C, the SOT-23
discretes, the 0603 indicator LEDs, the SMD buzzer, the SMD slide switches and
the PPTC fuse.

The **14 through-hole line items** in `THT_hand-solder_parts.csv` (JST/XT60/
USB-C connectors, the 6 mm tact buttons, the 5 mm IR emitters/phototransistors
and the TCRT5000s, the JTAG header) are **not** placed by economic SMT. Order
them loose (LCSC #s are in that file) and hand-solder, or add JLC's separate
THT/hand-soldering service. J10 (XT60) is optional — fit only if your pack lead
is XT60 (ONE PACK ONLY). The robu N20 motor cable plugs straight into J5/J6
(JST-ZH) — meter-check the cable's VCC/GND (positions 2/5) before first plug-in.

## Part changes vs the design MPNs (footprint- & value-compatible)
| Design part | JLCPCB part | Why |
|---|---|---|
| Passive R/C (Yageo RC0805, Samsung CL21) | JLC **Basic** UNI-ROYAL 0805W8F / Basic MLCC — value·size·1 %·dielectric identical | kills the per-part setup fee; always in stock |
| 39 k (R3) | Yageo `RC0805FR-0739KL` = **C113306** | the Basic 39 k was out of stock; kept the exact part |
| 10 µF/25 V & 22 µF/25 V **1210** (C1/4/11/18, C16/17) | Extended 1210 MLCC (**C39232**, **C307586**) | no Basic 1210 exists at these values; same footprint, ≥25 V |
| F1 fuse `MINISMDC350F/16-2` | BHFUSE `BSMD1812-300-16V` = **C883162** | exact Littelfuse MPN not on LCSC; same 1812/16 V, 3.0 A-hold (design intent 2.6 A) — **verify trip current** |
| J8 JTAG header, Wurth `61300611121` | generic 1×6 / 2.54 mm male header = **C124380** | Wurth MPN not on LCSC; same footprint |

Every other part keeps its exact design MPN (LCSC numbers are in
`BOM_JLCSMT.xlsx` / `THT_hand-solder_parts.csv`). Tier: apart from the Basic
passives above, the ICs/discretes are "Economic & Standard" parts that
currently carry **no** per-part setup fee.

## Before you hit order — two checks
1. **Rotations.** Mid X/Y already match the gerber frame exactly (the CPL uses
   KiCad's native coordinates — the board sits at X 0–100, Y 0 to −120 mm, so
   **Mid Y is negative and that is correct**; do not "normalise" it or it
   desyncs from the fab data). But KiCad and JLC disagree on the *zero-rotation
   reference* for some packages. In JLC's placement preview, eyeball pin-1 /
   polarity on: **U1 U2 U3 U4 U6 U7 U8**, the electrolytic **C30**, diode
   **D29**, the SOT-23 transistors **Q1 / Q16–Q27 / Q28–Q33 / Q34**, and the
   LEDs **D15–D28**. Rotate in the editor if any look flipped, then confirm.
2. **Stock.** These read low/variable at time of writing — check the live qty
   and order promptly (or pre-approve a substitute): **BNO055** (C93216, ~505),
   **SRP4020TA-4R7M** (C2041623, ~806), **110 k** (C17422).
