# Firmware & Simulation

Single controller: the board's **ESP32-S3-WROOM-1** (U3) does everything —
500 Hz control loop, sensing, motor drive, WiFi telemetry. (The old
STM32+Nano split described here before rev 4 is long gone.)

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
3. Bootloader: **hold A** (IO0/BOOT), **tap RST** (EN pulses through the
   10 ms R11/C9 RC), release A → ROM download mode.
4. `esptool.py --chip esp32s3 write_flash 0x0 firmware.bin` (or Arduino IDE
   "ESP32S3 Dev Module", USB-CDC on boot enabled).
5. Reset (RST) into the app.

JTAG debugging: the 1×6 header (J8) carries TMS/TCK/TDO/TDI at 3V3.
