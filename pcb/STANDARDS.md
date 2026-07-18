# Standards & Impedance Compliance — micromouse-pcb rev 6

Scope: 4-layer 100×120 mm robot PCB (ESP32-S3, USB 2.0 full-speed device,
2S LiPo 8.4 V max, 20 kHz motor PWM up to ~3 A). Stackup: F.Cu signal /
In1 GND plane / In2 +3V3 plane / B.Cu signal+pours (JLC7628-class:
0.035 mm outer Cu, 0.21 mm prepreg, 1.065 mm core, εr ≈ 4.6).
Sources: USB 2.0 spec ch.7, IPC-2221B, IPC-2152, IPC-7351/2610, Espressif
ESP Hardware Design Guidelines, TI/Diodes/Toshiba/Bosch datasheets.
(Research pass 2026-07-17; full details in PROJECT_NOTES.md.)

## 1. USB 2.0 impedance position (requirement: "check impedance matching")

The 90 Ω differential controlled-impedance requirement in USB 2.0 applies to
**high-speed (480 Mbps)** signalling only. This board's ESP32-S3 PHY is
**full-speed (12 Mbps)**: the spec constrains the cable (90 Ω ±15 %) and the
driver output impedance (28–44 Ω), not captive board traces. Physics check:
FS edges are 4–20 ns ≈ 660 mm on FR-4; the critical length (edge/6) ≈ 110 mm
exceeds any route on this board — every trace is electrically short.

What we implement anyway (pragmatic FS rules):
- D+/D− routed as a coupled pair over **continuous In1 GND** end-to-end, no
  plane splits under the pair.
- Intra-pair length match ≤ 2.5 mm (HS-grade; FS tolerates ~10 mm). Verified
  per revision in TRACE_REPORT.md (rev-5 measured 6.2 mm ≈ 41 ps against an
  ~4 ns FS edge = 1 % — rev 6 target is tighter; see the current report).
- **No series termination resistors** — the S3's integrated PHY meets the
  driver-impedance window internally; every Espressif S3 devkit routes
  GPIO19/20 directly. Rev 6 removed the rev-5 22 Ω resistors accordingly.
- ESD array (USBLC6-2SC6) adjacent to the connector, stubs ≤ 2.5 mm.
- Reference geometry for a true 90 Ω diff pair on this stackup (if a future
  rev goes high-speed): w = 0.27 mm / gap = 0.20 mm bare-board (IPC-2141:
  Z0 = 55.4 Ω, Zdiff = 90.4 Ω); with solder mask expect ~0.21/0.18 mm from
  the fab's field solver — order impedance control before relying on it.

All other signals on this board are DC–20 kHz class (motor PWM, IR pulses,
400 kHz I2C): at these frequencies trace impedance is irrelevant; what
matters is IR drop and loop area, covered below and in TRACE_REPORT.md.

## 2. Clearance / creepage (IPC-2221B)

8.4 V DC falls in the 0–15 V band: 0.05 mm internal / 0.10 mm external
required. The board's design rule (0.2 mm nominal, 0.16 mm floor in dense
SMD fields, 0.3 mm no-inter-pin hand-solder rule for THT) exceeds the
standard everywhere. First voltage where IPC clearance would bite: > 30 V.

## 3. Ampacity (IPC-2152 / IPC-2221 curve)

| Trace | Cu | 10 °C rise | 30 °C rise |
|---|---|---|---|
| 0.3 mm | outer 1 oz | 1.0 A | 1.6 A |
| 0.5 mm | outer 1 oz | 1.45 A | 2.35 A |
| 0.8 mm | outer 1 oz | ~2.0 A | ~3.3 A |
| 1.0 mm | outer 1 oz | 2.4 A | 3.9 A |

Applied: battery feed (BATT_RAW → fuse → FET) routed at 0.8 mm; the
protected rail and the 6 V motor rail are **B.Cu pours** (better than any
trace); motor phases target 0.8 mm with a documented 0.5/0.3 mm fallback in
the densest corridors (N20 6 V stall ≈ 1.6 A is transient — see
TRACE_REPORT.md verdicts). Motor current never routes on 0.5 oz inner
layers. Skin depth at 20 kHz (0.47 mm) ≫ foil thickness — no AC derating.

## 4. Grounding & partitioning

- One unbroken In1 GND plane (solid fill — thermal spokes starve in the TCRT
  hole clusters). No star points; return currents self-partition.
- Placement partitioning: TB6612 + 6 V buck + bulk caps grouped east-mid;
  IR/ADC front-end in the front band ≥ 10 mm away; the module's antenna at
  the rear over its cutout.
- Motor hot loop: TPS54302 → C30 220 µF/16 V → TB6612 VM pins, all within
  ~12 mm; PWM phase currents circulate driver ↔ bulk ↔ plane directly below.
- Every layer-changing signal picks up the plane through adjacent stitching
  (via stitch pass); ADC sense nets are RC-filtered at the divider and read
  through the mux with settle time budgeted in firmware.
- IMU (BNO055) on the centerline, 26 mm from the nearest motor can and ≥8 mm
  from both buck inductors. Magnetometer data is calibration-grade only on
  any motor robot (1 A at 5 mm ≈ Earth field) — the yaw loop uses the gyro.

## 5. Decoupling (per datasheet)

- ESP32-S3-WROOM-1: 10 µF + 100 nF at pin 2, EN 10 k + 1 µF RC (Espressif HDG).
- TB6612: C30 220 µF/16 V alu bulk at VM entry (engineering margin for
  3 A/20 kHz — datasheet minimum is 10 µF) + 10 µF/25 V + 100 nF at the pins,
  100 nF on VCC.
- AP63203: 2×10 µF/25 V in, 2×22 µF out, 100 nF bootstrap, L 4.7 µH.
- TPS54302: 10 µF/25 V + 100 nF in, 2×22 µF/25 V out, 100 nF BOOT, L 4.7 µH
  (SRP4020TA, Isat 3.5 A > 3 A limit).
- BNO055: 100 nF + 10 µF on VDD/VDDIO, 100 nF on the CAP (internal LDO) pin.
- **2S rail rule:** every capacitor on VM_BATT/VM_6V is 16 V/25 V class;
  the 1S-era 6.3–10 V bulk parts are banned from those rails (enforced in
  the schematic's value table).

## 6. Silkscreen / assembly (IPC-7351 / IPC-2610)

- Pin-1 marks outside bodies; cathode bars on diodes; "BATT 2S 8.4V MAX" at
  the battery connector; PWR / MOT labels at the two slides; buttons lettered
  A/B/C/RST.
- Bent-sensor aiming: U-shaped body outlines fully inside the board with a
  gated 3–5 mm edge margin, plus **angle callouts (0° / 45° / 90°) with
  reference + aim rays** at each cluster — silk duplication for hand-mounted
  parts per IPC-2610 practice.
- Board-level silk is gated ≥ 0.2 mm from every F-side pad/mask opening
  (build gate; also required for the DRC 0-warnings policy).

## 7. Antenna cutout (Espressif ESP Hardware Design Guidelines)

Implemented per the guide's sanctioned fallback: the WROOM-1 sits fully on
the board and the base board is **cut away on both sides of the antenna and
below it** — a 20.7 × 6.2 mm U-notch in the rear edge. The antenna tip stays
inside the 100×120 envelope (user requirement: nothing outside the board
except motor shafts). Copper/track keepout ribbon under the module's last
2 mm + the notch itself; the guide's mid-board hollow-out is explicitly
prohibited and avoided. Slot manufacturability: width 20.7 mm ≫ 1 mm
minimum, internal corners receive the fab's ≥ 1 mm mill radius.

## 8. DRC policy

Rev 6 restores every courtyard/hole severity to **error** and targets
0 errors / 0 warnings from KiCad's full DRC (`--severity-warning` included)
— see TEST_REPORT.md / the release notes for the shipped result.
