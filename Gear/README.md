# Micromouse 4WD 2.27:1 Drivetrain — Gears, Axles and Mounting Layout

Rev 4, 2026-08-10. Everything here is generated. Run `python generate_drivetrain.py`
to rebuild every STEP and DXF from `config.py`, then `make_schematic.py`,
`check_interference.py` and `check_printability.py` to re-verify.

**Nothing in this drivetrain is guessed.** Motor and board geometry are imported from the
PCB project, not re-modelled. Motor position, axle line and deck mounting are read off
`pcb/JLCPCB_2layers_simplified/xiao/design/micromouse-pcb-simplified.kicad_pcb`
(2-layer XIAO-nRF52840-Plus, no line sensor, 100 × 120 mm). Values tagged **PCB-DERIVED**
in `config.py` come from that file and must not be hand-edited.

| | |
|---|---|
| Train | **22T → 50T**, 3 gears per side, module 0.5, 20° |
| Ratio | **2.273 : 1** reduction |
| Centre distance | **18.0000 mm** |
| Wheelbase | **36.00 mm** (axles at board y 66 / 102) |
| Wheel | N20 Ø34 × 6.5, Ø8 × 7 hub, 3 mm D bore |
| Track over hubs | 106.60 mm |
| Ground clearance | 5.00 mm plates, **4.00 mm under the 50T** |
| Motors | 2 × N20 + encoder, back to back on board y 84 |

---

## 1. One thing to decide before you print

Module 0.5 teeth are 0.785 mm circular pitch with 0.125 mm root clearance — below what FDM
resolves and at the edge of desktop SLA. The realistic split:

| Part | Route |
|---|---|
| The two gear types | Buy as stock **POM M0.5 20°**, or have them cut/moulded. Print only for fit mock-ups. |
| Plates, motor cradle, shims, standoffs | **Print these.** Smallest feature is a Ø1.7 tap hole. |

The gear STEPs still matter: they define the exact envelope a purchased gear must fit, and
they drive the interference check in §8.

---

## 2. The centre-to-centre equation

For two standard (unshifted) involute spur gears meshing on a common plane:

```
        m · (N₁ + N₂)
  C  =  —————————————
              2
```

Pressure angle does not appear — at standard centres the operating pressure angle equals the
cutting angle, so 20° is inherited rather than imposed. The general form, needed only if you
run the pair off-standard to trim backlash:

```
        m · (N₁ + N₂)      cos α
  C  =  ————————————— · ————————————          j_t  =  2 · ΔC · tan α
              2            cos α_w
```

Opening the centres by ΔC adds circumferential backlash `j_t` — **0.0146 mm per 0.02 mm** of
opening at 20°. That is the knob to turn if the train binds; far more controllable than
re-cutting teeth.

### Applied here

| Mesh | N₁ | N₂ | C = m(N₁+N₂)/2 | Contact ratio |
|---|---|---|---|---|
| Motor pinion → wheel gear | 22 | 50 | **18.0000 mm** | **1.668** |

Contact ratio 1.668 means at least one tooth pair, and for two thirds of the cycle two pairs,
are always in contact. Anything above ~1.4 runs smoothly.

| | d | d_b | d_a | d_f |
|---|---|---|---|---|
| 22T pinion | 11.000 | 10.337 | 12.000 | 9.750 |
| 50T wheel gear | 25.000 | 23.492 | 26.000 | 23.750 |

22T clears the 17T undercut limit for 20° full-depth teeth, so no profile shift is needed.

---

## 3. Why the ratio is what it is

With 3 gears the pinion meshes both wheel gears directly, so the wheelbase **is** the gear
geometry: `WB = 2C = m(N_m + N_w)`. Rearranged:

```
                2·ra_w − 2m
  ratio  =  ————————————————————        ra_w = wheel-gear tip radius
             WB − 2·ra_w + 2m
```

which wants the **biggest wheel gear** and the **shortest wheelbase**. Both are capped: the
wheelbase must exceed the 34 mm wheel diameter or the two tyres on one side overlap, and
`ra_w` must stay under 17 mm or the gear drags. So ratio trades directly against clearance:

| Constraints | Teeth | Wheelbase | Tyre gap | Gnd clr | Ratio |
|---|---|---|---|---|---|
| gap ≥3.0, gnd ≥5.0 | 28T × 46T | 37.00 | 3.00 | 5.00 | 1.64:1 |
| gap ≥2.5, gnd ≥4.5 | 25T × 48T | 36.50 | 2.50 | 4.50 | 1.92:1 |
| **gap ≥2.0, gnd ≥4.0** | **22T × 50T** | **36.00** | **2.00** | **4.00** | **2.27:1** |
| gap ≥2.0, gnd ≥3.5 | 20T × 52T | 36.00 | 2.00 | 3.50 | 2.60:1 |

Change `N_MOTOR` / `N_WHEEL` in `config.py` to move along the table; plate size, standoff
positions and the DXFs all re-derive.

**If you want reduction *and* a long wheelbase**, set `N_IDLER` to an integer. That restores
a 5-gear layout where an idler per wheel decouples spacing from ratio — the idler tooth count
cancels, `(N_i/N_m)·(N_w/N_i) = N_w/N_m` — at the cost of two more gears and two more shafts
per side. The generator supports both; `GEARS_PER_SIDE` reports which is active.

### Parity

Each mesh reverses direction. With the pinion driving both wheel gears directly, each wheel
is **one** mesh from the motor, so both wheels on a side turn the same way. (Driving one
wheel direct and the other through a single idler would counter-rotate them — the robot
fights itself. That is why the 5-gear variant uses *two* idlers, not one.)

### Tooth phasing

Tooth 0 of every generated gear is centred on +X. At a mesh, one gear must present a tooth
where the other presents a space. `mesh_phase()` in `generate_drivetrain.py` **solves** this
rather than tabulating it, because the answer flips with tooth parity — an odd pinion already
presents a space at 180°, an even one does not. For 22T × 50T both wheel gears take a half
pitch (3.6°).

Consequence: the 50T D-bore is clocked with its gear, so **the D-shaft flat must be installed
at that same angle, not vertical.** The clash check found this as a 0.094 mm³ gear-on-shaft
interference during development.

---

## 4. Parallel axle layout

Frame: **+X** longitudinal (0 = motor axis), **+Y** to the robot's left (0 = centreline),
**+Z** up (0 = ground). `board_to_Y` maps +Y to board +x so the drivetrain frame is
**right-handed** with respect to the KiCad STEP export — the earlier `BOARD_CX − bx` made it
left-handed and would have silently mirrored the imported board.

Every axis sits at **Z = 17.000 mm**, the Ø34 wheel radius.

### Hole pattern, both plates (`dxf/parallel_axle_layout.dxf`)

| X | Board y | Z | Feature | Inner plate | Outer plate |
|---|---|---|---|---|---|
| −18.00 | 66 | 17.00 | Wheel axle | Ø6.95 bore + Ø8.5 × 0.5 flange CB (inboard) | Ø6.95 bore + Ø8.5 × 1.0 flange CB (outboard) |
| 0.00 | **84** | 17.00 | Motor | 12.2 × 10.2 slot, R1 + Ø13 × 0.3 relief | Ø5.0 shaft-tip clearance |
| +18.00 | 102 | 17.00 | Wheel axle | as above | as above |

Plate blank **69.0 × 31.0**, corner R3, Z 5.0 → 36.0. Inner plate 3.5 thick with a 4.75 mm
deck ledge folded inboard and four gussets; outer plate 4.0 thick. Blank extent and standoff
positions derive from the 50T tip circle (`_SO_KEEPOUT` holds the standoff barrel 0.5 mm
clear of the tip).

Both plates are **symmetric about X = 0**, so left and right are the same part rotated 180°
about Z. Print two of each, not four different ones.

Fasteners:
- **M2 × 5.0 standoffs** at (±31.5, 9.0), (±31.5, 32.5), (0, 32.5) tie the plate pair
- **M2** at (±9.0, 25.0) and (±9.0, 7.0) pull the motor cradle against each inner plate
- **M3 tapped** at X ±9.00, Y 32.75 in the deck ledge — directly under the PCB's H1–H4
- **M2** at X ±9.3, Y −20 / 0 / +20 clamp the two cradle halves together

### Lateral stack (Y), left side — mirror for right

| Y from | Y to | Item |
|---|---|---|
| 0 | 33.50 | Motor cradle (spans the full width, ±33.5) |
| 33.50 | **37.00** | **Inner plate** 3.5 — F683ZZ #1, race flush at 37.00. Outboard face = **motor faceplate, PCB-DERIVED** |
| 37.00 | 45.50 | N20 Ø3 D-shaft, trimmed to 8.5 of its 10 |
| 37.50 | 41.50 | **Both gears**, FW 4.0 — one common plane |
| 37.00 | 37.50 | Ø4.5 × 0.5 shim on the bearing inner race |
| 42.00 | 46.00 | **Outer plate** 4.0 — F683ZZ #2, flange sunk 1.0 from the outboard face |
| 45.50 | 46.30 | Ø4.5 × 0.8 shim, keeps the rotating hub off the static flange |
| 46.30 | 53.30 | Wheel (hub 46.30–53.30, tyre 46.55–53.05) |

Track over the hubs **106.60 mm**; PCB underside at **Z = 39.00** (plate top 36.0 plus a
3.0 standoff — see §5c).

The N20's 10 mm shaft is what lets both gears share one plane. It is **trimmed to 8.5 mm**:
at a 36 mm wheelbase the wheels reach back to X ≈ ±1, and the last 1.5 mm of shaft fouls the
tyre. `place_motor(trim_shaft=True)` models that cut.

---

## 5. Purchased-part interfaces

### 5a. Bearings

**F683ZZ, 3 ID × 7 OD × 3 W, flange Ø8.2 × 0.5.** Two per axle, eight total. Flanged is the
right call for printed plates: the flange takes axial load against a counterbore face rather
than relying on the press fit alone, which is what fails first in PETG or ABS.

| | Value | Why |
|---|---|---|
| Plate bore | **Ø6.95** | 0.05 interference on the 7.00 outer race |
| Flange counterbore | Ø8.5 | 0.15 clearance on the Ø8.2 flange |
| Lead-in | 0.30 × 45° | Bore mouth chamfer so the bearing starts square |
| Inner plate CB | 0.5 deep, inboard | Race ends flush at Y 37.00, gear shim seats on it |
| Outer plate CB | 1.0 deep, outboard | Sinks the static flange 0.5 below the face so the wheel hub cannot rub |

**For MR63ZZ / MF63ZZ instead** (3 × 6 × 2.5, flange Ø7.2), set `BRG_OD = 6.0, BRG_W = 2.5,
BRG_FL_OD = 7.2, BRG_PRESS = 5.95, BRG_FL_CB = 7.5`. The plates regenerate; nothing else
changes.

**Live axle note.** A 3 mm D-shaft in a round Ø3 bearing bore contacts over roughly 270°, not
360°. Normal for this class of build. For full contact, use round Ø3 stock and grind flats
only where the hub and gear sit.

### 5b. Motor — N20 with encoder

`step/` does **not** contain a motor: the assembly imports the real vendor model that ships
with the PCB project, `n20.3dshapes/N20_Motor_Encoder.step` (7 solids, 3800.8 mm³). A copy is
in `vendor/` for provenance.

Local frame: faceplate at x = 0, shaft Ø3 running 0→10 along +X, body back to x = −32.70,
axis at local (y = 0, z = 5).

Cross-checked against the [Robu N20-with-encoder listings](https://robu.in/product-category/dc-motors/motors/n20-gear-motor/n20-gear-motor-with-encoder/)
(Robu blocks automated fetch — HTTP 403 — so these come from their category and product
listing pages; every SKU across 3 V/6 V/12 V and 30–300 RPM quotes the same mechanicals):

| | Robu | Vendor STEP |
|---|---|---|
| Gearbox | 9 mm | 9.0 |
| Motor can | 15 × 12 × 10 mm | 15.4 long |
| Output shaft | **Ø3 × 10 mm, D-type** | Ø3 × 10 ✓ |
| Encoder | 3 PPR, 140 mm leads | rear section + flange |
| Body behind faceplate | 24 mm + encoder | **32.70** |

> **The slot and channel sections are measured off that solid at build time**
> (`chassis_lib.motor_slot_section()` → 12.00 × 10.00, `motor_channel_section()` → 14.00 ×
> 12.00). An earlier hand-built envelope had the gearbox as 10 × 12 — transposed — which cost
> 65.9 mm³ of interference, and missed the 14 mm rear flange entirely, which burst a 12.4 mm
> channel. Measuring removes that class of error; do not reintroduce duplicate constants.

Two motors sit **back to back on one axis**, bodies spanning Y 4.30 → 37.00 and −4.30 →
−37.00, leaving an **8.60 mm gap** at the centreline for the encoder leads.

### 5c. PCB

The assembly imports the real board export, `fab/micromouse-pcb-simplified.step` (96 solids).
KiCad negates board y on export (`sy = −by`), verified against the XT60 at board (83, 114) →
STEP (83, −114). Rotating +90° about Z maps STEP +x → +Y and +y → −X, which is exactly
`board_to_Y` / `board_to_X`, so the transform is a **pure rotation, no mirror**.

Two adjustments on import:
- **Motor solids are dropped.** KiCad stands them on the board face; the real motors are
  placed at their mechanical height instead. Without this you get four motors.
- **The board stands off the ledge by 3.0 mm.** The export reaches 2.905 mm *below* its own
  substrate (bottom-side parts and THT leads), so it cannot sit flat on the ledge.

### 5d. Wheel

Built to the spec documented in `n20.3dshapes/N20_Wheel.wrl` (copy in `vendor/`):
**Ø34 tyre, 6.5 wide, Ø8 × 7 hub, 3 mm D bore, 3.2 g.** The WRL header notes this
*"supersedes an earlier 32mm/9mm placeholder"* — the Pololu 32 × 7 figures used up to rev 3
were wrong, and at Ø34 the old 22T × 46T train closed the tyre gap to 0.00.

The WRL is VRML primitives and says its own hub bore is cosmetic (*"VRML primitives can't cut
a hole"*), so the wheel is rebuilt here as a solid with the D-bore actually cut. **Datum is
the hub face, not the tyre face** — the hub stands 0.25 proud on each side and is what seats
on the shim.

---

## 6. Bill of materials

### Printed (`step/`)

| Part | Qty | File | Print orientation |
|---|---|---|---|
| Inner side plate | 2 | `plate_inner_x2.step` | outboard face down; ledge and gussets grow upward |
| Outer side plate | 2 | `plate_outer_x2.step` | outboard face down; flange counterbores on the bed |
| Motor cradle, lower | 1 | `motor_cradle_LOWER_x1.step` | as modelled, trough opens upward |
| Motor cradle, upper | 1 | `motor_cradle_UPPER_x1.step` | **flipped**, outer face on the bed, trough upward |
| Standoff M2 × 5.0 | 10 | `standoff_M2_5p0mm_x10.step` | on end |
| Gear shim Ø4.5 × Ø3.1 × 0.5 | 4 | `shim_gear_4p5x3p1x0p5_x4.step` | flat |
| Wheel shim Ø4.5 × Ø3.1 × 0.8 | 4 | `shim_wheel_4p5x3p1x0p8_x4.step` | flat |

PETG or ABS; PLA creeps in the press fits. 0.4 mm nozzle is fine. **No supports** — see §8.
The 0.5 and 0.8 shims are thin enough that buying shim washers is the better option.

### Gears — POM, M0.5, 20°, 0.15 tip chamfer

| Part | Teeth | Bore | FW | Qty | File |
|---|---|---|---|---|---|
| Motor pinion | 22 | 3 mm D | 4.0 | 2 | `gear_22T_m0p5_D3bore_MOTOR.step` |
| Wheel axle gear | 50 | 3 mm D | 4.0 | 4 | `gear_50T_m0p5_D3bore_WHEEL.step` |

The pinion and wheel gear differ, and that difference *is* the 2.27:1. The 50T bore flat is
clocked — see §3.

### Purchased

| Item | Qty | Note |
|---|---|---|
| F683ZZ flanged bearing 3×7×3 | 8 | or MF63ZZ, see §5a |
| Ø3 D-profile shaft, 20.3 mm | 4 | steel or CF; `axle_D3_L20p3_x4_REFERENCE.step` is the model |
| N20 wheel Ø34 × 6.5 | 4 | 3 mm D press-fit hub, see §5d |
| N20 micro metal gearmotor + encoder | 2 | Ø3 × 10 D-shaft, **trim to 8.5**; see §5b |
| M2 × 10 screw | 10 | plate ties through 5.0 standoffs |
| M2 × 6 screw | 8 | cradle to inner plates |
| M2 × 16 screw | 6 | cradle clamp, upper into lower |
| M3 × 6 screw | 4 | PCB to deck ledge, through H1–H4 |
| M3 standoff, 3.0 | 4 | PCB off the ledge, clears bottom-side parts |

---

## 7. Fits and tolerances

| Interface | Nominal | Fit |
|---|---|---|
| Bearing OD → plate bore | 7.00 / 6.95 | 0.05 interference, press (0.30 lead-in) |
| Axle → bearing ID | 3.00 / 3.00 | slip, retained by wheel and gear |
| D-bore gear → D-shaft | 3.08 bore, flat 1.02 off centre | 0.08 slide; bond with retaining compound |
| Wheel hub → axle | 3.05 bore | press |
| Motor gearbox → plate slot | 12.00 × 10.00 + 0.20 | located here, cradle carries the load |
| Motor body → cradle channel | 14.00 × 12.00 + 0.40 | clearance, clamped |

Backlash is modelled into the teeth as 0.05 mm total per pair (each gear gives up 0.025 mm of
pitch-circle tooth thickness). If the train is stiff, open the plate centres — see §2.

---

## 8. Verification

Three checks, all runnable:

### `check_interference.py` — 48 solids, 1128 pairs

```
12 intended interference fit(s), 0 unexpected clash(es)
```

The 12 are deliberate: 1.486 mm³ per bearing press fit (reduced from 1.643 once the lead-in
chamfer took the corner), 1.167 mm³ where the R1 slot fillet meets the vendor model's sharp
gearbox corners, and 9.748 mm³ where the D-bore bites the vendor shaft — that last one is an
artifact, since the STEP models a plain round shaft but the real part is a D-shaft.

What matters is what is **absent**: zero gear-on-gear and zero gear-on-plate volume. That
confirms the centre distance *and* the solved tooth phasing.

This check has earned its place. During development it caught, in order: transposed motor
gearbox dimensions (65.9 mm³), an unmodelled rear flange bursting the cradle channel (30.7),
the shaft tip fouling the tyre, the PCB's bottom-side parts hitting the plates, a clocked
D-bore vs an unclocked shaft (0.094), gussets running into the cradle (15.9), a fillet
rounding the channel's internal corners (0.015), and the wheel hub eating the shim (2.089).

### `check_printability.py` — support-free audit

Measures every downward-facing face against the 45° rule in each part's print orientation:

```
plate_inner          bed 1887.5  bridge 18.9  overhang 0.0 mm2   OK
plate_outer          bed 1979.1  bridge 24.0  overhang 0.0 mm2   OK
motor_cradle_LOWER   bed 1327.0  bridge  0.0  overhang 0.0 mm2   OK
motor_cradle_UPPER   bed 1216.8  bridge  0.0  overhang 0.0 mm2   OK
standoff / shims                             overhang 0.0 mm2   OK

total unsupported overhang: 0.00 mm2  -> SUPPORT-FREE
```

The only sub-45° areas are the bearing counterbore ceilings — ~0.8 mm annuli, well inside
bridging range.

**The motor cradle is split for this reason.** As one closed tube its 14.4 mm channel roof was
an unsupported horizontal span; worse, it could not be assembled at all, because each motor's
encoder cable is already soldered on and would have to be threaded through a sealed bore.
Split on the axle plane and bolted, both halves print trough-up and the motors drop in. The
upper half carries a 12 mm cable exit in the gap between the two motor backs.

### `make_schematic.py` — dimensioned 2-panel drawing

`parallel_axle_layout.svg`, 784 × 924. Panel A side elevation with the axis table, panel B the
lateral stack. Rendered and visually checked via headless Edge at 2× — a bounds check alone
reports "no overflow" for stale labels and text buried under geometry, so the render matters.

---

## 9. Files

```
step/
  gear_22T_m0p5_D3bore_MOTOR.step       motor pinion (x2)
  gear_50T_m0p5_D3bore_WHEEL.step       wheel axle gear (x4)
  plate_inner_x2.step  plate_outer_x2.step
  motor_cradle_LOWER_x1.step  motor_cradle_UPPER_x1.step
  standoff_M2_5p0mm_x10.step
  shim_gear_4p5x3p1x0p5_x4.step  shim_wheel_4p5x3p1x0p8_x4.step
  axle_D3_L20p3_x4_REFERENCE.step
  drivetrain_assembly_4wd.step          full assembly, 48 solids, coloured
dxf/
  plate_inner_layout.dxf  plate_outer_layout.dxf    1:1 flat plate layouts
  parallel_axle_layout.dxf                          pitch + tip circles on the axle line
vendor/
  N20_Motor_Encoder.step   N20_Wheel.wrl            as shipped with the PCB project
parallel_axle_layout.svg                            dimensioned schematic
```

The assembly includes the **real motor and real board**, plus modelled bearings, shims and
wheels. Note the board is the KiCad export: outline, substrate and components, with the motor
solids removed as described in §5c.

### Source

| File | Role |
|---|---|
| `config.py` | every dimension; the only file you should need to edit |
| `gear_lib.py` | involute generator — spline flanks, arc tips, tangent root fillets |
| `chassis_lib.py` | plates, cradle, shims, axles; imports and measures the vendor solids |
| `generate_drivetrain.py` | builds and exports everything |
| `make_schematic.py` | the dimensioned SVG |
| `check_interference.py` | pairwise clash check |
| `check_printability.py` | support-free audit |

### Re-parametrising

Everything derives from `config.py`. To move along the ratio table in §3, change `N_MOTOR` /
`N_WHEEL`. To go back to a 5-gear layout, set `N_IDLER` to an integer.

**Do not hand-edit** `MOTOR_BOARD_X`, `BOARD_MOTOR_Y` or `DECK_HOLES_BOARD` — those are read
off the PCB. If the board moves, re-read them from the `.kicad_pcb` rather than nudging the
drivetrain to match. Likewise do not add motor section constants: they are measured off the
vendor STEP, and a duplicate number is how the transposed-gearbox bug happened.

---

## 10. Known limitations

- **Clearances are tight by choice**: 2.00 mm between the front and rear tyres, 4.00 mm under
  the 50T. Both come from the 3-gear geometry. §3 has the table if you want margin instead of
  ratio — 25T × 48T gives 2.50 / 4.50 at 1.92:1.
- **No weight relief in the plates.** A competition mouse would have lightening pockets; these
  are left solid rather than guessing at load paths.
- **The 50T tip circle is the lowest point of the drivetrain**, below the plates. It is a
  gear, not a skid — do not land on it.
- **The wheel is modelled from the WRL's documented spec**, not from vendor CAD. Tyre profile
  and tread are not represented.
- `N20_Wheel.wrl` carries its own FLAG FOR REVIEW: the board's wheel-clearance notch is still
  cut to the old 32 mm / 9 mm figures, so a real Ø34 wheel is 2 mm larger than that notch
  allows. That is a board change, outside this folder — **check it before cutting metal.**
