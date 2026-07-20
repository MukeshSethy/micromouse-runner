# THT Variant — engineering decisions

## 1. Controller: socketed ESP32-S3-DevKitC-1-N8R2
- The WROOM module is SMD-only; the DevKit IS the THT form of the same chip
  (same N8R2 memory config → IO35-37 usable, same fw).
- Two PPTC221LFBN-RC 22-pos sockets; DevKit antenna overhangs the rear —
  keep the copper keepout under the antenna end, but the PCB antenna NOTCH
  of the SMD board is no longer needed (antenna sits ~10 mm above board).
- **USB moves to the DevKit**: its on-board USB-C exposes the S3's native
  USB-Serial-JTAG — identical flashing/console flow to rev 7.2 (still
  battery-powered logic; the DevKit's 5V-USB rail must NOT back-feed:
  power the DevKit from our 3V3 via the 3V3 pin, never both USB+battery
  with motors on — same procedure table as rev 7.2, documented at layout).
- Deleted with it: J7, U6 (ESD), R12/R56 (CC), R67/R68 (VBUS divider) —
  the biggest routing pocket of the SMD board disappears.

## 2. Motor driver: TB6612FNG breakout on headers (recommended)
- No modern DIP H-bridge exists. The classic DIP parts fail this design:
  - SN754410NE / L293D: VCC1 (logic) requires **4.5-5.5 V** — this board
    has no 5V rail. Adding one (LM2596-5.0) plus level concerns = worse.
  - L298N (Multiwatt THT): logic VSS accepts 6 V, but total saturation drop
    of 1.4-3 V robs the 6 V rail — motors would see ~3-4.6 V. Rejected.
- The breakout keeps TB6612 (IN/IN PWM, 0.23 A robu stall = 20% of one
  channel) and the whole rev-7.2 firmware unchanged. Two 1×8 headers.

## 3. IMU: GY-BNO055 breakout on a 1×8 header
- BNO055 is LGA-only. The breakout carries the same 0x28 I2C interface,
  pull-ups, and INT pin; `imu_selftest()` works unchanged.
- Mount at the board center-line, connector row inboard (mass centered).

## 4. Analog mux: DIP
- First choice: **CD74HC4067E** (DIP-24, drop-in logical equivalent of the
  SMD 4067 — same select lines S0-S3, same firmware). Lion's catalog page
  404s on slashless slugs; it is a jellybean part — let Lion procure, or:
- Fallback: **2× CD74HC4051E** (DIP-16 8:1). S0-S2 shared; S3 selects the
  bank: S3 → bank-B enable directly, S3 → 2N7000 inverter → bank-A enable.
  Costs one extra 2N7000 + 10k. Firmware: identical channel numbering if
  bank-B carries channels 8-15.

## 5. Power tree (same architecture, THT silicon)
- LM2596T-3.3 (logic) + LM2596T-ADJ set to 6.00 V (motors; FB divider
  100k/... computed at layout). Both 150 kHz: each needs 33 µH
  (RLB0914-330KL), a 3 A schottky (1N5822), and 220 µF output.
- 40 V-rated TO-220s: the 8.4 V pack is nothing; thermally lazy at our
  currents — no heatsinks.
- IRF9540N reverse-polarity P-FET (Vgs ±20 V — 2S-safe like rev 7.2).
- RUEF300 radial PPTC (3 A hold / 6 A trip): sim_power's stall envelope
  (4.3 A transient) sits between hold and trip exactly like rev 7.1's
  MINISMDC350F — same protection philosophy.
- Motors still see the **regulated 6.00 V** rail: the 8.4 V-pack question
  stays closed by architecture in this variant too.

## 6. What carries over UNCHANGED
- Sensor geometry (0°/45°/90° pairs + TCRT line array) — all THT already.
- All connectors incl. rev-7.2 ZH direct-plug motors and the XT60/XH
  parallel battery inputs with ONE PACK ONLY rule.
- The verification methodology: every gate in `pcb/tools/` + `fw/` applies;
  the THT layout session must end at verify_drc 0/0 + full battery, same
  as rev 7.2.

## 7. Known deltas / accepted losses
- Piezo buzzer (PS1240) ≈ 70 dB vs 95+ dB magnetic. Acceptable for status
  chirps; a THT magnetic transducer can substitute later if Lion lists one.
- No USB ESD array on the robot (the DevKit has its own protection); field
  care: touch chassis ground before plugging in dry weather.
- Mass/height: DevKit + radial parts raise CoG; this variant is a builder's
  robot, not a podium chaser.

## 8. Layout session TODO (the remaining work)
1. New `tht/` KiCad project reusing `board_geom.py` outline (antenna notch
   optional now) — evaluate 2-layer (THT density allows it; cheaper fab).
2. Placement: DevKit socket over the old module+USB pocket; TO-220s along
   the left waist; DIPs mid-board; breakouts on the center-line.
3. The free-rect placement scanner + optical-corridor keepouts from
   rev 7.2 (memory: hole-aware, both faces, true outline polygon).
4. Route (the gen_pcb harness), verify_drc 0/0, full battery, export_fab,
   production folder.
