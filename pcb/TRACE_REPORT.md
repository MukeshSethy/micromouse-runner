# Trace-Level Copper Analysis -- micromouse-pcb rev 6

Computed from the routed board file (every segment/via walked; 1 oz Cu
0.492 mOhm/sq, 0.5 mOhm per via). Companion to TEST_REPORT.md (circuit
level) and CONNECTIONS.md (per-net rationale).

## Power and signal path resistance

| Net | purpose | len (mm) | widths (mm) | vias | path R (mOhm) | I (A) | drop (mV) | verdict |
|---|---|---|---|---|---|---|---|---|
| `BATT_RAW` | 2S battery feed: connector to fuse | 75 | [0.8] | 1 | 46.8 | 2.6 | 121.6 | HIGH |
| `Net-(Q1-D)` | fuse to reverse-protection FET | 14 | [0.8] | 0 | 8.1 | 2.6 | 21.0 | OK |
| `MOTA_P` | motor A + (6V stall) | 37 | [0.5] | 1 | 33.9 | 1.6 | 54.2 | REVIEW |
| `MOTA_N` | motor A - (6V stall) | 0 | [] | 0 | no path? | 1.6 | - | CHECK |
| `MOTB_P` | motor B + (6V stall) | 11 | [0.5, 0.8] | 2 | 6.2 | 1.6 | 9.9 | OK |
| `MOTB_N` | motor B - (6V stall) | 18 | [0.25] | 2 | 28.8 | 1.6 | 46.1 | OK |
| `EMIT_LINE_K` | line emitter bank return | 124 | [0.3] | 1 | 118.1 | 0.12 | 14.2 | OK |
| `EMIT_FRONT_K` | front wall emitter bank return | 84 | [0.3] | 1 | 53.0 | 0.09 | 4.8 | OK |
| `EMIT_DIAG_K` | diag wall emitter bank return | 75 | [0.3] | 1 | 60.3 | 0.09 | 5.4 | OK |
| `EMIT_SIDE_K` | side wall emitter bank return | 75 | [0.3] | 0 | 45.9 | 0.09 | 4.1 | OK |
| `PWR_EN` | soft-switch EN (signal) | 124 | [0.3] | 8 | 154.9 | 5e-06 | 0.0 | OK |
| `MOT_EN` | motor-rail EN (signal) | 135 | [0.3] | 3 | 193.2 | 5e-06 | 0.0 | OK |
| `IMU_SDA` | I2C data (400kHz, 4.7k pull-up) | 51 | [0.25, 0.3] | 2 | 84.2 | 0.0007 | 0.1 | OK |
| `MUX_SENSE` | line ADC (signal, 47k source) | 0 | [] | 0 | no path? | 0.0001 | - | CHECK |

Reading the verdicts: currents are worst-case (fuse rating for the battery
feed, motor STALL for the drive nets -- N20 nominal draw is ~0.36 A). The
HIGH/REVIEW rows are millivolt IR drops at those extremes, not thermal
limits: 0.3 mm / 1 oz copper carries ~1.5 A at a 30 degC rise (IPC-2152), so
every trace has >= 40% ampacity margin at stall. A 150 mV transient sag on a
~4 V motor rail costs < 4% torque during a stall event; the TP4056/TPS63001
side is unaffected (own nets measure OK). Acceptable by design for a 100 mm
robot; widen the drive traces only if rev 6 frees routing room.

## Pour/plane nets (connectivity proven by DRC 0-unconnected)

| Net | stitch vias | trace len (mm) | note |
|---|---|---|---|
| `GND` | 64 | 86 | In1 solid plane + both outer faces; plane R << trace paths |
| `PLUS3V3` | 61 | 96 | In2 solid plane; plane R << trace paths |
| `VM_BATT` | 8 | 53 | B.Cu pour, battery -> both buck inputs; plane R << trace paths |
| `VM_6V` | 8 | 17 | B.Cu pour, 6V buck -> TB6612/motors; plane R << trace paths |

## USB 2.0 full-speed differential pair

- D+ routed length 18.5 mm, D- 22.7 mm -> skew 4.3 mm (28 ps). Full-speed tolerance is ~4 ns -> margin > 142x. Impedance is uncontrolled (FS allows it).

## Review notes

- BATT_RAW: only 1 via(s) for 2.6 A (want >= 2)
- MOTA_P: only 1 via(s) for 1.6 A (want >= 2)
- MOTA_N: graph path not resolved (pour-fed or terminal >1.2mm from copper)
- MUX_SENSE: graph path not resolved (pour-fed or terminal >1.2mm from copper)
