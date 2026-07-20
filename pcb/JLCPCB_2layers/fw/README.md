# Firmware & Simulation

Single controller: the board's **ESP32-S3-WROOM-1** (U3) does everything —
500 Hz control loop, sensing, motor drive, WiFi telemetry. (The old
STM32+Nano split described here before rev 4 is long gone.)

Rev 7.2 additions:
- **Buzzer on IO46** (`PIN_BUZZER`, LEDC 4 kHz): `beep(ms, n)`. Chirps:
  2×60 ms = boot ready · 40 ms = RUN · 120 ms = STOP · 3×250 ms = LOW
  BATTERY cutoff · 2×80 ms = stall watchdog tripped · **4×60 ms = IMU
  self-test failure** (bot still runs, yaw degraded to 0).
- **IMU functional self-test at boot**: CHIP_ID must read 0xA0 (with a
  cold-boot retry window), the BNO055's power-on self-test result (reg 0x36)
  must report ACC/MAG/GYR/MCU all-pass, and after NDOF is selected
  SYS_STATUS/SYS_ERR must reach "fusion running"/0 — otherwise the failure
  is printed, the 4-chirp sounds, and the robot runs without gyro damping.
  The board-side IMU wiring (I2C topology, pull-ups, straps, reset lines,
  CAP bypass, INT) is gated by `sim_preflight.py` sections I1–I6.
- **Balance plug (J9) is OPTIONAL**: unplugged, `BAT_MID_SENSE` reads ~0 V
  (board divider drains it) → firmware logs it and guards on the 6.6 V pack
  floor alone; plugged, per-cell 3.3 V floors are enforced too.
- **Motors plug straight in**: J5/J6 are JST ZH in the robu GA12-N20 cable
  order (M1, VCC, C1, C2, GND, M2) — meter-check VCC/GND (pins 2/5) against
  the delivered cable once, before the first plug-in. 600 ticks/rev
  (3 PPR × 4 × 50:1); motors always see the regulated 6 V rail, never the
  8.4 V pack.

```
fw/
├── micromouse/
│   ├── pins.h            every GPIO assignment; GATED against the netlist
│   ├── control_core.c/.h pure control logic (no ESP32 deps — the same file
│   │                     compiles on the host for simulation)
│   └── micromouse.ino    Arduino-ESP32 app: mux scan, wall ADC, IN/IN motor
│                         PWM (LEDC), BNO055 fusion, modes on buttons A/B/C
├── check_pins.py         gate: pins.h GPIO -> WROOM pad -> netlist net —
│                         a THREE-way match for all 29 firmware pins
├── sim_flash.py          USB-C FLASH-PATH simulation (netlist-driven): CC
│                         pulldowns, ESD'd D± to the module, BOOT/RST straps,
│                         EN RC timing, then a virtual esptool session
└── sim/
    ├── sim_linefollow.c  control-loop sim: the SHIPPED control core against
    │                     board-derived physics (5 scenarios, asserted)
    └── sim_hw.c          sensor/actuator CHAIN sim: wall optics (0/45/90°),
                          line array + estimator, motors + encoders, BNO055
                          yaw, corridor-centring demo (asserted)
```

## Build & run the simulations (host, gcc)

```bash
gcc -O2 -I fw/micromouse -o sim_lf fw/sim/sim_linefollow.c fw/micromouse/control_core.c -lm && ./sim_lf
gcc -O2 -I fw/micromouse -o sim_hw fw/sim/sim_hw.c      fw/micromouse/control_core.c -lm && ./sim_hw
python fw/sim_flash.py        # flash-path: ALL STAGES PASS expected
python fw/check_pins.py       # pin gate:   29/29 expected
```

All three simulations exit non-zero on any failed assertion; they are part of
the verification battery. The hw-chain sim already caught a real firmware
bug: the line estimator's factory `cal_min` default (300) left ~10 %
"line-ness" on every idle channel with the board's true 0.4 V white floor,
compressing reported positions ~0.55× — fixed with an idle-channel deadband
in `control_core.c`.

## Flashing over the board's USB-C (verified by `sim_flash.py`)

1. **Battery on**: connect the 2S pack, switch **PWR (SW5)** ON. (VBUS
   deliberately does not power the board — it is sense-only.)
2. Plug USB-C. The host sees the CC 5.1 k pulldowns and enumerates the
   S3's **native USB-Serial-JTAG** (VID 303A, PID 1001) — no UART bridge.
3. **Normally: no buttons.** The S3's USB-Serial-JTAG lets esptool/Arduino
   enter download mode and reset back into the app automatically over USB —
   a blank chip boots into it too, so even the first flash is button-free.
4. `esptool.py --chip esp32s3 write_flash 0x0 firmware.bin` (or Arduino IDE
   "ESP32S3 Dev Module", USB-CDC on boot enabled).
5. **Recovery only** (app crashes early, reconfigures USB/GPIO19-20, deep
   sleeps, or the port never appears): **hold A** (IO0/BOOT), **tap RST**
   (EN pulses through the 10 ms R11/C9 RC), release A → forced ROM download
   mode; flash, then tap RST once to start the app.

JTAG debugging: the 1×6 header (J8) carries TMS/TCK/TDO/TDI at 3V3.

## Power / switch procedure (SW5 = PWR ALL, SW6 = PWR MOTORS)

The two slide switches gate the rails independently: **SW5** enables both
regulators' logic path (3V3 + the 6 V controller EN chain); **SW6** adds the
6 V motor rail on top (motors can never run without BOTH on).

| Activity | Battery | SW5 (PWR) | SW6 (MOT) | Why |
|---|---|---|---|---|
| **Flashing** | connected | **ON** | **OFF** | VBUS is sense-only — the ESP32 must be battery-powered to enumerate. Motors off = no surprise motion if the app starts driving after reset. |
| **Sensor testing** (walls/line/IMU/telemetry) | connected | **ON** | **OFF** | Whole logic domain (sensors, mux, IMU, WiFi, indicators) runs on 3V3; the 6 V rail is not needed and wheels stay safely dead. |
| **Motor testing / driving** | connected | **ON** | **ON** | Both rails live. Put the robot on a stand first — the app drives on mode-select. |
| **Storage / transport** | disconnect | OFF | OFF | The reverse-FET path has µA-level leakage, but a stored LiPo should always be physically disconnected. |
| **Emergency stop** | — | — | **OFF** | SW6 is the hardware motor kill: it drops the 6 V rail regardless of firmware state (the TB6612 INs also idle low). |

Safe bring-up order for a fresh board: SW5+SW6 OFF → connect battery →
SW5 ON → check 3V3 rail / smoke-test → flash → sensor tests → *then*
SW6 ON with wheels off the ground.
