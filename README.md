# Micromouse PCB

A full-size micromouse robot main/carrier PCB, designed from scratch in KiCad 10.
The board is a "carrier" that hosts socketed plug-in modules plus onboard sensor,
power, and motor-drive circuitry.

![PCB top](images/pcb_render.png)

## What's on the board

| Subsystem | Part | Mounting |
|---|---|---|
| MCU | STM32 NUCLEO-G431KB (Cortex-M4F) | Socketed (Nano-form 2×15 headers) |
| Wireless | Arduino Nano ESP32 (ESP32-S3) | Socketed |
| Motor driver | TB6612FNG breakout | Socketed (2× 1×8) |
| Motors | 2× N20 gearmotors + quadrature encoders | JST-PH connectors |
| Wall sensors | 6× SFH4550 / SFH309 IR pairs | THT, bent-lead (top) |
| Line sensors | 8× SMD IR pairs (QTR-8A style) | SMD, bottom face |
| Sensor readout | 2× HEF4067 16-ch analog mux/demux | one ADC pin reads all 14 sensors |
| Power | 2S LiPo → AP63203 buck → 3V3 | reverse-polarity P-FET, fuse, per-cell sense |

## Repository layout

```
micromouse-runner/
├── pcb/            KiCad hardware design (this is the finished part)
│   ├── micromouse-pcb.kicad_sch / .kicad_pcb / .kicad_pro
│   ├── netlist.net
│   ├── CONNECTIONS.md      every net, every pin, and why (generated, coverage-enforced)
│   ├── PROJECT_NOTES.md    full design decision log, research, and known issues
│   └── tools/              generators (schematic + PCB are script-produced, so auditable)
│       ├── gen_sch.py / build_schematic.py     schematic generator
│       ├── gen_pcb.py / build_pcb.py           placement + in-house autorouter
│       ├── finalize.py / route_loaded.py       in-place ops that preserve manual edits
│       └── gen_connections.py / verify_netlist.py   docs + connectivity checks
├── fw/             firmware for the STM32 (control) and ESP32 (telemetry) — planned
├── simulation/     maze-solving / motion simulation — planned
└── images/         renders and photos
```

## Build / regenerate

The PCB tooling runs from `pcb/` using the KiCad-bundled Python (`pcbnew`) and
msys Python; the scripts reference paths under `pcb/`. See `pcb/PROJECT_NOTES.md`
for exact commands and the many hard-won KiCad-format notes.

## Status / remaining work

Routed (in-house router, ~0.3mm clearance so no trace runs between through-hole
pins for hand-solder safety); DRC-clean apart from a few dangling stubs. Finishing
work: fill the GND pour in the GUI (one keypress), complete ~24 remaining traces
(PLUS3V3 web + a few sensor/control lines), and add module 3D `.step` models for a
full 3D render. See `PROJECT_NOTES.md` for the honest open-issues list.
