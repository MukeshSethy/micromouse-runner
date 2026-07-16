# Micromouse PCB — Project Knowledge & Progress Log

This file is the living source of truth for this project: requirements, decisions made, research findings, and what's actually been built. Update it whenever a decision changes or a new sheet/part is completed — don't let it drift from reality.

## Requirements (as given by the user)

- Full-size micromouse robot PCB, built from scratch in KiCad.
- 6 IR sensors for wall detection + 8 IR sensors for line following (14 total).
- STM32 dev board with an Arduino-Nano-compatible footprint, socketed (not soldered direct).
- TB6612FNG motor driver.
- N20 gearmotors.
- ESP32 module for wireless comms with the user's laptop — both flashing the STM32 and telemetry data to/fro.
- "Take inspiration from other projects online" — researched, see below.
- "Remember to use IR emitters and receivers correctly" — see IR sensor circuit section below.
- User wants "the best [MCU board] with more IO pins and speed" — see component decisions.
- Sensor mounting: single flat PCB (no perpendicular daughter boards) — angled sensors done via bent THT leads.
- ESP32 role: both telemetry AND flashing (higher-risk option — no proven WiFi bootloader-relay prior art found, only Bluetooth SPP).
- Project lives at `D:\Projects\micromouse-pcb`, standalone from the user's other repos.
- 2026-07-11 (later): Specific motor picked — N20 6V 150RPM with magnetic encoder (robu.in listing, page returned HTTP 403 to direct fetch; specs below are from equivalent listings of the same widely-resold OEM part, e.g. Adafruit #4640/#4638 and Cirkit Designer's pinout doc — physical wire-color-to-pin mapping still needs verification against whatever actually arrives, see below). Connectors need to be added to the PCB for it.
- 2026-07-11 (later): Line sensor count may drop from 8 to 6, SMD, styled after Pololu's QTR-8A analog reflectance sensor (same emitter/receiver element, not a QTR-8A module itself) — conditional on STM32 ADC pin budget (see new research section below). All sensors (wall + line) should present as ADC inputs to the STM32.

## N20-with-encoder motor: researched specs (2026-07-11)

Could not access the exact robu.in page (403). The "N20 6V 150RPM with encoder" is a widely-resold identical OEM part (same listing appears near-verbatim across many Indian and international resellers) — cross-referenced against Adafruit's documented equivalents (#4640, 1:150 ratio; #4638, 1:50 ratio) and a general N20-encoder pinout doc:

- **6 wires/pins total**: 2 motor power + 2 encoder power + 2 encoder quadrature outputs (A/B).
- **Function grouping is consistent across sources; exact physical pin ORDER is not** — one documented example orders them M+, M−, ENC_A, ENC_B, ENC_VCC, ENC_GND; others group motor-power and encoder-power adjacently. **Do not trust a specific pin-order assumption for the real connector — verify against the actual cable that arrives (JST connectors are keyed so it only plugs in one way, but which wire carries which function inside that housing varies by reseller).**
- Encoder is magnetic (Hall-effect), quadrature (2-channel A/B), commonly ~11 PPR at the *motor shaft* (i.e. before the gearbox) — multiply by the gear ratio (~150:1 for this "150RPM" variant, exact ratio varies by reseller batch) to get counts-per-revolution at the output shaft. This only matters for firmware odometry math, not the schematic.
- Encoder logic is typically 3.3–5V tolerant (open-drain or push-pull Hall outputs) — safe to power from our regulated +3V3 rail directly, matching STM32 logic levels with no level-shifting needed. **Assumption, not yet verified against the actual datasheet for this specific unit.**
- Connector: 6-pin, JST-XH or JST-PH family (1.25mm/2.0mm/2.5mm pitch depending on reseller) is typical for this class of product, but not confirmed for this exact listing.
- **Schematic approach**: since exact pin order is unverified, the KiCad connector will use a generic 6-pin header/JST footprint with pins clearly labeled by FUNCTION (M+, M−, ENC_VCC, ENC_GND, ENC_A, ENC_B) in the schematic — the physical wire-to-pad mapping is an assembly-time verification step, not something to hard-code into the design as if verified.

## STM32G431Kx (LQFP32, the package on NUCLEO-G431KB) real ADC pinout — researched 2026-07-11

This directly constrains the sensor architecture below. Source: ST DS12589 (official STM32G431x6/x8/xB datasheet), Table 12 pin definitions, cross-checked against the LQFP32 pin diagram.

| Header pin (D-number) | GPIO | ADC-capable? |
|---|---|---|
| A0-A7 (all 8) | PA0,PA1,PA3,PA4,PA5,PA6,PA7,PA2 | **Yes, all 8** (ADC1/ADC2 channels) |
| D3 | PB0 | **Yes** — ADC1_IN15 |
| D7 | PF0 | **Yes** — ADC1_IN10 (usable as GPIO/ADC since we don't use an external HSE crystal) |
| D8 | PF1 | **Yes** — ADC2_IN10 |
| D0,D1,D2,D4,D5,D6,D9,D10,D11,D12,D13 | PA10,PA9,PA12,PB7,PA15,PB6,PA8,PA11,PB5,PB4,PB3 | **No ADC function on any of these** — confirmed USB/TIM1/JTAG-only pins on this package |

**Total real ADC-capable pins available on the whole Nano header: 11** (the 8 "A" pins + D3/D7/D8). This is a hard ceiling, not a soft guideline — no other header pin can be repurposed for analog input on this exact MCU/package.

**Sensor budget math**: 6 wall + 6 line (even after reducing from 8) = 12 sensor signals, plus 2 battery-sense signals (VBAT_CELL1_SENSE, VBAT_PACK_SENSE) already wired on the Power sheet = **14 ADC signals needed, only 11 pins physically capable of carrying them.** Reducing line sensors 8→6 alone does NOT make "fully direct, no-multiplexing" fit — flagged to user rather than silently picking a workaround, since "all with ADC inputs to STM" was explicit and the literal all-direct reading is mathematically infeasible on this header regardless of sensor count within reason.

## Pololu QTR-8A sensor element specs (for the SMD line sensor design) — researched 2026-07-11

- Pololu doesn't publish exact LED/phototransistor part numbers for QTR-8A; both are SMD, exact package undocumented. Treat our existing SFH4550 (emitter) + SFH309 (receiver) choice as the practical stand-in — same electrical role, both already confirmed present in the stock KiCad library.
- QTR-8A analog divider: **47kΩ pull-up** per phototransistor channel (not the same as the QTR-8RC digital variant, which uses a cap instead) — matches our existing pull-up approach, just need to set the exact value to 47k for consistency with the reference design.
- LED current-limiting: two 47Ω resistors in series per channel for 5V operation, with a jumper to remove one stage for 3.3V (we're running everything off +3V3, so a single ~47Ω-class resistor stage, recompute exact value for our regulated 3.3V rail and SFH4550's real Vf/target current rather than copying 47Ω blindly).
- **Sensor pitch: 0.375in = 9.525mm center-to-center** between adjacent line-sensor elements — use this for the line array's mechanical layout.

## Component decisions (locked in, approved plan)

| Role | Part | Why |
|---|---|---|
| MCU board | NUCLEO-G431KB (STM32G431KB, Cortex-M4F @170MHz), Nano-compatible footprint | Best IO/speed within Nano footprint: 5 ADCs, rich timers (hw encoder mode + motor PWM), way faster than alternatives (e.g. OtterPill's Cortex-M0 @48MHz). Ships with a snap-off ST-LINK tab for bring-up. |
| Motor driver | TB6612FNG | User-specified. STBY must be GPIO-driven (not hardwired), not left floating/low. |
| Motors | N20 gearmotors — **assumed 6-wire "with encoder" variant** (M+/M-/ENC_VCC/ENC_GND/ENC_A/ENC_B) | Closed-loop odometry is near-mandatory for micromouse. **Not yet confirmed with user** — flag if they meant bare 2-wire N20 + separate encoder hardware. |
| Wireless module | ESP32-S3-MINI-1 | Dual-core, native USB, enough GPIO for UART+BOOT0+NRST control lines. |
| Sensor read-out | 2x HEF4067BT 16-channel analog mux/demux (Nexperia, pin-compatible with CD74HC4067), sharing 4 select lines (S0-S3) | 14 sensors would need ~14 dedicated ADC pins otherwise — tight on a 30-pin Nano footprint. One mux reads phototransistors → 1 ADC pin; the other acts as a demux routing a single LED_PULSE GPIO to the correct emitter driver transistor. Only ~6 GPIO total for all 14 channels, and it naturally enforces "pulse one emitter, read one receiver at a time" (crosstalk avoidance). |

## IR sensor circuit design (wall x6 + line x8)

Per research (Peter Harrison's micromouse book, IEEE Bruins sensor module) — **not** continuous-on LED + comparator:
- Emitter: SFH4550 (940nm IR LED), driven low-side by a small NPN/logic-MOSFET switch (GPIO can't source ~100mA pulsed current directly). Current-limit resistor sized off the **regulated +3V3 rail**, not raw battery, so brightness doesn't drift as the 2S LiPo discharges 8.4V→6.0V.
- Receiver: SFH309 phototransistor. Collector → mux common line through a pull-up resistor; emitter → GND. Output goes *low* as reflected light increases.
- Timing: pulse ~60-100µs, sample ADC ("bright"), LED off, sample again ("ambient"), subtract in firmware — synchronous/differential ambient-light rejection.
- Package: **through-hole** for both emitter and receiver (single-flat-PCB choice means wall sensors need hand-bent leads to aim forward/diagonal/side; line sensors point straight down).

## Power architecture

- 2S LiPo → `Conn_01x02` input, P-MOSFET reverse-polarity protection, fuse, external switch (off-board, modeled as a connector), bulk decoupling.
- VM_BATT (raw battery rail, 6.0-8.4V, hierarchical label not a power symbol) → TB6612FNG VM directly (within 2.5-13.5V spec).
- Single regulated +3V3 rail (AP63203WU switching buck, not LDO — ESP32 WiFi TX bursts to ~500mA) → everything else: STM32, ESP32, mux logic, encoder VCC, phototransistor pull-ups, IR LED driver current.
- Battery voltage sense: resistor dividers on each LiPo cell tap (from a JST-XH balance connector) → ADC-sense hierarchical labels for the MCU sheet.

## Wireless + flashing (ESP32-S3-MINI-1)

- ESP32 UART ↔ STM32 USART (bootloader-capable pins) for telemetry AND, on request, relaying the STM32 UART bootloader protocol over WiFi — mirrors the `esp32-bluetooth-bridge` project's approach (ESP32 GPIO drives BOOT0 high + pulses NRST low ~250ms to force bootloader mode), except over WiFi instead of Bluetooth (unproven combination — flagged as higher risk).
- 4-pin SWD header on our PCB regardless, as a guaranteed wired fallback if a wireless flash attempt bricks the link mid-transfer.
- **Open risk, needs verification**: whether BOOT0 and SWDIO/SWCLK are actually accessible on the NUCLEO-G431KB's Nano-compatible header (CN3/CN4), or only via onboard solder-bridge pads not present on the header. This directly affects whether the wireless-flashing design as specified is even physically wireable. See "Research log" below once resolved.

## KiCad symbol library survey (confirmed present in the stock KiCad 10.0.4 install, `C:\Program Files\KiCad\10.0\share\kicad\symbols\`)

| Part | Library | Symbol name | Notes |
|---|---|---|---|
| TB6612FNG | Driver_Motor.kicad_sym | `TB6612FNG` | exact part |
| ESP32-S3-MINI-1 | RF_Module.kicad_sym | `ESP32-S3-MINI-1` | exact part |
| 16-ch analog mux | Analog_Switch.kicad_sym | `HEF4067BT` | Nexperia, function-compatible with CD74HC4067 |
| IR emitter LED | LED.kicad_sym | `SFH4550` | exact part, 940nm |
| Phototransistor | Sensor_Optical.kicad_sym | `SFH309` | exact part, 2-pin (C/E only, base not brought out) |
| Buck regulator | Regulator_Switching.kicad_sym | `AP63203WU` | Diodes Inc, TSOT-23-6, fixed 3.3V out, extends `AP63200WU` base symbol |
| LED driver switch | Transistor_FET.kicad_sym | `BSS138` or `2N7002` | logic-level N-MOSFET, low-side switch |
| P-MOSFET (reverse protection) | Device.kicad_sym | `Q_PMOS` | generic; note real part e.g. DMP2035U-7 in Value/Description |
| Resistor / Capacitor / Inductor | Device.kicad_sym | `R` / `C` / `L` | generic |
| Fuse | Device.kicad_sym | `Fuse` | generic |
| Headers | Connector_Generic.kicad_sym | `Conn_01x02`...`Conn_01x15`, `Conn_02x02_Odd_Even`...`Conn_02x40_Odd_Even` | `Conn_02x15_Odd_Even` = the Nano-footprint socket |
| Power symbols | power.kicad_sym | `+3V3`, `GND`, `PWR_FLAG` | standard |
| No phototransistor-specific symbol needed — SFH309 already exists as a real part, no generic-NPN substitution required. |

**Format reference for hand-authoring `.kicad_sch`/`.kicad_pro`**: use `C:\Program Files\KiCad\10.0\share\kicad\template\kicad.kicad_pro` (+ paired blank `.kicad_sch`) for correct v10 headers/UUIDs, and `C:\Program Files\KiCad\10.0\share\kicad\template\Arduino_Nano\Arduino_Nano.kicad_sch` as a real populated example at the same KiCad version.

## Reference designs found (research)

- **Mushak** (github.com/gautam-dev-maker/mushak) — STM32F405, DRV8833, SFH-4045N/SFH-3015-FA sensor pairs, VL6180X front ToF, AS5600 encoders, HC-08 BLE telemetry.
- **UKMARSBOT/mazerunner-core** (github.com/ukmars/ukmarsbot) — Arduino Nano primary, STM32 variants in `ecad/`, HC-05/06 BT telemetry pattern (leave BT attached during programming).
- **Piccola** (github.com/Isuru-Dissanayake/piccola) — STM32F103C8T6 "Blue Pill", HC-06 BT telemetry.
- Wireless STM32 flashing prior art: `coddingtonbear/esp32-bluetooth-bridge` (BT SPP, not WiFi) — ESP32 drives BOOT0 high + pulses NRST low ~250ms, then relays the standard STM32 UART bootloader protocol.

## NUCLEO-G431KB confirmed CN3/CN4 pinout (researched 2026-07-11)

Source: community EAGLE library (github.com/martonmiklos/EAGLE-libraries/NUCLEO-G431KB.lbr), cross-checked against ST's official NUCLEO-F303K8 CN3/CN4 table (same Nucleo-32 physical family, UM1956) — 13 of 15 positions matched exactly, only D5/D6 differ (expected, since alternate-function availability differs per MCU). Confidence: high for D0-D13/A0-A7/power pins; the BOOT0/SWD finding below is corroborated by a second independent source (a search snippet quoting ST's UM2397 directly).

```
D0=PA10   D1=PA9    D2=PA12   D3=PB0    D4=PB7    D5=PA15   D6=PB6
D7=PF0    D8=PF1    D9=PA8    D10=PA11  D11=PB5   D12=PB4   D13=PB3
A0=PA0    A1=PA1    A2=PA3    A3=PA4    A4=PA5    A5=PA6    A6=PA7   A7=PA2
Plus: RESET (NRST), GND (x2), AREF, +3V3, +5V, VIN
```

**Critical finding: BOOT0 and SWD (PA13/SWDIO, PA14/SWCLK) are NOT on CN3/CN4.** Neither PA13, PA14, nor PB8 (the BOOT0-remap pin on some STM32G4 option-byte configs) appear anywhere in the 30-pin header list. A direct manual excerpt confirms: "PA13 and PA14 are shared with SWD signals connected to STLINK-V3E. It is not recommended to use them as I/O pins" — they're dedicated to the onboard ST-LINK section, not brought out to the Arduino-compatible header at all.

**Impact on the approved plan:**
- The "ESP32 drives BOOT0 high + pulses NRST" hardware bootloader-forcing trick (the `esp32-bluetooth-bridge` pattern) **cannot be wired** through the Nano-footprint socket — BOOT0 simply isn't there to drive.
- NRST **is** available on the header, so ESP32 can still trigger a hardware reset.
- Our planned "4-pin SWD fallback header on our own PCB" **cannot connect to the socketed module** via the Nano pins either — SWD isn't there.
- **Resolved 2026-07-11**: user wants unified OTA — one WiFi update mechanism from the ESP32 that can update either chip. Design:
  - **ESP32 self-update**: standard ESP32 WiFi OTA (well-established, firmware-only, no schematic impact beyond the WiFi module itself).
  - **STM32 update via ESP32**: no BOOT0 hardware forcing. Instead, STM32 firmware checks early in `main()` (before most peripheral init) for an "enter update mode" request — either a command byte from the ESP32 over UART (normal case, app is alive and listening) or a magic value in a backup/RTC register set by the app just before a self-triggered reset — and if set, deinitializes and jumps to STM32's built-in System Memory ROM bootloader (AN2606, no BOOT0 pin needed since this is a software jump, not a boot-time pin sample). ESP32 then streams the new STM32 binary over UART using the standard STM32 bootloader protocol, same protocol `esp32-bluetooth-bridge` speaks over BT SPP, just carried over UART/WiFi instead.
  - ESP32 needs only: UART TX/RX to STM32 (already planned) + NRST (available on the header, for a hard-reset trigger when the app is responsive enough to request one). **No BOOT0 or SWD connection needed from the ESP32 at all.**
  - **Accepted residual risk**: if STM32 firmware/flash ever gets corrupted badly enough that it can't run to the "check for update request" point, there is no wireless recovery path (BOOT0 isn't reachable to force it). Recovery in that scenario requires physical access — the Nucleo module's own USB/ST-LINK (only while its snap-off tab is still attached) or direct SWD wires to the module's test pads. This is a normal, accepted tradeoff for this class of design (same one many WiFi-updatable products make) — flagging it so it's a known decision, not a silent gap.

## How the schematic is actually being built (important for continuing this)

Hand-authoring raw `.kicad_sch` S-expression files by typing them out directly turned out to be far too error-prone and context-expensive (invalid files fail to load with an opaque "Failed to load schematic", no line number). Instead, built a small **Python generator** at `D:\Projects\micromouse-pcb\tools\` that:
- Extracts real symbol definitions verbatim from the installed KiCad library files (`C:\Program Files\KiCad\10.0\share\kicad\symbols\*.kicad_sym`) so every part used is a genuine, correctly-defined library symbol.
- Places components using a verified coordinate transform (see fact #6 below). Rail-style nets (GND, VM_BATT, PLUS3V3, GPIO nets reaching a not-yet-built sheet) get a global label sitting directly on the pin — matching label text anywhere on the sheet is electrically the same net regardless of position. Local 2-node nets get an actual drawn wire via `g.connect()`, Z-routed through a grid-snapped midpoint (see fact #9 — the routing choice itself has a real correctness gotcha, not just a cosmetic one).
- Renders one flat `.kicad_sch` (single sheet, not the originally-planned 6 separate hierarchical sheet files) — chosen deliberately to avoid the hierarchical sheet `sheet_instances`/UUID-path linkage format, which has no bundled reference example to verify against and is a much higher-risk thing to get subtly wrong. Sections are visually grouped with `TXT()` headers (POWER, MCU, ...) on one large A2-size sheet. **If you want true multi-sheet hierarchy**, the cleanest path is to open this file in the real KiCad GUI and use its "Import Sheet"-style refactor tools rather than hand-authoring the hierarchy format blind.
- Generator files: `tools/gen_sch.py` (the reusable engine) and `tools/build_power_mcu.py` (this sheet's actual component list) — both live in the project repo, so the schematic is regeneratable/auditable outside this conversation. Run with the msys64 Python (`C:\msys64\ucrt64\bin\python3.exe`), not the Windows Store Python shim.

### Hard-won technical facts about the KiCad 10 `.kicad_sch` format (don't rediscover these)
1. **Embedded `lib_symbols` cache entries must use the fully-qualified `"LibName:SymbolName"` as the name — but ONLY at the top level.** Nested sub-unit symbols (e.g. a resistor's `"R_0_1"`/`"R_1_1"` graphics/pin sub-blocks) keep their bare unqualified name. Qualifying the sub-units too silently breaks loading with no useful error.
2. **A symbol using `extends` must have its base symbol embedded too, inserted BEFORE the extending symbol** in `lib_symbols` (forward references break loading). More importantly: **avoid `extends` entirely if you can** — KiCad's ERC appears to skip pin-connectivity validation (`pin_not_connected`) for symbols reached via `extends` (confirmed: `AP63203WU extends AP63200WU` produced zero pin-connectivity errors even with every pin left floating, while the plain `AP63200WU` base symbol correctly flagged all 6). Prefer instantiating the base symbol directly and noting the real BOM part in the `Value`/Description field.
3. **Component `instances` blocks use `(path "/<root-schematic-uuid>" (reference "REF") (unit 1))`** — NOT `(path "/" (page "1"))` (that form is only for the top-level `sheet_instances` block). Getting this wrong causes "Failed to load schematic" with no further detail.
4. **This is a native-Windows Python build (`C:\msys64\ucrt64\bin\python3.exe`)** — writing text files with the default `open(path, "w")` re-adds `\r` before every `\n` on Windows. Always pass `newline="\n"` when writing `.kicad_sch`/any KiCad file, or the CRLF contamination (inherited further if you also read a CRLF source file) can break the parser.
5. **Multi-line `text` annotation elements need embedded newlines escaped as the literal two characters `\n`**, not a raw newline byte inside the quoted string — a raw newline breaks the parser (silently, same opaque "Failed to load schematic").
6. **The critical one — pin placement transform, empirically confirmed via `kicad-cli sch erc` ground-truth tests (leave a pin unconnected, read back its reported position):** for a symbol placed at `(base_x, base_y)` with rotation 0, a pin with library-defined local offset `(local_x, local_y)` ends up at **`(base_x + local_x, base_y − local_y)`** — X is applied as-is, **Y is negated**. This is easy to get wrong silently: on a symmetric 2-pin passive (R/C/L/Fuse) getting it wrong just swaps which physical pin gets which net (harmless, no polarity), but on anything asymmetric (connectors, MOSFETs, regulators, the Nano header) it silently swaps which real-world pin gets which signal, and ERC does NOT reliably flag it as an error (sometimes shows as `label_dangling`, sometimes shows nothing at all if the mislabeled position happens to coincide with a *different* real pin). Always compute label positions via a `pin_at(base, local_offset) = (base_x+lx, base_y-ly)` helper, never raw `+`. If adding a new part, verify its offsets empirically (place it alone with NO labels, run ERC, confirm the reported "pin not connected" positions match your assumed offsets) before trusting them.
7. `kicad-cli sch erc` requires a companion `.kicad_pro` file with a matching-enough presence in the same folder to load reliably (a lone `.kicad_sch` with no project file nearby can fail to load or crash with `std::bad_alloc`).
8. **A symbol reached via `extends` silently skips ERC's pin-connectivity checking.** Confirmed empirically: `AP63203WU extends AP63200WU` produced zero `pin_not_connected` errors even with every pin left completely unconnected, while the plain `AP63200WU` base symbol correctly flagged all 6 floating pins at their exact real positions. Don't trust ERC being clean as proof of correctness for any symbol using `extends` — instantiate the base symbol directly instead (put the real BOM part name in `Value`).
9. **The dangerous one, found via user visual review (2026-07-11), NOT via ERC:** an early revision added straight/L-shaped wires for local point-to-point connections instead of labels, to make the schematic visually readable (see below). The L-shape's bend point was chosen as `(x2, y1)` — reusing one endpoint's X and the other's Y. In a *tidy, aligned* layout (many parts sharing a baseline Y — exactly what "well laid out" means), that bend can land **exactly on a real, unrelated pin** (e.g. two parts on the same row, each with a symmetric ±Y pin offset: the bend reuses one part's X and the other's Y, which is precisely that other part's actual pin position). This silently merged GND and PLUS3V3 into one mega-net across almost every component. **ERC did not reliably flag this** — kicad-cli's ERC missed it entirely at low severity; only `kicad-cli sch export netlist` + a script diffing net membership against intent caught it, and even then only because the diff was done net-by-net rather than eyeballing the ERC pass/fail count. **Lesson: after adding any auto-routed wire, export the netlist and mechanically verify net membership — a clean ERC is not sufficient proof of correct connectivity when wires are involved.** Fixed by routing point-to-point wires through the horizontal midpoint (an arbitrary average of two placements, snapped to grid, that no real component is ever placed at) instead of reusing either endpoint's raw coordinate.

## STM32G431 timer alternate-function verification (researched 2026-07-11, for Motor/Encoder/Sensor GPIO assignment)

Needed to know which Nano-header GPIOs support PWM output and which pairs support hardware quadrature-encoder mode (both channels of the SAME timer), to assign the motor driver / encoder / mux nets without silently picking an unusable pin -- this is NOT caught by schematic ERC (ERC has no concept of internal alternate-function routing), so it had to be checked before finalizing, same rigor as the ADC pin table above.

Direct datasheet PDF fetch (`st.com/resource/en/datasheet/stm32g431cb.pdf`) failed both via WebFetch (timeout on the full PDF) and `curl` (silently blocked, same class of issue as the robu.in 403). Used an equally-authoritative alternative instead: Zephyr RTOS's `hal_stm32` pin-control data (`dts/st/g4/stm32g431k(6-8-b)tx-pinctrl.dtsi`, the exact LQFP32 "K" package used on NUCLEO-G431KB) -- this file is machine-generated (`genpinctrl.py`) directly from ST's own CubeMX pin database, and is what real embedded projects build firmware against, so it's ground truth, not a secondary summary.

Confirmed relevant mappings (pin: alternate-function timer channel):
- PA8 (D9): TIM1_CH1 (AF6) -- used for PWMA
- PA11 (D10): TIM1_CH4 (AF11) -- used for PWMB (paired with PWMA on the same timer, TIM1)
- PB4 (D12): TIM3_CH1 (AF2) -- used for ENC1_A
- PB5 (D11): TIM3_CH2 (AF2) -- used for ENC1_B (paired with ENC1_A on the same timer, TIM3)
- PA15 (D5): TIM2_CH1 (AF1) -- used for ENC2_A
- PB3 (D13): TIM2_CH2 (AF1) -- used for ENC2_B (paired with ENC2_A on the same timer, TIM2)
- PF1 (D8): no timer alternate function at all on this pin -- confirms it's a "wasted" pin for anything but ADC, so it's the correct choice for a pure analog signal (VBAT_CELL1_SENSE)

This is a firmware-configuration fact (which register/AF value to program), not something the schematic file itself encodes -- flagging that firmware bring-up must configure these exact AFs (TIM1 CH1/CH4 for PWM, TIM2 CH1/CH2 and TIM3 CH1/CH2 in encoder mode) for the hardware to work as intended.

## Final GPIO / net allocation across the Nano header (all 22 signal pins + NRST, locked in 2026-07-11)

All ADC budget concerns from the earlier "Sensor budget math" section are now moot: the 2x HEF4067BT mux/demux collapses all 14 sensor channels onto ONE ADC pin, so only 3 ADC-capable pins are actually needed (not 11+). This freed up all 8 A-pins for digital use.

| Header pin | GPIO | Net name | Function |
|---|---|---|---|
| D0 | PA10 | USART1_RX | STM32 receives, from ESP32 TX |
| D1 | PA9 | USART1_TX | STM32 transmits, to ESP32 RX |
| D2 | PA12 | MUX_S0 | mux/demux shared select line |
| D3 | PB0 | MUX_SENSE | ADC1_IN15 -- analog common from the read-mux (phototransistor side) |
| D4 | PB7 | MUX_S1 | mux/demux shared select line |
| D5 | PA15 | ENC2_A | TIM2_CH1, motor B encoder |
| D6 | PB6 | MUX_S2 | mux/demux shared select line |
| D7 | PF0 | VBAT_PACK_SENSE | ADC1_IN10 -- full pack voltage sense |
| D8 | PF1 | VBAT_CELL1_SENSE | ADC2_IN10 -- cell 1 voltage sense (no timer fn wasted on this pin) |
| D9 | PA8 | PWMA | TIM1_CH1, motor A speed |
| D10 | PA11 | PWMB | TIM1_CH4, motor B speed |
| D11 | PB5 | ENC1_B | TIM3_CH2, motor A encoder |
| D12 | PB4 | ENC1_A | TIM3_CH1, motor A encoder |
| D13 | PB3 | ENC2_B | TIM2_CH2, motor B encoder |
| A0 | PA0 | MUX_S3 | mux/demux shared select line |
| A1 | PA1 | LED_PULSE | GPIO into the write-demux common pin, pulses the currently-selected IR LED |
| A2 | PA3 | STBY | TB6612 standby (GPIO-driven, per earlier decision -- never hardwired) |
| A3 | PA4 | AIN1 | TB6612 motor A direction bit 1 |
| A4 | PA5 | AIN2 | TB6612 motor A direction bit 2 |
| A5 | PA6 | BIN1 | TB6612 motor B direction bit 1 |
| A6 | PA7 | BIN2 | TB6612 motor B direction bit 2 |
| A7 | PA2 | USER_BTN | spare pin -- used for a start-run push button (active low, pull-up), standard micromouse UX, not in the original spec but essentially free given the budget worked out exactly even |
| NRST | NRST | NRST | hardware reset; also driven by an ESP32 GPIO (open-drain, firmware-configured) for a wireless hard-reset trigger |

Every one of the 22 usable signal pins is now assigned with zero spare pins left over (other than the repurposed A7/USER_BTN) -- this is a tight but complete fit, consistent with the earlier finding that the Nano footprint is the binding constraint on this design.

## Progress log

- 2026-07-11: Plan approved. Project folder created. Symbol library survey done (table above). Chose to hand-author `.kicad_sch` files directly rather than delegate to a subagent, working sheet-by-sheet with `kicad-cli sch erc` verification after each one.
- 2026-07-11: Researched NUCLEO-G431KB pinout — found BOOT0/SWD are not exposed on the Nano header (see above). Flagged to user before proceeding with the Wireless/Connectors-Debug sheets.
- 2026-07-11: Built `micromouse-pcb.kicad_sch` (Power + MCU sections, single flat A2 sheet) via a Python generator after a long debugging pass (see technical facts above). First pass was ERC-clean but used tightly-packed label-on-pin placement with no visible wires — user opened it in the real KiCad GUI and correctly called out that it wasn't laid out properly.
- 2026-07-11: Reworked the layout — components spread out generously, and local 2-node nets (J1→J2, F1→Q1, the regulator's SW/BST loop, the sense-divider chains) now get an actual drawn wire via `g.connect()` instead of a floating label pair. That's what surfaced the wire-routing short in fact #9 above. Rail nets (GND, VM_BATT, PLUS3V3, STM32 GPIO nets) still use a label sitting directly on the pin. Copied the generator (`gen_sch.py`, `build_power_mcu.py`) into `D:\Projects\micromouse-pcb\tools\` so it's regeneratable/auditable outside this conversation.
- **Current state, verified two ways**: `kicad-cli sch erc` → 0 errors, 23 warnings (all `isolated_pin_label` on the 23 STM32 GPIO nets awaiting the not-yet-built Motor Driver / IR Sensors / Wireless sheets — PA9/PA10 to the ESP32 UART, PB0/PB7/PA8/PA11/PB5/PB6/PA15 to TB6612 + encoders, PA0-PA7 to the analog mux). **AND** `kicad-cli sch export netlist` cross-checked net-by-net against intent — every net (GND, VM_BATT, PLUS3V3, VBAT_CELL1_SENSE, VBAT_PACK_SENSE, each local point-to-point net) contains exactly the pins it should. Exported `micromouse-pcb.svg` (couldn't rasterize it to view inline in this session — user is reviewing directly in the KiCad GUI, which is also how the layout problem was caught).
- Next: Motor Driver + Motors/Encoders section, IR Sensor Array section (mux + 14 pairs), Wireless (ESP32-S3-MINI-1) section, Connectors/Debug section — all appended to the same flat schematic, same generator approach. **For every future section using `g.connect()`, re-run the netlist cross-check (not just ERC)** — see fact #9.
- 2026-07-11: **Schematic complete.** Replaced `tools/build_power_mcu.py` with `tools/build_schematic.py` — one script now builds the entire schematic (Power, MCU, Motor Driver + Encoders, IR Sensor Array, Wireless, Connectors/Debug) in a single regeneration, bumped paper to A1 landscape (841x594mm) since A2 only had room for the first two sections without cramming. 120 components, 229 labels, 209 wires, 41 no-connects, 20 unique library symbols.
  - Researched and finalized the complete GPIO/net allocation across all 22 usable Nano-header signal pins (table earlier in this file) — STM32G431 timer alternate-function mapping verified against Zephyr's `hal_stm32` pinctrl data (ST's own CubeMX database, ground truth) since the direct ST datasheet PDF fetch failed (timeout/blocked, same class of issue as the earlier robu.in 403).
  - **Found and fixed a new variant of the fact-#9 wire-collision bug** while building this: multiple independent `g.connect()` calls between two same-orientation groups of components (e.g. two resistors in one column both wiring to two connector pins in another column) can compute the *identical* auto-picked midpoint bend X, so their vertical bend segments overlap and silently short two unrelated nets together. This happened twice in the first draft — TB6612's AO2 output shorted to BO2, and separately the ESP32's EN pin shorted to IO0 — caught the first via ERC (`pin_to_pin` output-output conflict) but the second did NOT trip any ERC violation, only showing up once the netlist was diffed (exactly the class of silent bug fact #9 warned about). **Fixed generally**: `build_schematic.py`'s `WIRE()` helper no longer calls `g.connect()` directly — it gives every Z-routed wire a small unique cycling offset (12-step, 3.81mm each) so no two bends can land on the same X. A related but distinct variant also occurred where a capacitor's decoupling wire routed a horizontal segment *through* an unrelated same-row pin (TB6612's VCC, sitting between the wire's bend and its VM1 target) — fixed by placing those two decoupling caps so the wire is a pure vertical line (X aligned exactly with the target pin), avoiding the horizontal segment entirely rather than relying on offset luck.
  - Wrote `tools/verify_netlist.py` — parses the exported netlist and asserts, net-by-net, that GND/VM_BATT/PLUS3V3 stay distinct, all 4 motor-output nets are distinct, all 4 encoder nets are distinct, ESP32's EN/IO0 nets are distinct, and all 28 IR-sensor `_SENSE`/`_LED` nets exist and are distinct with the exact expected (ref, pin) membership. This is the "mechanical, net-by-net" verification fact #9 calls for, made reusable/re-runnable rather than a one-off manual diff. All checks passed after the fixes above.
  - Visually inspected the rendered PDF myself (`kicad-cli sch export pdf`, read directly) after each change — same practice the user used to catch the original layout problem. Caught and fixed two text-block overlaps this way (Motor Driver's encoder note colliding with Wireless's IO note; the IR Sensor Array's description text colliding with its own section header) before calling the layout acceptable.
  - Final state: `kicad-cli sch erc` → 0 errors, 0 warnings. Netlist cross-check → all checked nets correct. Deleted the superseded `tools/build_power_mcu.py` (no git history yet on this project, so nothing lost by removing it).
  - Added a start-run push button (`USER_BTN`, on PA2/A7) in the Connectors/Debug section — not in the original spec, added because the final GPIO budget came out exactly even with that one pin otherwise unused, and a start button is standard micromouse UX.
  - Two judgment calls flagged as unverified assumptions rather than hard specs: (1) IR LED current-limit resistor sized at 33ohm assuming SFH4550 Vf~1.35V typical and ~0.3-0.5V allowance for the BSS138 switch's on-resistance at only 3.3V gate drive — BSS138's Rds(on) is characterized in its datasheet mainly at Vgs=2.5V/4.5V, not 3.3V, so actual LED brightness may differ from the 33ohm napkin math and should be tuned at bring-up. (2) All 4 encoder signal lines get defensive 10k pull-ups since it's still not confirmed whether the actual N20-with-encoder unit's Hall outputs are open-drain (pull-up required) or push-pull (pull-up harmless but unnecessary).
  - Next: PCB layout (board outline, footprint placement, routing).
- 2026-07-11: **PCB placement + ground plane complete.** Built `tools/gen_pcb.py` (a pcbnew-Python engine, same "single regeneratable source of truth" philosophy as the schematic generator) and `tools/build_pcb.py` (the actual board layout). `kicad-cli pcb drc` → **0 errors, 0 warnings**, with 287 unconnected ratsnest items remaining (expected -- see "what's NOT done" below).
  - **Connectivity comes entirely from `netlist.net`**, not re-derived: `gen_pcb.py` parses the schematic's already-verified netlist for each ref's footprint and every (ref, pin) -> net mapping, so `PcbGen.place(ref, x, y, rot)` only ever needs a physical position -- it looks up the right footprint and wires every pad automatically. PCB and schematic connectivity cannot silently drift apart, by construction.
  - **Board shape**: hexagonal outline (chamfered front corners so the mouse doesn't catch maze walls turning), 165x210mm -- comfortably inside a 180mm maze cell. Went through four placement drafts (110x110 → 130x130 → 150x170 → 165x210) before landing here; each earlier draft hit real `kicad-cli pcb drc` violations (courtyard overlaps, and a couple of pads that actually bridged PLUS3V3 to GND) from underestimating real component size, most notably:
    - The **ESP32-S2/S3-MINI-1 footprint's courtyard is genuinely 45x35mm**, confirmed by querying `FOOTPRINT.GraphicalItems()` filtered to the `F.Courtyard` layer directly rather than guessing from the module's ~25x18mm physical size -- Espressif's recommended antenna keep-clear area is baked into the courtyard, and it fundamentally competes for the same board region as the WALL5/6 side sensors. Resolved by giving the ESP32 its own Y-band (below the motor driver) instead of a side column.
    - Wall sensor clusters (WALL1/2, the "front diagonal" pair) were initially placed with anchors that put them *outside* the chamfered corner geometry entirely (e.g. anchor (14,12) is outside the `x+y=35` chamfer line) -- caught as `copper_edge_clearance` DRC errors (pads sitting on/past the board edge), not a courtyard issue. Fixed by keeping anchors at `x+y >= 50` from that corner.
  - **Fast iteration**: added `PcbGen.check_overlaps()` -- an in-process courtyard-bbox pairwise check -- so placement could be iterated in milliseconds instead of a full export+`kicad-cli pcb drc` round trip (~10-20s) each time. Used it to converge the last few overlaps (mux ICs vs. their own decoupling caps, mux ICs vs. wall-sensor clusters) before the final confirming DRC pass.
  - **Ground plane**: GND poured as a copper zone on *both* F.Cu and B.Cu (88 pin-instances in the schematic, the largest net by far) -- standard practice for a busy 2-layer board, and resolves the large majority of connections without a single hand-routed trace. Deliberately did **not** pour PLUS3V3 as a full plane on either layer -- doing so would leave little room to route the many signal nets (motor phase, encoder, GPIO fan-out, 14-way sensor mux) that still need traces; +3V3 gets routed as normal copper during interactive routing instead.
  - **Zone-fill segfault, worked around**: calling `pcbnew.ZONE_FILLER(board).Fill(zones)` from the headless/scripted Python bundled with KiCad crashes (segfault) in this environment. Confirmed via a small prototype that this isn't actually necessary -- `kicad-cli pcb drc` (and, by extension, gerber/fab export) correctly resolves zone-to-pad connectivity from the zone's *outline* even without a pre-computed fill, and the real KiCad GUI fills zones on load/edit automatically. **The one manual step left for the user**: press B (or Edit > Fill All Zones) once after opening the board in KiCad, to generate the actual copper polygons for fab output -- this is a single keypress, not a design gap.
  - Verified the final render visually (`kicad-cli pcb render`, read directly, same practice as the schematic PDF review) -- board reads clearly as a micromouse chassis: line-sensor row + 6 wall-sensor clusters up front, MCU socket + mux ICs + motor driver + connectors in the middle, power section and the isolated ESP32 quadrant at the back. No visual overlaps.

## What's NOT done yet on the PCB (honest scope -- do not treat this as finished for fab)

- **No copper traces routed** beyond the GND plane. All 287 remaining ratsnest connections (motor phase wires, all 4 encoder lines, the full STM32 Nano-header GPIO fan-out, the 14-way sensor mux fan-in/out, +3V3 distribution, battery input chain) still need to be routed. This is a genuinely large interactive-routing task -- realistically the next work session's main effort, most practically done in the KiCad GUI (or a proper autorouter like Freerouting via specctra DSN export/import, not attempted here). Do **not** read "0 DRC errors" as "board is routed" -- DRC on an unrouted board just means nothing placed is illegal yet, not that the design is complete.
- **Zones need one manual fill** (press B in the GUI) before the GND plane becomes real copper for fab output -- see above.
- Silkscreen reference designator placement is whatever KiCad's default auto-placement produced -- worth a manual tidy pass before fab (a few labels likely overlap their own component at this density, though DRC's silk-clearance checks came back clean on the final layout).
- No mounting holes, no wheel/motor-bracket cutouts, no battery strap/tray cutouts -- these are mechanical decisions that depend on the specific motor bracket and battery pack dimensions, neither of which has been finalized/measured yet.
- Board outline is a first-pass hexagon sized from component-clearance math, not from a caliper measurement of an actual maze cell or a real motor/wheel CAD model -- treat the 165x210mm figure as a reasonable starting point, not a validated final dimension.

## 2026-07-12: full-BOM footprint audit (prompted by the user asking "did you check the same for other components?")

Verified every footprint against manufacturer datasheets + the installed `.kicad_mod` files (subagent research, sources in CONNECTIONS.md): **all PASS** -- TB6612FNG=SSOP24-P-300-0.65A ✓, HEF4067BT=SOT137-1/SO24 wide ✓, AP63203WU=TSOT-23-6 ✓, SFH309=2-pin 3mm T-1 ✓, SFH4550=5mm THT ✓, DMP2035U/BSS138=SOT-23 ✓, JST XH/PH part-number-to-footprint pairings internally consistent (S-prefix=side entry=Horizontal, B-prefix=top entry=Vertical) ✓ -- **except one soft fail: the ESP32 footprint.** KiCad stock has no ESP32-S3-MINI-1 footprint; the S2-MINI-1 footprint's 65-pad grid is IDENTICAL to the S3's per both Espressif datasheets (60x 0.4x0.8mm @0.85mm + 4 corner + 9 thermal), but the S3 BODY is 20.5mm vs the S2's 20.0mm -- the real module will overhang the courtyard/silk by 0.5mm at the antenna end. Pads align, purely cosmetic at our placement margins; kept, documented. (The KiCad footprint's own description even links the S3 datasheet -- upstream metadata quirk, not a verified-compatibility statement.)

## 2026-07-12: sensor mounting corrected to match real micromouse practice (user direction + research)

Researched UKMARSBOT, UCI micromouse-kit, Pololu QTR docs (links in the research log / CONNECTIONS.md):
- **Line sensors belong on the BOTTOM face** looking at the floor: UKMARSBOT solders its line-sensor optics on the underside of the main board; Pololu recommends ~3.2mm (max 6.35mm) above the surface. → All 8 line-sensor clusters (photo, pull-up, LED, resistor, switch -- the whole 5-part cluster, so only the two mux-bound nets need vias) are now placed FLIPPED (B.Cu) in `build_pcb.py` via a new `place(..., flip=True)`.
- **Wall sensors with 90-deg hand-bent THT leads on a flat board is a real, used technique** (UCI kit instructs exactly this; UKMARSBOT bends side sensors 30 deg) -- so wall sensors stay on top, placed with photo+LED nearest the board edge to minimize bent-lead length (shorter bent leads = less inter-sensor crosstalk per the UCI guide). **Open risk: no source documents strain relief for bent leads; plan hot glue/brackets at assembly.**
- pcbnew gotcha for the flip: `FOOTPRINT.Flip()` before `board.Add()` segfaults; flip only after adding.

## 2026-07-12: TWO more schematic bugs found and fixed (both invisible to ERC/DRC)

**1. Nano header row order was wrong** (found while writing CONNECTIONS.md justifications). The previous "confirmed" CN3/CN4 table contained a phantom NC pin at digital-row position 5 (shifting D2-D11 by one), had D12 on the wrong row, scrambled the analog row's power pins, and missed that the Nano standard carries RESET on BOTH rows. Ground truth used for the fix: **KiCad's own bundled Arduino Nano reference PCB** (`template/Arduino_Nano/Arduino_Nano.kicad_pcb`), pad-by-pad: digital row pin1->15 = D12 D11 D10 D9 D8 D7 D6 D5 D4 D3 D2 GND RESET D0 D1; analog row = D13 3V3 AREF A0-A7 5V RESET GND VIN; both rows' pin 1 at the SAME physical end (D12 across from D13). Also: ST swapped the CN3/CN4 silk labels on the G431KB vs every other Nucleo-32 (ST community, ST-moderator-confirmed), so the design now names rows by function (J4=digital, J8=analog) and avoids CN3/CN4 entirely. Netlist re-verified after the fix; NRST now correctly spans J4.13 + J8.13 + ESP32 IO6.

**2. Reverse-protection P-MOSFET Q1 was installed backwards** (found while writing the justification for the power chain -- the doc forced the body-diode analysis). Battery entered at SOURCE, load at DRAIN; in that orientation a REVERSED battery conducts straight through the body diode (anode=drain on a P-FET) -- zero protection. Correct topology (now applied): battery -> DRAIN, load -> SOURCE, gate to GND via R1: power-up conducts via body diode until the channel enhances; reversal leaves diode reverse-biased AND Vgs>=0. **Lesson recorded: ERC cannot catch either bug class (both are electrically-legal wrong wirings); writing per-connection justifications is what surfaced both.**

## 2026-07-12: flagged design risks (documented, deliberately not silently "fixed")

- **Balance-lead standby drain**: both ADC dividers hang on J3 upstream of switch+fuse → ~0.65mA continuous whenever the balance lead is plugged (kills a stored pack in weeks). Rule: unplug balance lead for storage; future rev could add a high-side sense switch.
- **Floating demux gates**: unselected HEF4067 outputs are high-Z, so 13 of 14 BSS138 gates float; a deselected gate HOLDS its last charge (LED could stay on). Firmware rules (in CONNECTIONS.md): always drop LED_PULSE low while the channel is still selected; on boot, walk all 14 channels with LED_PULSE low. Hardware alternative (14 gate pulldowns) deemed unnecessary given the firmware rule.
- **J7 dongle power**: J7 carries +3V3 so a USB-serial dongle can power the ESP32 for bench flashing -- do NOT connect dongle power with the battery switched on (two regulators fighting).

## 2026-07-12 (later): "socket everything" module rework + mechanical + SMD line sensors + Freerouting

Big user-driven rework of the whole board into a "modules-plugged-into-a-carrier" design. All changes below are ERC-clean, netlist-verified, Freerouting-completed (all non-GND nets in copper), and DRC-clean (0 violations; GND on the twin pours awaiting the one GUI fill).

**Parts now socketed / changed (user requests):**
- **ESP32**: was bare ESP32-S3-MINI-1 SMD → now a **socketed Arduino Nano ESP32 dev board** (J12 digital row + J13 analog row, two 1x15 female headers 15.24mm apart, same mounting as the Nucleo). Dropped all the SMD-module support that a dev board already carries: EN/IO0 strap buttons, their pull-ups, the 4-pin programming header, and the module decoupling. Only 3V3/GND/D0(RX)/D1(TX)/D2(NRST) are wired. Chosen because it's an ESP32-S3 dev board in the SAME Nano form factor, so it sockets identically to the STM32 and the pinout risk is low (verified against KiCad's Arduino Nano reference).
- **Motor driver**: was bare TB6612FNG SSOP-24 → now a **socketed TB6612 breakout** (SparkFun ROB-14451 / Pololu class) modeled as J10 (control 1x8) + J11 (power+outputs 1x8) female rows, functional pin labels. **Flagged: breakout pin order/row spacing varies by vendor -- verify before fab.**
- **Line sensors (8)**: was THT SFH309/SFH4550 → now **SMD** on the bottom face (Osram SFH4045N-class 940nm emitter + SFH320FA-class phototransistor, modeled on 1206 land patterns to fit the 9.525mm QTR pitch -- LPT80A's ~11mm land was too wide). Wall sensors (6) stay THT bent-lead on top.
- **Motor connectors J5/J6**: horizontal JST-PH → **vertical (top-entry) JST-PH B6B-PH-K** for easy plugging.

**Mechanical (from research -- micromouseonline, UKMARS, Pololu; see the research log):**
- Board outline now has **wheel/motor-shaft edge notches** cut directly into the outline polygon (a single valid simple polygon -- NOT overlaid Edge.Cuts rectangles, which self-intersect the outline: that produced `invalid_outline` DRC errors, now fixed) at the axle line (y=118), 6mm deep x 34mm tall for ~32mm drive wheels.
- **N20 motor bodies** = keep-out rule areas (~26x13mm) on the axle line; the wheels sit in the edge notches; **motor-shaft through-slots** just inboard of each notch.
- **Front castor/skid**: keep-out + an M3 mount hole on the centerline.
- Side wall sensors WALL5/6 moved up to y=68 to clear the wheel notches (side sensors and wheels compete for the same side edges -- a real tension).

**Board size / layers -- FINAL user-driven iteration 2026-07-12 (later):**
- User referenced a micromouse dimensions diagram (body width 70-90mm, max height 70mm, 110mm diagonal corridor) and asked for a 90mm-wide, then 90x100, then **100x100 square with wheels inside the envelope**, keeping the sockets, "3-4 layer if needed."
- **Demonstrated conclusively that 100x100 + all three socketed modules + 14 sensors is infeasible** (11+ unavoidable courtyard overlaps after aggressive two-sided packing). Root cause, now understood precisely: the sockets/connectors/buttons are all THROUGH-HOLE, so their pins occupy every layer -- you cannot place other parts on the bottom underneath them (attempting it produced 27 DRC shorts). Two-sided packing only frees area under SMD top parts, and here the big parts are all THT. So the design is effectively SINGLE-SIDED-TOP (only the 8 SMD line sensors go on the bottom), which is what forces the larger board.
- **Layers don't fix fit** (components mount only on the two outer faces regardless of internal layer count) -- communicated to the user. The 4-layer request is honored as a stackup DESIGN (In1=GND plane, In2=+3V3 plane) but the board is currently generated as **2-layer with GND poured on both outer layers** because (a) pcbnew's zone filler segfaults headless and (b) an UNFILLED internal plane falsely shorts to every through-hole pad in DRC (a filled plane clears around each pad, but I can't fill/verify that headless). The 2-layer outer-GND version is fully DRC-verifiable; converting to 4-layer is a few GUI clicks (add In1/In2 planes, move GND to In1, fill) and does not change the routing. This is recorded at the top of build_pcb.py.
- **Final board: 150 x 185mm, single-sided-top, wheels INSIDE the envelope** (interior 9x32mm slots, not edge notches), front castor, 2WD axle at the rear. This is the honest minimum for keeping three socketed modules + 14 sensors; smaller is only possible by dropping sockets for SMD chips (offered, declined).

**Earlier size tension note (superseded by the above but kept for context):**
- Reference the user gave (kleberhub micromouse dimensions diagram): mouse body **width 70-90mm**, **max height 70mm** (vertical/Z envelope), **110.3mm** diagonal corridor clearance for diagonal runs. So a cell-legal full-size mouse is ~90mm wide.
- Current outline: **165mm wide x 210mm tall** -- deliberately LARGER than the 70-90mm reference. **The user was shown the hard conflict (sockets vs. 90mm size are mutually exclusive: two Nano-form-factor plug-in boards + a motor breakout + 14 sensors physically cannot fit a 90mm envelope) and explicitly chose "keep sockets, larger board"** -- i.e. a development/bring-up mouse that is easy to build and debug but is NOT competition-cell-legal (210mm cannot rotate in a 180mm cell). This is a conscious, recorded decision, not an oversight.
- To hit the 70-90mm competition size later would require reverting the socketed modules to bare SMD chips (STM32 QFP, ESP32-S3-MINI SMD, TB6612 SSOP) -- offered as an option, not chosen.
- Note the **70mm max HEIGHT** (Z) constraint is separate and still applies to the physical stack (socket headers ~8mm + module + tallest of {motor+wheel ~24-32mm dia}); the socketed modules add height but stay well under 70mm.

**Ref-stability refactor:** all non-sensor refs are now hardcoded and the ref() counter is re-seeded (Q=1,R=12,D=0) right before the sensor loop, so adding/removing module parts can never shift the sensor refs (Q2-Q29 / R13-R40 / D1-D14) that build_pcb.py and gen_connections.py depend on. CONNECTIONS.md regenerated (119 nets, coverage-enforced, 0 missing) with all module/mechanical changes and the socketing table.

**Routing pipeline (now the primary router):** KiCad placement (build_pcb.py) → Specctra DSN export (export_dsn.py) → **Freerouting 2.2.4 headless** (`java -jar freerouting.jar -de in.dsn -do out.ses -mp 60`, ~30-40s, routes all ~175 connections to score ~994, 0 unrouted) → SES import (import_ses.py, pcbnew.ImportSpecctraSES) → kicad-cli DRC (0 violations). The in-house MST+A* router (gen_pcb.py) is kept as a documented from-scratch fallback but Freerouting is faster and completes 100%.

## 2026-07-13: user hand-edits the board -> switched to IN-PLACE modification (do NOT run build_pcb.py)

The user started manually repositioning components in the KiCad GUI and asked to keep those positions. **build_pcb.py regenerates placement from scratch and WILL clobber the user's manual layout -- do not run it anymore** unless first re-syncing its coordinates to the board. New workflow via `tools/finalize.py`: LOAD the existing board, keep every footprint position, strip only tracks/vias, apply design rules, re-export DSN, Freerouting, import SES. Positions preserved by construction.

New user requirements folded in / pending:
- **No trace between through-hole pins** (avoid hand-solder bridges): enforced by raising routing clearance to **0.3mm** -- with ~1.7mm pads on 2.54mm pitch the inter-pin gap is ~0.84mm, and 0.3+0.25(trace)+0.3 = 0.85 > 0.84, so no trace can fit between adjacent THT pins. Set on the board's default netclass + exported into the DSN (verified: DSN shows `(clearance 300)`).
- **Real module footprints + 3D** (STM32 Nucleo, ESP dev board, TB6612 breakout): dimensions/pin-counts are ALREADY correct (15.24mm-row 30-pin Nano sockets; 16-pin 2x8 TB6612) per research matching robu.in/robokits parts. BUT the module 3D bodies can't render -- this KiCad install ships none of the Arduino/Nano/ESP/module 3D model files (Module.3dshapes has 10 files, none of these) and free downloadable ones are login-walled (SnapEDA) or a different board (jahm86's is the bigger DevKit V1). The socket HEADERS render in 3D; the plug-in module boards need their .step/.wrl added locally (a GUI step). Deferred, communicated.
- **Smaller ESP OK**: keeping the Arduino Nano ESP32 (smaller than the 30-pin DevKit V1, which the research found is the popular-India board but has 25.4mm rows and is larger).
- **More motor space for mounts**: build_pcb.py has enlarged motor keep-outs (34x34mm bracket envelope + M2.5 mount holes), but since the user is hand-editing, applying it must not move their parts -- pending confirmation of approach.

**Freerouting SES-write is intermittently hanging** post-completion (writes fine some runs, hangs others). Reliable pattern: launch detached, poll for the .ses FILE to appear (routing itself finishes in ~60s), then kill the java process (it hangs after writing). If it won't write, the in-house gen_pcb.py router is the fallback (~90% completion vs Freerouting's 100%).

## 2026-07-12: scripted autorouter -- how it works and every bug class it hit (don't rediscover)

`tools/gen_pcb.py` now contains a real 2-layer autorouter (used by `tools/route_pcb.py`); GND stays on the twin full-board pours, everything else gets copper. Architecture: per-net Prim MST over pad centers -> per-edge A* over a 0.5mm two-layer grid (via moves cost ~4mm-equivalent) -> **continuous-geometry verification with true clearances before any copper is committed** (grid search is the planner, exact geometry is the judge -- same philosophy as the schematic's netlist cross-check). Obstacles come in two tiers per layer: **hard** = another net's actual copper grown by our half-width (never traversable), **soft** = comfort clearance + 0.75*grid inflation (traversable only within an escape radius of the route's endpoints, needed because fine-pitch neighbors' clearance disks overlap the pad being escaped -- SSOP-24 at 0.65mm, ESP32 at 0.85mm). Verify-failures walk a retry ladder (shrinking escape radius, then 4-dir-only). Board-edge margin (0.7mm) and the ESP32 antenna keepout (a real rule-area zone read from the footprint) are static obstacles on both layers.

Bug classes found on the way (each confirmed via `kicad-cli pcb drc` ground truth, all fixed):
1. **Layer-blind pads**: treating every pad as front-side shorted/dangled tracks the moment the line sensors moved to B.Cu -- pads now carry real per-layer presence (SMD = its side only, THT = both).
2. **Diagonal corner-cutting**: an A* diagonal step can pass grid*sqrt(2)/2 closer to an obstacle than either endpoint cell; one such step grazed a pad and shorted PLUS3V3 to an LED net. Hence the 0.75*grid obstacle inflation (and the continuous verifier as backstop).
3. **Vias dropped on THT pad centers** (drill-in-drill, 37 hole-collocation warnings) -- vias now only appear at genuine layer-change points, deduped per net within 0.85mm (0.5mm-spaced same-net vias earlier tripped the 0.25mm hole-to-hole rule).
4. **Escape-zone tunneling**: the escape allowance let A* propose paths straight across the NEIGHBORING pad of an 0805 (both pads inside the radius), which verification then always rejected -- unroutable loop. Fixed by the hard/soft split.
5. **Congestion ordering**: routing the wide power webs first fenced the board (24 failed nets); signals-first-ascending still starved the long runs (16 fails, retry recovered 2). Current order: sub-2mm micro-bridges across ALL nets first (the TB6612's doubled output pins have exactly one legal route hugging the pad column -- anything else there first kills them), then signals LONGEST-first, then PLUS3V3, then the fat motor/battery nets, then a 400k-expansion retry pass. Mild H/V layer discipline (top prefers horizontal, bottom vertical, 1.25x soft cost) stops long runs on different layers from fencing each other.
6. **pcbnew segfaults**: `ZONE_FILLER.Fill()` headless and `FOOTPRINT.Flip()` before `board.Add()` both segfault this KiCad build -- fill zones in the GUI (press B), flip only after adding.

Board rules registered in the file (so kicad DRC enforces what the router built): clearance 0.127mm, min track 0.2mm, via 0.6/0.3mm, hole-to-hole 0.2mm -- all standard JLCPCB capability. Routed geometry: signals 0.25mm width at 0.15mm routed clearance (0.13mm verify floor), power 0.5mm.

## 2026-07-12: routing status (final for this session)

Board: **2 layers** (F.Cu + B.Cu), GND poured on both. Autorouter (gen_pcb.py) result after 5 progressive passes: **129 of 137 nets fully track-routed, 0 DRC violations** for everything routed. **8 edges remain unrouted**, all in the congested center band between the MCU socket and motor driver:
- 3 sensor tracks: `WALL3_SENSE`, `LINE3` LED-anode (`Net-(D9-A)`), `LINE4` LED-cathode (`Net-(D10-K)`).
- 5 `PLUS3V3` web edges (the 52-pin rail threading the center).

So 11 of 14 sensors are 100% track-routed; 3 sensors each have exactly ONE remaining track segment. Every sensor's GND-return side (phototransistor emitter, LED-switch source) rides the GND plane.

**Two finishing steps only a human/GUI can do here (both flagged, neither a design defect):**
1. **Fill zones (press B in KiCad).** 98 of the ~106 remaining ratsnest items are GND pads that connect through the GND pour -- but the pour must be FILLED to become real copper, and `pcbnew`'s zone filler segfaults headless in this environment, so I could not fill/verify it. The pour polygon covers the whole board inset 2mm, so every in-board GND pad will connect on fill. After filling, only the 8 signal/power edges above remain.
2. **Close the last 8 edges** -- ~2 minutes of manual trace-dragging in the GUI, OR they largely vanish if PLUS3V3 is converted to a top-layer pour (which again needs the GUI fill to verify). This is the normal "last 10% by hand" of a dense 2-layer board; the autorouter got 94% and stalled exactly where a from-scratch MST+A* router is expected to (cross-congestion on 2 layers at 4-layer density).

Router lives in `tools/gen_pcb.py` + `tools/route_pcb.py`, fully regenerable; every routed track was continuous-geometry-verified before commit and the whole board re-checked with `kicad-cli pcb drc`.

## Fixed: MCU header was the wrong physical footprint (caught by user, 2026-07-11)

User pointed out (comparing against ST/Mouser's real NUCLEO-G431KB bottom-layout photo) that the socket didn't look like it could physically accept the real module. They were right, and it was a real error, not just a stylistic choice:

- **What was wrong**: used a single `Connector_Generic:Conn_02x15_Odd_Even` symbol with footprint `Connector_PinSocket_2.54mm:PinSocket_2x15_P2.54mm_Vertical` -- a *compact* dual-row header with both rows only 2.54mm apart (like a standard IDC/pin-header strip).
- **What's actually true**: a real Nano-form-factor board (Arduino Nano, and Nucleo-32 boards like the G431KB specifically because they're designed to be Nano-header-compatible) has TWO SEPARATE 15-pin single-row headers (CN3, CN4) on the two opposite long edges of a narrow ~18mm-wide, ~38mm-long board -- 15.24mm (0.6") apart, not 2.54mm. Confirmed two ways: (1) the module's real bottom-layout photo the user linked, and (2) KiCad's own bundled reference, `share/kicad/template/Arduino_Nano/Arduino_Nano.kicad_pcb`, which places two separate `Connector_PinHeader_2.54mm:PinHeader_1x15_P2.54mm_Vertical` footprints exactly 15.24mm apart -- not a single 2x15 part.
- **Fix**: split the schematic's single J4 into two `Conn_01x15` symbols -- J4 (=CN3, pins 1-15) and J8 (=CN4, pins 1-15) -- each with footprint `Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical`, preserving the exact same net-per-physical-pin mapping as before (just split by the original odd/even grouping, which was already tracking real CN3 vs CN4 positions). On the PCB, placed 15.24mm apart as two parallel columns. Re-verified: ERC still 0/0, netlist cross-check still passes (GND/VM_BATT/PLUS3V3/motor/encoder/ESP32/sensor nets all still correct and distinct), PCB DRC still 0 violations after re-placing.
- **Lesson for next time**: for socketed dev-board modules, verify the footprint against the module's real physical photo/mechanical drawing *before* trusting a schematic symbol's default footprint assignment -- a symbol can be electrically correct while its assigned footprint doesn't match the real part's shape at all. This wasn't caught by ERC or DRC (both only check electrical/spacing rules, not "does this footprint's shape match reality") -- only caught by the user's visual comparison against a real photo, same category of gap as the earlier wire-routing short that only netlist diffing caught, not ERC.


---

## 2026-07-14: ESP32-only redesign -- board shrunk to 100 x 128mm, 4 layers

User decisions: (1) DROP the STM32 entirely; a single socketed **Arduino Nano
ESP32** (ESP32-S3) is now the sole controller (control + telemetry), chosen to
shrink the board; (2) use the ACTUAL library footprint so dimensions are real;
(3) pack components very close to satisfy the dimension target.

**What changed**
- Schematic: MCU section removed; the ESP32 section became the CONTROLLER
  section. One 30-pin part `A1` (symbol `Conn_02x15_Odd_Even`, footprint
  **`Module:Arduino_Nano`** -- the real KiCad land pattern, pin==pad 1:1,
  orientation locked against the footprint's USB silk marker). All control nets
  kept their NAMES; only their source pin moved. ADC nets (MUX_SENSE,
  VBAT_CELL1/PACK_SENSE) sit on A0/A1/A2 (ESP32 ADC1 works with WiFi on).
  USART1_TX/RX, NRST, and the flash-relay wiring are GONE (ESP32 flashes over
  its own USB-C / OTA). L1 downsized to `L_Bourns_SRP7028A_7.3x6.6mm` (the
  SRR1260 was the biggest overlap source in the tight power band).
- ESP32-only GPIO map (30-pin Nano header, see build_schematic.py A1_MAP):
  A0=MUX_SENSE A1=CELL1 A2=PACK A3..A5=MUX_S1..S3 A6=LED_PULSE A7=USER_BTN
  D13=MUX_S0 D12/D11=ENC1_A/B D10/D9=ENC2_A/B D8/D7=PWMA/PWMB D6/D5=AIN1/2
  D4/D3=BIN1/2 D2=STBY; D0/D1 left free for USB-serial debug. Encoders use the
  ESP32-S3's 4 PCNT units (hardware quadrature, any-pin via GPIO matrix); PWM
  uses LEDC (any pin).
- Board: **100 x 128mm** chamfered outline (was 150 x 185), wheels inside via
  interior slots at AXLE_Y=108, castor hole at (50,4) (NOT (50,8) -- that sat in
  the middle of the bottom line array and made LINE3/4 unroutable). All 6 wall
  sensors are compact side-edge clusters (front pair aims diagonally forward);
  their THT LEDs are ROTATED 90deg so pads stack vertically -- horizontal pads
  reached x=14.5 and shorted into the bottom line-sensor columns (caught by DRC
  at D1/R26). Line array: 8 columns, 9.525 QTR pitch, 5mm intra-column pitch
  (4mm left no routing channel at 0.3mm clearance).
- **4 copper layers**, all signal (user pre-approved 3-4 layers). The in-house
  router was generalized from hardcoded F/B to an N-layer `LAYERS` list: THT
  pads pierce/connect all layers, SMD pads only their face, through-vias join
  every layer, alternating H/V discipline per layer. 2 layers left 40-51 edges
  unroutable; 4 layers + a final 0.25mm fine-grid retry pass got it to **5**.
- Freerouting note: on this board it ROUTES perfectly (~15-24s, score 995) but
  its SES writer never returns -- reproducible with and without the optimizer
  (-mp 1 -oit 99). Same hang as the old board. Do not burn time on it; the
  in-house 4-layer router is the working path.
- pcbnew API landmine (new): REMOVING many tracks from a loaded board corrupts
  SWIG proxies for the rest of the process (footprint.Pads() raises
  'SwigPyObject not iterable', GetDesignSettings dies). route_loaded.py now
  REFUSES a tracked board -- always regenerate trackless via build_pcb.py first.
- verify_clr raised 0.13 -> 0.16 (was below the 0.15 netclass clearance, so the
  router legalized 0.145mm squeezes that DRC then flagged).

**Verified state (kicad-cli, headless)**
- ERC: 0. DRC: **0 errors** (9 cosmetic silk warnings). 2012 tracks, 150 vias,
  105 footprints, 96 nets documented in CONNECTIONS.md (coverage-enforced).
- Remaining for the GUI: fill the GND pours (B), route the last **5 edges**
  (4x PLUS3V3 spokes + 1 LINE6_LED), optionally convert In1/In2 to GND/3V3
  planes (then delete the outer pours + the PLUS3V3 spokes entirely).
- Honest caveats: 0.3mm routing clearance is blanket EXCEPT endpoint escape
  zones (<=1.8mm from a route's own pads) where 0.16mm squeezes are allowed --
  necessary at the SOIC muxes; near THT pin rows the escapes exit perpendicular
  in practice but this is not a hard guarantee. Nano-ESP32 header->GPIO->
  ADC1-channel mapping must be confirmed in firmware. TB6612 breakout pin order
  varies by vendor -- verify before fab.


---

## 2026-07-15: rev 3 -- indicator LEDs, research-verified sensor geometry, 100x114

User requests: (1) a top-side indicator LED per line sensor whose brightness
varies with the IR receiver; (2) wall-sensor positioning per professional
projects; (3) a smaller, tighter board.

**Indicator LEDs (D15-D22 + R41-R48 + Q30-Q37, top face over each column)**
- Topology: BSS138 gate directly on each LINEx_SENSE node; drain sinks a
  visible red 0603 from +3V3 via 1k (~1.3mA). A MOSFET gate draws no DC
  current, so the 47k divider and the muxed ADC reading are untouched --
  an NPN follower would have skimmed ~10uA of base current (~0.5V of divider
  error), and hanging an LED directly on the node (the naive way) is exactly
  what Pololu's own guidance warns against. Brightness follows the node
  analogically: dark line under the sensor -> node high -> brighter.
  Continuous, upstream of the mux, zero firmware.
- ADVERSARIALLY REVIEWED (2-agent refutation pass + 3-agent primary-source
  research, 2026-07-15). Confirmed: zero-DC-load (<=100nA worst-case gate
  leakage = ~5mV on the 47k, typ <<1 LSB), direction (dark line -> LED on),
  ~1.4mA sizing, thermal non-issue (~0.5mW max in the FET). REFUTED and
  fixed:
  (1) "analog brightness" -- the BSS138's ~100mV/decade subthreshold slope
      compresses the whole visible fade into ~150-300mV, so it is a crisp
      THRESHOLD indicator (which is the better UX for 8-LED line reading;
      it's also what all commercial boards build, via comparators). Docs
      reframed; Vth spread 0.8-1.5V is harmless because the node swings
      <=0.5V (lit floor) to >=2.5V (dark line), straddling every possible Vth.
  (2) DUTY-CYCLE BLINDNESS (the big one): emitters are demux-PULSED one at a
      time, so each node is ambient-dominated ~93% of the time and the
      indicator would mostly display ambient light. FIX: line-channel
      current-limit resistors changed 33R -> 120R (~15mA; line range is ~3mm
      so margin is ample, QTR-class boards run continuous at similar
      currents), letting firmware LATCH all 8 line emitters on continuously
      in line-follow mode (~120mA total) -- indicators are then live. Wall
      channels keep 33R/~50mA pulsed for the 60-180mm range. FIRMWARE RULE
      recorded in the schematic text.
  (3) BOM constraints: indicator LEDs must be high-efficiency AlInGaP
      super-red (e.g. Kingbright APT1608SURCK) -- standard red is washed out
      in daylight at 1.4mA, and InGaN colors have no Vf headroom on 3.3V.
      The 8 line receivers must be the DAYLIGHT-FILTERED variant (SFH320FA,
      not SFH320) or the red indicators feed back optically into the ADC
      readings. Both requirements are in the Value fields.
  (4) Sampling detail: the gate adds ~30-150pF (Miller) to LINE nodes only;
      firmware should tune the post-mux ADC settling delay on a LINE channel
      mid-transition (the slowest case), not on a WALL channel.

**Wall-sensor geometry -- verified against Harrison/Decimus, UKMARS, Zeetah**
Primary-source findings (micromouseonline.com, ukmars repo, retrieved 2026-07-15):
- Decimus ran SIX assemblies, verbatim: "Two face almost sideways, two face
  diagonally at around 45 degrees ... and two more face nearly forwards".
  Wall sensors belong "well in front of the driving wheels, or at least, the
  centre of rotation" -- the forward lever arm makes heading errors visible
  early; the greater the distance the better.
- Harrison later found 90-degree side sensors "give the information too late"
  -- the ~45-degree diagonals became the steering workhorses, and "any future
  mice will have the sensors pointing significantly farther forwards".
- Forward sensors are toed OUTWARD a little (post detection on diagonals +
  never hitting a shiny wall at exactly 90 degrees); side sensors are angled
  FORWARD a little (earlier edge detection, and a heading error then shows as
  a left/right difference which perpendicular sensors cannot see).
- Zeetah VII: emitter-detector centre spacing ~7mm (ours: 7-8mm). UKMARSBOT
  advanced sensor: forward pairs on CHAMFERED corner edges -- the board
  outline sets the aim, same trick as our chamfers.
- Vertical aim: target spot ~20mm above the floor, sensors tilted up a touch
  (cuts specular reflection off shiny walls). Fit short heat-shrink sleeves
  over the 5mm emitters ("emitters well shielded from the detectors").
This board (axle y=92): front pair anchors (30,3)/(70,3) = 89mm ahead of the
axle, diagonal pair (5,18)/(95,18) ON the chamfered corners = 74mm, side pair
(5,36)/(95,36) = 56mm -- the Decimus arrangement, everything far forward.
ASSEMBLY: bend front pair slightly outward, diagonals 45 out (chamfer line),
side pair 90 out with slight forward toe; all tilted up a little; heat-shrink
each emitter; epoxy after aiming (Harrison's alignment procedure).
Diagonal/side clusters stack the LED BEHIND the photo along the edge -- the
5mm LED's 7.1mm courtyard cannot sit beside the photo without hitting the
line array's first column; optically irrelevant since leads are bent to aim.

**Board shrink 100x128 -> 100x114 (area -11%)**
- A1 rotated HORIZONTAL (rot=270; calibrated: analog row runs -x at anchor y,
  digital row +15.24 toward the rear where the TB6612 lives) -- its 43.6mm
  length now spends the board's width. Muxes rot=0 vertical on the side edges
  (measured: rot=90 lays a SOIC-24W HORIZONTAL, 16mm of x). TB6612 header
  rows horizontal under A1. Axle up at y=92.
- Width stays 100: pinned by the 76.2mm line array + two side clusters.
- Courtyard lesson: MEASURE, don't estimate (F.Courtyard bboxes): LED_D5.0 is
  a 7.1mm circle, LED_0603 is 3.0mm wide, SW_PUSH_6mm is 9.5mm, SOIC-24W is
  16.0mm long. Guessed sizes cost three placement iterations.
- Mounting holes are circles on Edge.Cuts that the router's outline check
  does not see -- a VM_BATT track ran inside a hole's edge clearance (real
  DRC error). route_loaded.py now blocks a square around every hole.


---

## 2026-07-15 (later): rev 4 -- WROOM-1 module, 1S power, direct wall ADC, full I/O suite

User requests, all in one sweep: (1) mux only for the line array, wall sensors
on ESP32 analog pins; (2) exact ESP32 library footprint + 3D model; (3) exact
N20 library; (4) an ESP32 with speed + RTOS; (5) 1S LiPo; (6) at least 3 user
buttons; (7) USB-C at the rear; (8) JTAG debug outlet; (9) wall indicator LEDs
on top too; (10) competition-grade emitter/receiver positioning. (Two 7-seg
displays were requested then withdrawn.)

**Controller: ESP32-S3-WROOM-1 (U3, SMD)**
- The only ESP32 in stock KiCad with BOTH exact footprint and 3D STEP. Dual-core
  LX7 @240MHz, FreeRTOS native. Bare module = 10 WiFi-safe ADC1 channels
  (IO1-10), which is what makes direct wall-sensor reading possible at all
  (the Nano dev board exposed only 8 analog pins; 6 wall + mux + battery = 8
  fit exactly with zero spares -- the module gives headroom + the dedicated
  USB pads + JTAG quad).
- LOCKED PIN MAP in build_schematic.py (U3_NET). Highlights: IO1-6 walls,
  IO7 mux common, IO8 battery; IO39-42 = the real JTAG quad -> J8 (2.54mm 1x6: 3V3,TMS,TCK,TDO,TDI,GND
  -- a 1.27mm 2x5 proved UNROUTABLE at the 0.3mm no-inter-pin clearance); IO43/44 (UART0) = ENC2 via 1k series guards -- ADVERSARIAL-REVIEW
  BLOCKER: IO43 is U0TXD, actively driven by the ROM at every boot, and would
  fight a push-pull encoder driver-vs-driver without the guard. Console moves
  to native USB-CDC (firmware: CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG).
- Straps: IO0 = SW1 (start button doubles as BOOT -- hold SW1, tap SW2/reset
  for download mode); IO45=BIN2, IO46=STBY as IDLE-LOW outputs with 10k
  pull-downs (R65/R66) -- IO45 high at reset selects 1.8V VDD_SPI and bricks
  the boot; the pull-downs also hold the motor driver disabled through boot.
  NEVER add pull-ups to those two nets. IO35/36 = buttons 2/3 (gone on
  octal-PSRAM -R8 modules -- sacrificial; use N16-class modules).
- Antenna: Espressif guidelines (verified from the official PDF) DISALLOW
  interior placement. Module sits on the RIGHT edge, rot=270, anchor
  x=93.25 -> the antenna section AND the footprint's embedded keepout zone
  land entirely off-board past x=100. Mid-edge overhang (corner is the gold
  standard; both rear corners are wheels, both front corners are chamfered
  sensor mounts). WiFi is telemetry-only.
- Support circuit per Espressif: EN = 10k + 1uF + SW2; USB-C (rear, GCT
  USB4105) -> USBLC6-2SC6 ESD array -> 22R series -> module USB pads; CC1/CC2
  5.1k pull-downs; VBUS deliberately NC (battery powers the board -- flash
  with the battery on, documented).

**1S power (was 2S)**
- TPS63001 BUCK-BOOST (a buck can't make 3.3V from a cell sagging below
  ~3.8V); 1.2A covers WiFi bursts. TPS63000 base symbol instantiated (the
  extends-skips-ERC workaround), 1.5uH between L1/L2, FB tied to VOUT (fixed
  3.3V part), PS/SYNC low.
- No balance connector; ONE divider (22k/33k -> 2.52V max: the S3 ADC's
  calibrated range tops at ~2.9V with worst error near the top -- review
  fix), tapped DOWNSTREAM of the switch (no storage drain).
- Motors on raw 1S: TB6612 VM min 2.5V OK; ORDER 3V-WOUND N20s (a 6V wind at
  3.7V gives ~60% speed). Fuse now 2A.

**Sensor architecture rework**
- U4 (single mux, line array only): swapped HEF4067BT -> CD74HC4067M -- the
  CD4000-family part is only spec'd from 3V with kR-class Ron at 3.3V (review
  catch); HC is ~70R. Pin geometry verified IDENTICAL. S3 tied low (8 ch).
- U5 (write demux) DELETED. Emitters ganged UKMARS-style: front pair / diag
  pair / side pair / line bank on four BSS138s (Q16-19, gates IO15/16/17/14,
  100k boot pull-downs R62/63/64/61). Firing a wall pair + reading BOTH its
  ADC channels in parallel halves scan time vs the serial mux walk.
- Ref renumbering (regenerators updated): photos Q2-15, group FETs Q16-19,
  line indicators Q20-27/D15-22/R41-48, wall indicators Q28-33/D23-28/R49-54.
- WALL INDICATORS (new): 6 top-side LEDs near the front, PMOS-driven
  (BSS84-class, Q_PMOS base symbol): wall reflection pulls the node LOW ->
  PMOS on -> LED ON = wall seen (inverted vs the line indicators' NMOS
  because the intuitive polarity flips). Same zero-DC-load gate principle.
- WIRE-COLLISION BUG (real, caught in the netlist audit): the sensor loops'
  Z-bend wires landed bend columns on unrelated pins every 6th sensor (lane
  counter period 12 / 2 wires per iteration), folding D3/D9 anodes into
  cathode nets and shorting two indicator drains into neighboring SENSE
  nets. FIX: all loop passives are now x-aligned with their pin columns so
  every generated wire is dead straight (no bends at all). Lesson recorded:
  never Z-bend inside a repeated loop.

**N20 library (project-local)**
- Stock KiCad has NO N20 (checked). tools/gen_n20_lib.py generates
  n20.pretty/N20_Motor_Encoder (pad-less mechanical footprint) +
  n20.3dshapes/*.wrl (hand-authored VRML, 1 unit = 2.54mm). Dimensions from
  Pololu's official drawing 0J949: gearbox 12.0x10.0x9.0 (+0.7 faceplate),
  can dia12 flatted-10 x15.4, 3mm D-shaft x10; encoder extension is VENDOR-
  DEPENDENT (~5-12mm; modeled 8 -- verify your unit). MOT1/MOT2 placed at
  true positions; motor keep-outs enlarged to the TRUE 33mm body length --
  which is also why the module could NOT go rear-center (31+31+18 > 100-24).

**Board: still 100x114.** Rear strip (y>107) = USB-C + ESD + CC + battery +
divider. Buttons row y=44 front-center. JTAG beside the module. 152
footprints placed, 0 courtyard overlaps.


Rev-4b DRC hardening (same day): min-through-drill 0.2 (WROOM/TPS in-pad
thermal vias), hole-clearance 0.15 (GCT USB-C NPTH pattern), motor keep-outs
allow the MOT footprints they represent (width trimmed to 20mm freeing the
rear strip), J7 pulled to y=109.3 so its pads clear the rear edge rule, power
rows moved to y=68/74 with the tall inductor + output cap in the inter-motor
corridor, router mounting-hole keep-outs recomputed from the placement formula
(they were stale -- tracks hugged the new hole positions), via-vs-keepout test
now includes the via radius.


---

## 2026-07-16: rev 5 -- SMD driver, rear service panel, research-exact sensors, route-to-zero

User directives: TB6612 as SMD; ESP32 at the rear with the antenna outside the
chassis; USB-C + JTAG near it; motor driver + motor connectors also near it;
switches at the rear, lettered A/B/C (+RST) on silk; motors a little forward;
PCB holes for a downloadable 3D-printable N20 bracket (with link); bottom-side
SMD allowed; EVERYTHING routed, nothing left behind.

**N20 mounting bracket (research, STL-measured -- print this):**
- WINNER: UKMARSBot printable Pololu-pattern bracket (MIT licence):
  https://github.com/ukmars/ukmarsbot -> mechanical/pololu-gear-motor-bracket-standard.stl
  (raw: https://raw.githubusercontent.com/ukmars/ukmarsbot/master/mechanical/pololu-gear-motor-bracket-standard.stl)
  12.0 x 26.6 x 12.0mm saddle clamping the N20 gearbox to the board; screws
  from the underside into nuts captured in the bracket tabs; M2/M2.5/M3 all fit.
- PCB pattern drilled on this board (per motor): 2x D3.2mm NPTH, 18.0mm c-c,
  perpendicular to the motor axis, symmetric about the axle line, 4.25mm
  inboard of the gearbox faceplate -> holes at (17.25, 75)/(17.25, 93) and
  (82.75, 75)/(82.75, 93) with the axle at y=84.
- Runner-up (also fits M2, holes ALONG the axis -- NOT drilled here):
  thingiverse.com/thing:6895505. Extended-wheel variant of the winner:
  pololu-gear-motor-bracket-extended.stl (same pattern, 13.75mm setback).

**Wall sensors -- research-exact geometry (UKMARSBOT advanced V1.2 parsed
from its .kicad_pcb + Decimus/Zeetah doctrine):**
| pair | detector | emitter | aim |
|---|---|---|---|
| FRONT-L/R | (33.8,3.5)/(66.2,3.5) | (26.2,3.5)/(73.8,3.5) | 10 deg toe-out |
| DIAG-L/R | (12,9.5)/(88,9.5) | (7,14.5)/(93,14.5) | 45 deg (chamfer normal) |
| SIDE-L/R | (5,24)/(95,24) | (5,31.5)/(95,31.5) | 75 deg (15 fwd of perp) |
Arrangement: detector FORWARD, emitter ~7.5mm BEHIND, in-line along the local
edge, both co-aimed (Zeetah ~7mm / UKMARSBOT 7.6mm pair spacing). The earlier
side-by-side-across-the-aim layout was wrong -- this replaces it. ASSEMBLY:
bend up ~5 deg (spot ~20mm above floor), heat-shrink every emitter, epoxy
after optical alignment. Angles follow Harrison's parsed 10-deg front toe-out
and the never-90-to-a-shiny-wall rule (side = 75 not 90); 45 diag per Decimus.

**Rear service/drive panel (final, board grown 114 -> 100x120mm for a real
rear fan-out band after 9 routing iterations proved the panel density-bound):**
ESP32 (U3) rear-center-left, rot 180, anchor (35.25,107.5) -- ANTENNA
OVERHANGS THE REAR EDGE (Espressif-preferred placement; the interior-slot
option was dropped when the user chose the rear). USB-C J7 (54,114.3), mouth
out the rear, recessed 1mm to widen the pad-row strip its nets live in;
USBLC6 ESD U6 (54,106,B). JTAG J8 = 2.54mm 1x6 at (76,55) mid-band (the
1.27mm 2x5 was unroutable at 0.3 clearance, and the first rear spot sat on
the motor). Buttons SW1/SW3/SW4 at (71/81/91,114) with silk letters A/B/C
BELOW each button (y118.6 -- the first offset hid A under J6's housing);
RST SW2 (64,102). TB6612 U2 (64,66) mid-band (its first canyon between the
motor courtyards defeated even micro-bridges). J5 (8,107) / J6 (76,107);
battery J1 (8,116). CC pulldowns R12=CC1 (62,110,B) / R56=CC2 (46,110,B) --
initially crossed (east pad to west resistor and vice versa), which forced an
X inside the USB pocket; uncrossing them was one of the route-to-zero keys.
VBUS divider R67/R68 (20/14,111,B) -> IO37 cable detect. Bottom face carries
the support passives (EN RC, decoupling, CC, encoder pull-ups/guards, strap
pull-downs, dividers, wall-sensor pull-ups/limiters).

**Route-to-zero machinery (final: 0 unrouted, DRC 0/0/0, ERC 0):**
- In1 = GND plane, In2 = +3V3 plane (solid-connect), VM_BATT partial B.Cu
  pour (16,44)-(99,113). Headless ZONE_FILLER works on KiCad 10.0.4 (the old
  segfault lore is STALE -- retested). Signals are ALLOWED on inner layers;
  fill flows around them (island removal = ALWAYS, else inner-layer traffic
  strands slivers).
- route_loaded.py pipeline (each stage earned by a failure class):
  hand-bridges (J7 D+ pair on F.Cu; VBUS stack link on In1 -- the two VBUS
  stacks flank the D/CC field so no F.Cu path exists, and B.Cu/behind-row
  placements blocked the CC escape vias) -> fan-out stubs (U1/U2/U3) ->
  pre-stitch of jail-prone pour pads (U6.2, U2.9/10/18/20; direction ladder
  aims UNDER THE BODY -- free real estate signals never fight over) ->
  JAILED-first nets (USB pocket + whole U2 control cluster + junction nets),
  each getting its FULL retry ladder immediately while the board is empty --
  the single biggest win; letting failures wait for the global ladders on a
  full board is what kept the pockets in whack-a-mole for seven iterations ->
  plane stitching -> priority nets (wall/line/mux sense, encoders BEFORE
  motor sweeps, chip-attached long nets) -> micro-bridges -> signals
  (span-sorted) -> power -> retry ladder (400k -> WIDE 0.4-clearance rung ->
  0.25/1.2M -> 0.2/2M -> SMD-relief 0.18 with THT pads always keeping 0.3).
- The WIDE rung fixes a pathology: A*'s cost-optimal path hugs a pad,
  verification rejects it, and every rung then finds the SAME path -- forcing
  0.4 obstacle clearance makes the planner keep verify-proof distance.
- THT-vs-SMD clearance split: _verify_geo now enforces 0.3mm against any
  holed pad on EVERY verification path (including the string-pull smoother,
  which previously verified shortcuts at 0.16 uniformly -- latent hole) while
  SMD may relax to 0.16. The user's hand-solder rule is structural now.
- _commit_via near-duplicate replacement stitches on ALL routing layers (was
  F/B only -- an F->In2 transition left its inner run dangling; found as a
  DRC unconnected on LINE3_SENSE).
- heal_all.py: convergent post-pass. Loops DRC -> heal -> refill -> DRC:
  copper-pair gaps get A* micro-routes (retry_edge doglegs through
  fine-pitch fields); pour-net items get stitch vias laddered to their
  plane; zone fragments (anchored by a stitch via, walled off by inner-layer
  tracks, so island removal keeps them) get a via dropped where same-net F/B
  copper overlies the fragment polygon. Converged in 4 rounds from 8
  unconnected to zero.
- check_overlaps upgraded to per-courtyard-piece testing (the module's
  off-board antenna rectangle no longer falsely claims the rear panel), with
  a justified-whitelist for rotated-part bbox over-flags.
- Final numbers: ~1240 tracks, ~310 vias, 4 layers, ERC 0, DRC 0 violations /
  0 unconnected / 0 schematic-parity issues.
