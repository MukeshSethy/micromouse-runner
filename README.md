# Micromouse Runner

A competition-style micromouse robot on a custom **100 × 120 mm, 4-layer**
KiCad 10 PCB: ESP32-S3 module doing all control + wireless telemetry, bare-die
motor driver, research-verified sensor geometry, and a fully script-generated,
fully autorouted design — ERC 0, DRC 0 errors, 0 unconnected as shipped.

![PCB top](images/render_top.png)

## The board (rev 5)

| Subsystem | Part | Notes |
|---|---|---|
| Controller | ESP32-S3-WROOM-1 (bare module, dual-core FreeRTOS) | Rear placement, antenna overhangs the rear edge (Espressif-preferred keep-out) |
| Motor driver | TB6612FNG bare SSOP-24 | Mid-band, between the wheel slots |
| Motors | 2× N20 gearmotors + quadrature encoders (PCNT hardware decode) | JST-PH; project-local exact footprint + 3D model |
| Motor mounting | 2× Ø3.2 mm holes per motor, 18.0 mm c-c | Fits the printable UKMARSBot Pololu-pattern bracket (below) |
| Wall sensors | 6× SFH 4550 + PT334-6B pairs: front 10° toe-out, diagonal 45°, side 75° | Bent flat over the board (silk outlines mark each body); holes ~10 mm inboard so the bent tips stay inside the outline |
| Line sensors | 8× Vishay TCRT5000, 9.525 mm QTR pitch, bottom face (~2.4 mm off the floor = datasheet-optimal) | Read through a CD74HC4067 mux; wall sensors go **direct to ADC1** |
| Indicators | Per-sensor LEDs on top for all 8 line + 6 wall channels | Wall LED ON = wall seen |
| User I/O | Buttons **A / B / C** (+ RST) lettered on silk, rear edge; power slide switch | A doubles as BOOT; switch gates the regulator EN (soft power) |
| USB | USB-C at the rear (flash/debug), ESD-protected, VBUS cable-detect divider on IO37 | Plus 1×6 JTAG header |
| Power | 1S LiPo → TPS63001 buck-boost 3V3 | Fuse, reverse-polarity P-FET, VBAT sense divider |

Drive wheels run in open edge notches (wheel/tyre width unconstrained);
front castor hole at the nose. Chamfered nose for the diagonal sensor pair.

### 3D-printable motor bracket

Print two of the UKMARSBot **Pololu-pattern N20 bracket** (MIT licence):
[`pololu-gear-motor-bracket-standard.stl`](https://raw.githubusercontent.com/ukmars/ukmarsbot/master/mechanical/pololu-gear-motor-bracket-standard.stl)
(from [github.com/ukmars/ukmarsbot](https://github.com/ukmars/ukmarsbot),
`mechanical/`). The board is drilled for it: Ø3.2 mm NPTH pairs at 18.0 mm
centres — (17.25, 75)/(17.25, 93) and (82.75, 75)/(82.75, 93), axle at y = 84.
M2/M2.5/M3 screws from the underside into nuts captured by the bracket.

## Design rules & tooling

- 0.3 mm clearance against **every through-hole pin** on every verification
  path (hand-solder safety, structural in the router); SMD fields may relax
  to 0.16 mm where physics demands it.
- In1 = GND plane, In2 = 3V3 plane, partial VM battery pour on B.Cu; every
  SMD pour pad stitched by via + verified stub.
- Routed to **zero unrouted edges** by the project's own 4-layer A*
  autorouter (`route_loaded.py`): jailed-first ordering with immediate retry
  ladders, hand-computed bridges for the USB-C pad field, wide
  "verify-proof" retry rungs, and a convergent DRC heal loop
  (`heal_all.py`). The war stories live in `pcb/PROJECT_NOTES.md`.

## Repository layout

```
micromouse-runner/
├── pcb/            KiCad hardware design
│   ├── micromouse-pcb.kicad_sch / .kicad_pcb / .kicad_pro
│   ├── netlist.net
│   ├── CONNECTIONS.md      every net, every pin, and why (generated, coverage-enforced)
│   ├── PROJECT_NOTES.md    full design decision log, research, and known issues
│   ├── n20.pretty/         hand-authored exact N20 motor footprint + 3D model
│   └── tools/              generators (schematic + PCB are script-produced, so auditable)
│       ├── gen_sch.py / build_schematic.py     schematic generator
│       ├── gen_pcb.py / build_pcb.py           placement + in-house N-layer A* autorouter
│       ├── board_geom.py                       single source of mechanical truth
│       ├── route_loaded.py                     routing pipeline (run build_pcb.py first)
│       ├── heal_all.py                         convergent DRC-unconnected healer
│       └── gen_connections.py / verify_netlist.py   docs + connectivity checks
├── fw/             sample firmware + host simulation
│   ├── micromouse/     pins.h (netlist-gated) + control_core + .ino (line following)
│   ├── sim/            gcc host sim of the EXACT control core (scenarios asserted)
│   └── check_pins.py   gate: every firmware pin verified against the netlist
├── simulation/     maze-solving / motion simulation — planned
└── images/         renders
```

## Verification

- `pcb/TEST_REPORT.md` — 28 analytical circuit tests computed from the
  netlist (operating points + datasheet margins for power, flashing, straps,
  JTAG, buttons, motors, encoders, every IR chain, mux), adversarially
  audited by independent datasheet re-derivation. Coverage metrics included.
- `pcb/TRACE_REPORT.md` — trace-level copper analysis of the routed board:
  per-net path resistance (every segment/via walked), IR drops at operating
  currents, via ampacity, USB pair skew.
- `fw/sim/` — the shipped control core runs against board-derived physics;
  the sim caught two real control bugs before hardware (weak steering, a
  D-term spike on line loss). All scenarios pass.
- `pcb/CONNECTIONS.md` — the per-trace justification document: every net,
  every pin, and why (generated, coverage-enforced).

## Ordering / fabrication

- `pcb/BOM.csv` — 42 line items, every row with a verified MPN (packages and
  FET pinouts checked against datasheets + distributor stock).
  Optos are chosen for Indian marketplace availability: TCRT5000 line
  sensors (robu.in / ElectronicsComp / Robocraze) and PT334-6B wall
  phototransistors (hubtronics / rarecomponents; robu's black-lens pack).
- `pcb/tools/export_fab.py` regenerates `pcb/fab/`: gerbers (11 layers),
  Excellon drill (bracket/castor NPTH tools asserted present), placement
  CSV, and a fit-check STEP that loads **every** 3D model (project-local
  box-true models for the N20 motors, TPS63001 and the power inductor).

## Build / regenerate

The PCB tooling runs from `pcb/` using the KiCad-bundled Python (`pcbnew`);
see `pcb/PROJECT_NOTES.md` for exact commands and the many hard-won
KiCad-format notes. Regeneration order: `build_schematic.py` → export
netlist → `build_pcb.py` → `route_loaded.py` → `heal_all.py` →
`export_fab.py` (gates: `verify_netlist.py`, ERC, DRC, drill/STEP/BOM
assertions run inside the chain).

## Status

Rev 5 ships fully routed and verified: **ERC 0 · DRC 0 violations · 0
unconnected · 0 schematic-parity issues** — ~1240 tracks, ~310 vias.
Next: firmware bring-up.
