# Micromouse THT Variant — self-solderable edition (project charter)

A **separate project** from the rev-7.2 SMD board: the same robot, redesigned
so that **every board-mounted part is through-hole**. You order the bare PCB
from Lion Circuits and solder everything yourself with a basic iron — no
assembly service, no reflow, no SMD tweezers.

> **Status: engineering package complete (BOM + architecture verified against
> Lion stock 2026-07-20). Board layout/routing is the next work session —
> this folder is the single source it will be built from.**

## Why this exists
- Bare-PCB fab is the only Lion cost; assembly labor is yours.
- Every part is hand-replaceable — great for a learning build or repair.
- Trade-offs accepted: bigger/taller/heavier than the SMD board (worse
  competition dynamics), piezo buzzer instead of magnetic, no on-board USB
  ESD array (see DESIGN.md).

## The three architecture moves (modern silicon has no DIP package)
1. **Controller = socketed ESP32-S3-DevKitC-1-N8R2** (Lion: In Stock) on two
   22-pin female headers. Bonus: the DevKit brings its **own USB-C** — the
   whole USB-C/ESD/VBUS-divider cluster (J7, U6, R12, R56, R67, R68) is
   **deleted**; you flash through the DevKit like any dev board.
2. **Motor driver = TB6612FNG breakout module** on female headers (robu
   ~₹150) — keeps the rev-7.2 IN/IN firmware and the regulated-6V motor
   architecture unchanged. (All-Lion DIP alternative SN754410NE exists but
   needs a 5V logic rail and is NOT recommended — analysis in DESIGN.md.)
3. **IMU = GY-BNO055 breakout** on a 1×8 female header (breakout from robu;
   same I2C address/firmware).

Everything else substitutes 1:1 THT: LM2596 TO-220 bucks, DIP muxes, TO-92
transistors, axial resistors, radial caps, 3mm LEDs, radial PPTC — the full
map with Lion stock status is `BOM-THT.csv`, decisions in `DESIGN.md`,
ordering flow in `ORDERING.md`.

## Firmware
Identical `fw/` tree. Only `pins.h` gets a THT-variant overlay (DevKit pin
mapping + the mux bank-enable line) once the board exists.
