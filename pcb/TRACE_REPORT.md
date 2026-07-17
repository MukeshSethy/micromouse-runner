# Trace-Level Copper Analysis -- micromouse-pcb rev 5.3

Computed from the routed board file (every segment/via walked; 1 oz Cu
0.492 mOhm/sq, 0.5 mOhm per via). Companion to TEST_REPORT.md (circuit
level) and CONNECTIONS.md (per-net rationale).

## Power and signal path resistance

| Net | purpose | len (mm) | widths (mm) | vias | path R (mOhm) | I (A) | drop (mV) | verdict |
|---|---|---|---|---|---|---|---|---|
| `Net-(J1-Pin_1)` | battery feed: connector to fuse | 81 | [0.5] | 2 | 79.6 | 2.4 | 191.1 | HIGH |
| `Net-(Q1-D)` | fuse to reverse-protection FET | 21 | [0.5] | 0 | 21.1 | 2.4 | 50.7 | REVIEW |
| `MOTA_P` | motor A + (stall) | 93 | [0.25, 0.3] | 3 | 145.3 | 1.05 | 152.6 | HIGH |
| `MOTA_N` | motor A - (stall) | 97 | [0.25, 0.3] | 1 | 151.5 | 1.05 | 159.1 | HIGH |
| `MOTB_P` | motor B + (stall) | 52 | [0.25, 0.3] | 2 | 80.5 | 1.05 | 84.6 | REVIEW |
| `MOTB_N` | motor B - (stall) | 113 | [0.25, 0.3] | 3 | 85.5 | 1.05 | 89.8 | REVIEW |
| `EMIT_LINE_K` | line emitter bank return | 130 | [0.3] | 1 | 126.4 | 0.12 | 15.2 | OK |
| `EMIT_FRONT_K` | front wall emitter bank return | 89 | [0.3] | 0 | 61.2 | 0.09 | 5.5 | OK |
| `EMIT_DIAG_K` | diag wall emitter bank return | 93 | [0.3] | 1 | 77.4 | 0.09 | 7.0 | OK |
| `EMIT_SIDE_K` | side wall emitter bank return | 86 | [0.3] | 1 | 55.6 | 0.09 | 5.0 | OK |
| `PWR_EN` | soft-switch EN (signal) | 110 | [0.25, 0.3] | 2 | 156.1 | 5e-06 | 0.0 | OK |
| `MUX_SENSE` | line ADC (signal, 47k source) | 106 | [0.25, 0.3] | 3 | 171.0 | 0.0001 | 0.0 | OK |

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
| `GND` | 59 | 83 | In1 solid plane + both outer faces; plane R << trace paths |
| `PLUS3V3` | 60 | 81 | In2 solid plane; plane R << trace paths |
| `VM_BATT` | 13 | 42 | partial B.Cu pour over the power/drive region; plane R << trace paths |

## USB 2.0 full-speed differential pair

- D+ routed length 27.6 mm, D- 21.3 mm -> skew 6.2 mm (41 ps). Full-speed tolerance is ~4 ns -> margin > 97x. Impedance is uncontrolled (FS allows it).
