# Trace-Level Copper Analysis -- micromouse-pcb rev 6

Computed from the routed board file (every segment/via walked; 1 oz Cu
0.492 mOhm/sq, 0.5 mOhm per via). Companion to TEST_REPORT.md (circuit
level) and CONNECTIONS.md (per-net rationale).

## Power and signal path resistance

| Net | purpose | len (mm) | widths (mm) | vias | path R (mOhm) | I (A) | drop (mV) | verdict |
|---|---|---|---|---|---|---|---|---|
| `BATT_RAW` | 2S battery feed: connector to fuse | 75 | [0.8] | 1 | 45.8 | 2.6 | 119.2 | REVIEW |
| `Net-(Q1-D)` | fuse to reverse-protection FET | 13 | [0.8] | 0 | 8.3 | 2.6 | 21.5 | OK |
| `MOTA_P` | motor A + (6V stall) | 44 | [0.5] | 2 | 43.0 | 1.6 | 68.8 | REVIEW |
| `MOTA_N` | motor A - (6V stall) | 30 | [0.25, 0.5] | 1 | 55.1 | 1.6 | 88.2 | REVIEW |
| `MOTB_P` | motor B + (6V stall) | 39 | [0.5] | 1 | 27.7 | 1.6 | 44.3 | OK |
| `MOTB_N` | motor B - (6V stall) | 36 | [0.25, 0.3] | 1 | 49.1 | 1.6 | 78.6 | REVIEW |
| `EMIT_LINE_K` | line emitter bank return | 124 | [0.3] | 1 | 117.9 | 0.12 | 14.2 | OK |
| `EMIT_FRONT_K` | front wall emitter bank return | 84 | [0.3] | 1 | 54.8 | 0.09 | 4.9 | OK |
| `EMIT_DIAG_K` | diag wall emitter bank return | 72 | [0.3] | 1 | 59.5 | 0.09 | 5.4 | OK |
| `EMIT_SIDE_K` | side wall emitter bank return | 75 | [0.3] | 0 | 45.9 | 0.09 | 4.1 | OK |
| `PWR_EN` | soft-switch EN (signal) | 128 | [0.25, 0.3] | 6 | 159.4 | 5e-06 | 0.0 | OK |
| `MOT_EN` | motor-rail EN (signal) | 110 | [0.3] | 5 | 157.2 | 5e-06 | 0.0 | OK |
| `IMU_SDA` | I2C data (400kHz, 4.7k pull-up) | 52 | [0.25, 0.3] | 4 | 85.7 | 0.0007 | 0.1 | OK |
| `MUX_SENSE` | line ADC (signal, 47k source) | 88 | [0.3] | 4 | 145.2 | 0.0001 | 0.0 | OK |

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
| `GND` | 73 | 95 | In1 solid plane + both outer faces; plane R << trace paths |
| `PLUS3V3` | 73 | 175 | In2 solid plane; plane R << trace paths |
| `VM_BATT` | 13 | 83 | B.Cu pour, battery -> both buck inputs; plane R << trace paths |
| `VM_6V` | 7 | 18 | B.Cu pour, 6V buck -> TB6612/motors; plane R << trace paths |

## USB 2.0 full-speed differential pair

- D+ routed length 31.0 mm, D- 25.2 mm -> skew 5.8 mm (38 ps). Full-speed tolerance is ~4 ns -> margin > 105x. Impedance is uncontrolled (FS allows it).

## Review notes

- BATT_RAW: only 1 via(s) for 2.6 A (want >= 2)
- MOTA_N: only 1 via(s) for 1.6 A (want >= 2)
- MOTB_P: only 1 via(s) for 1.6 A (want >= 2)
- MOTB_N: only 1 via(s) for 1.6 A (want >= 2)
