# Micromouse 4WD drivetrain — Bill of Materials (rev 7)

Scope: everything mechanical for the drivetrain + tyre casting. The PCB
carries its own electronic BOM in the KiCad project
(`pcb/JLCPCB_2layers_simplified/xiao/`); it appears here only as the
chassis it is.

## 3D-printed parts (`Gear/step/`, all support-free)

| # | Part | File | Qty | Material / notes |
|---|------|------|-----|------------------|
| P1 | Motor pod | `motor_pod_x2.step` | 2 | PETG or ABS; prints outboard-face-down |
| P2 | Wheel, keyed | `wheel_printable_keyed_x4.step` | 4 | hub-face-down; keying holes are the casting gates |
| P3 | Gear 40T M0.5, D3 bore + bolt circle | `gear_40T_m0p5_D3bore_WHEEL.step` | 4 | spec is POM (cut/moulded); printable for bring-up |
| P4 | Pinion 19T M0.5, D3 bore | `gear_19T_m0p5_D3bore_MOTOR.step` | 2 | same as P3 |
| P5 | Tyre mould cup | `mold_cup_x1.step` | 1 | prints upright; reusable |
| P6 | Tyre mould plug | `mold_plug_x1.step` | 1 | print plate-down; reusable |

## Purchased hardware

| # | Item | Spec | Qty | Where used |
|---|------|------|-----|------------|
| H1 | N20 gearmotor with encoder | 3 mm D-shaft; stock (~1500 rpm out) for 1 m/s, high-RPM (~4500 rpm class) for 3 m/s | 2 | one per side (Robu.in class part) |
| H2 | Flanged bearing F683ZZ | 3×7×3, flange Ø8.2×0.5 | 8 | two per axle, press-fit in pod bosses |
| H3 | Steel D-shaft | Ø3.0, flat to 2.5, cut to 35.1 mm | 4 | live axles (`axle_D3_L35p1` is the cut drawing) |
| H4 | M2×12 + M2 nut + M2 washer | DIN 912/934/125 | 12 ea | gear-to-wheel positive lock, 3 per wheel |
| H5 | M3×8 countersunk | DIN 7991 | 4 | pods to PCB from below, thread-forming into pads |
| H6 | M3×16 socket-head | DIN 912 | 3 | tyre-mould clamp, thread-forming into cup bosses |
| H7 | Rubber band | small, ~30–40 mm loop | 2 | motor retention over the can (pod ears) |
| H8 | Two-part RTV-2 silicone | Shore A 20–30 (NOT one-part sealant — never cures enclosed) | ~20 ml per wheel set | tyres: 2.4 ml cast + ~1.3 ml sprue waste each |
| H9 | Micromouse PCB (xiao 2-layer) | with corner notches per `dxf/board_notch_required.dxf` | 1 | the chassis |

No other fasteners exist: gears, axles and wheels drive on D-flats;
bearings press in; the M2s are retention on top of the wheel press fit,
not the torque path.

## Consumables / tools

- M2.5 hex key (H6), M2 hex key (H5 csk), 1.5 mm hex key (H4)
- Pin or Ø2 drill to clear silicone from the keying holes if recast
- Optional release agent for the mould plug: petroleum jelly, trace
- Tape for race tyres (competition grip), applied fresh

## Assembly order

Interactive guide: the assembly artifact's Step buttons walk one group
per press. Sequence: pods on bare board (M3×8 from below) → motors in
(slide inboard, then into the wall register) → pinions on shafts →
bearings pressed (flange leads) → gear+wheel pairs bolted (M2) →
axles through → wheels pressed on.
