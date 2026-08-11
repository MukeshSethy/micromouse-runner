"""
chassis_lib.py - Printed structure for the Micromouse 4WD 1:1 drivetrain.

The two side plates are modelled in a LOCAL frame:
    local x = longitudinal (matches global X)
    local y = height        (matches global Z)
    local z = plate thickness, 0 .. t

    local z = 0  ->  OUTBOARD face
    local z = t  ->  INBOARD  face

place_plate() rotates +90 deg about X (so local y -> global Z, local z ->
global -Y) and drops the plate so its outboard face lands on y_out.
"""

import math

import cadquery as cq

import config as K


# ------------------------------------------------------------------ helpers
def _cyl(d, h, x=0.0, y=0.0, z=0.0):
    return cq.Workplane("XY").circle(d / 2.0).extrude(h).translate((x, y, z))


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _cyl_y(d, y0, y1, x=0.0, z=0.0):
    """Cylinder whose axis runs along +Y, spanning y0..y1."""
    return (cq.Workplane("XY").circle(d / 2.0).extrude(y1 - y0)
            .rotate((0, 0, 0), (1, 0, 0), -90)
            .translate((x, y0, z)))


def _holes(solid, pts, d, t, z0=None, depth=None, from_face="through"):
    """Cut cylinders at (x, y) points in the local plate frame."""
    for (x, y) in pts:
        if from_face == "through":
            solid = solid.cut(_cyl(d, t + 2.0, x, y, -1.0))
        elif from_face == "z0":
            solid = solid.cut(_cyl(d, depth + 1.0, x, y, -1.0))
        else:  # "zt"
            solid = solid.cut(_cyl(d, depth + 1.0, x, y, t - depth))
    return solid


def _blank(t):
    h = K.PL_Z1 - K.PL_Z0
    return (cq.Workplane("XY")
            .center(0.0, (K.PL_Z0 + K.PL_Z1) / 2.0)
            .rect(2 * K.PL_X, h).extrude(t)
            .edges("|Z").fillet(K.PL_R))


def _lead_in(d, cham, x, y, z, up=True):
    """Conical lead-in at a bore mouth so the bearing starts square."""
    c = cq.Solid.makeCone(d / 2.0 + cham, d / 2.0, cham)
    wp = cq.Workplane("XY").newObject([c])
    if not up:
        wp = wp.rotate((0, 0, 0), (1, 0, 0), 180)
    return wp.translate((x, y, z))


def _bearing_pocket(solid, t, from_face, cb_depth):
    """F683ZZ seat: press bore right through + flange counterbore + lead-in."""
    ch = K.BRG_LEAD_IN
    for sx in (-1.0, 1.0):
        x = sx * K.X_AXLE
        solid = solid.cut(_cyl(K.BRG_PRESS, t + 2.0, x, K.AXLE_Z, -1.0))
        if from_face == "z0":
            solid = solid.cut(_cyl(K.BRG_FL_CB, cb_depth + 1.0,
                                   x, K.AXLE_Z, -1.0))
            # bore is entered from z0, so the lead-in sits at the CB floor
            solid = solid.cut(_lead_in(K.BRG_PRESS, ch, x, K.AXLE_Z, cb_depth))
        else:
            solid = solid.cut(_cyl(K.BRG_FL_CB, cb_depth + 1.0,
                                   x, K.AXLE_Z, t - cb_depth))
            solid = solid.cut(_lead_in(K.BRG_PRESS, ch, x, K.AXLE_Z,
                                       t - cb_depth, up=False))
    return solid


def _motor_slot(t):
    sx, sz = motor_slot_section()
    return (cq.Workplane("XY").center(0.0, K.AXLE_Z)
            .rect(sx + K.MOT_SLOT_CL, sz + K.MOT_SLOT_CL).extrude(t + 2.0)
            .edges("|Z").fillet(K.MOT_SLOT_R).translate((0, 0, -1.0)))


# -------------------------------------------------------------- motor pod
def motor_pod():
    """
    Rev 7: ONE printed part per side replaces the inner plate and both cradle
    halves. Local frame = plate frame (x longitudinal, y height/Z-global,
    z = distance inboard from the outboard face at global |Y| = 37).

    Sections, all support-free printed outboard-face-down:
      wall   z 0..3.5           old plate: motor slot, pinion/gear reliefs
      bosses z 0..13.5          bearing tubes at x = +/-14.75
      base   z 3.5..33.5        floor over the PCB, 2x M3 into H1/H2
      ribs   two V-saddles cradling the N20 can, band ears beside them
    """
    t = K.PLATE_IN_T
    z_base_end = K.Y_IN_OUT - K.POD_Y_IN               # 33.5 inboard reach
    p = _blank(t)

    # bearing bosses + bores (identical seat geometry to rev 6)
    for sx in (-1.0, 1.0):
        x = sx * K.X_AXLE
        p = p.union(cq.Workplane("XY").circle(K.BOSS_D / 2.0)
                    .extrude(K.BOSS_T + t).translate((x, K.AXLE_Z, 0)))
        L = K.BOSS_T + t
        p = p.cut(_cyl(K.BRG_PRESS, L + 2.0, x, K.AXLE_Z, -1.0))
        p = p.cut(_cyl(K.BRG_FL_CB, K.BRG_FL_W + 0.05, x, K.AXLE_Z, 0.0))
        p = p.cut(_lead_in(K.BRG_PRESS, K.BRG_LEAD_IN, x, K.AXLE_Z,
                           K.BRG_FL_W))
        p = p.cut(_cyl(K.BRG_FL_CB, K.BRG_FL_W + 0.05, x, K.AXLE_Z,
                       L - K.BRG_FL_W))
        p = p.cut(_lead_in(K.BRG_PRESS, K.BRG_LEAD_IN, x, K.AXLE_Z,
                           L - K.BRG_FL_W, up=False))
        # rotating-face relief so the 40T (butting the inner race) never rubs
        # the static wall outside the race diameter
        p = p.cut(_cyl(2 * K.RA_WHEEL + 1.0, K.POD_RELIEF_T + 1.0,
                       x, K.AXLE_Z, -1.0))

    # base floor over the board, out to the saddle end - SLOTTED under the
    # motor: the encoder section (12 wide, bottom at Z 7.5) sits lower than a
    # solid floor top, so the floor is two rails beside the motor belly
    p = p.union(_box(-K.POD_X, K.POD_X, K.PL_Z0, K.PL_Z0 + K.POD_BASE_T,
                     t, z_base_end))
    # slot width 7.3 per side: the encoder flange (dia ~14 at Y 9.3..10.9)
    # reaches past the 12-wide body
    p = p.cut(_box(-7.3, 7.3, K.PL_Z0 - 1.0, K.AXLE_Z, t + 0.6, z_base_end + 1.0))

    # the wall cuts the pod inherited from the plate: gearbox register slot
    # and the pinion-face relief (the 19T butts nothing, but rotates 0.3 mm
    # clear of the static wall like the 40Ts do)
    p = p.cut(_motor_slot(t))
    p = p.cut(_cyl(2 * K.RA_MOTOR + 1.0, K.POD_RELIEF_T + 1.0,
                   0.0, K.AXLE_Z, -1.0))

    # M3 board-mount pads: the PCB's H1..H4 land at x +/-9, |Y| 32.75 ->
    # local z = 37 - 32.75 = 4.25, just inboard of the wall
    z_h = K.Y_IN_OUT - K.DECK_LEDGE_Y
    for sx in (-1.0, 1.0):
        # inner pad edge at 6.7, OUTBOARD of the 12-wide gearbox
        x0, x1 = sorted((sx * 6.7, sx * (K.DECK_HOLE_X + 4.0)))
        p = p.union(_box(x0, x1, K.PL_Z0, K.PL_Z0 + 4.5, t, z_h + 3.0))
        p = p.cut(_cyl_y(3.2, K.PL_Z0 - 2.0, K.PL_Z0 + 6.0,
                         x=sx * K.DECK_HOLE_X, z=z_h))

    # V-saddle ribs under the motor can (axis at global Z 13.5, dia 10)
    for zr in K.POD_RIB_Y:
        zq = K.Y_IN_OUT - zr                            # local z of the rib
        # U-channel saddle: flat floor under the can's flat belly, cheeks
        # beside its rounded sides. (A V-saddle was tried first - the N20 can
        # is a 12x10 flat-sided oval per the vendor STEP, not a cylinder, and
        # its corners speared the V walls.)
        rib = _box(-9.4, 9.4, K.PL_Z0, K.AXLE_Z - 1.0, zq - 2.0, zq + 2.0)
        p = p.union(rib)
        p = p.cut(_box(-K.POD_CHAN_W / 2.0, K.POD_CHAN_W / 2.0,
                       K.POD_CHAN_FLOOR, K.AXLE_Z + 6.0,
                       zq - 3.0, zq + 3.0))
        # band ears: dia-3 hole through each, elastic band over the can
        for sx in (-1.0, 1.0):
            p = p.union(_box(sx * K.POD_EAR_X - 1.5, sx * K.POD_EAR_X + 1.5,
                             K.PL_Z0, K.POD_EAR_HOLE_Z + 3.0,
                             zq - 2.0, zq + 2.0))
            p = p.cut(_cyl_y(3.0, zq - 3.0, zq + 3.0,
                             x=sx * K.POD_EAR_X, z=K.POD_EAR_HOLE_Z))

    return p


# ------------------------------------------------- inner plate (rev 6, kept
# only because motor_pod builds on the same blank; do not export separately)
def plate_inner():
    """
    Rev 6: the ONLY plate. Carries a cantilever bearing boss per axle,
    extending INBOARD (the pinion plane outboard is owned by the motor shaft,
    so bearings cannot live there). Two F683ZZ per axle: one flanged at the
    plate's outboard face, one flanged at the boss's inboard end.
    """
    t = K.PLATE_IN_T
    p = _blank(t)

    for sx in (-1.0, 1.0):
        x = sx * K.X_AXLE
        # boss body, inboard of the plate (local z runs 0=outboard face)
        p = p.union(cq.Workplane("XY").circle(K.BOSS_D / 2.0)
                    .extrude(K.BOSS_T + t).translate((x, K.AXLE_Z, 0)))
        # through press bore + flange counterbores + lead-ins at both mouths
        L = K.BOSS_T + t
        p = p.cut(_cyl(K.BRG_PRESS, L + 2.0, x, K.AXLE_Z, -1.0))
        p = p.cut(_cyl(K.BRG_FL_CB, K.BRG_FL_W + 0.05, x, K.AXLE_Z, 0.0))
        p = p.cut(_lead_in(K.BRG_PRESS, K.BRG_LEAD_IN, x, K.AXLE_Z,
                           K.BRG_FL_W))
        p = p.cut(_cyl(K.BRG_FL_CB, K.BRG_FL_W + 0.05, x, K.AXLE_Z,
                       L - K.BRG_FL_W))
        p = p.cut(_lead_in(K.BRG_PRESS, K.BRG_LEAD_IN, x, K.AXLE_Z,
                           L - K.BRG_FL_W, up=False))

    # idler dowel press fit (ream to 3.00 slip if you prefer a floating pin)
    if K.X_IDLER is not None:
        p = _holes(p, [(-K.X_IDLER, K.AXLE_Z), (K.X_IDLER, K.AXLE_Z)], 2.90, t)

    # N20 gearbox nose passes through; face lands flush with the outboard face
    p = p.cut(_motor_slot(t))

    # relief so the motor pinion never touches the plate
    p = p.cut(_cyl(K.MOT_RELIEF_D, K.MOT_RELIEF_T + 1.0, 0.0, K.AXLE_Z, -1.0))

    p = _holes(p, K.STANDOFF_PTS, K.M2_TAP, t)
    p = _holes(p, K.TUBE_SCREW_PTS, K.M2_CLEAR, t)

    # No deck ledge. Both side plates sit OUTBOARD of the board edge, over the
    # wheel notch, so there is no board under them to bolt to. The whole
    # drivetrain hangs off the motor cradle, which is the single board
    # interface and picks up H1..H4 directly -- see motor_tube_half().
    return p


# Rev 6: no outer plate. The 19.06 wide wheel would push it to Y ~65 and the
# track to ~131; the cantilever boss on the inner plate replaces its bearings.


def place_plate(p, y_out, right=False):
    p = p.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, y_out, 0))
    return p.mirror("XZ") if right else p


# --------------------------------------------------------------- motor tube
def motor_tube_half(lower=True):
    """
    Motor cradle, SPLIT on the axle plane into a bolted clamp.

    Why split: as one closed tube the 14.4 mm channel roof is an unsupported
    horizontal span, so it cannot print without supports; and a sealed bore
    cannot be assembled at all, because each motor's encoder cable is already
    soldered on and would have to be threaded through. Split on Z = AXLE_Z,
    both halves print TROUGH-UP straight onto the bed with no overhang, and
    the motors drop in before the cap goes on.

    Both halves carry both N20s back to back on the axis the PCB fixes at
    board y = 84. The motors are LOCATED by the gearbox in the inner-plate
    slot at each end; the cradle carries them and ties the plates together.
    """
    yt = K.Y_TUBE
    z0, z1 = ((K.TUBE_Z0, K.AXLE_Z) if lower else (K.AXLE_Z, K.TUBE_Z1))
    body = _box(-K.TUBE_X, K.TUBE_X, -yt, yt, z0, z1)
    # fillet the OUTER long edges only, never the ones on the split face
    body = body.edges("|Y and " + ("<Z" if lower else ">Z")).fillet(1.5)

    cx, cz = motor_channel_section()
    cx = (cx + K.TUBE_CHAN_CL) / 2.0
    cz = (cz + K.TUBE_CHAN_CL) / 2.0
    if lower:
        trough = _box(-cx, cx, -yt - 1.0, yt + 1.0, K.AXLE_Z - cz,
                      K.AXLE_Z + 1.0)
    else:
        trough = _box(-cx, cx, -yt - 1.0, yt + 1.0, K.AXLE_Z - 1.0,
                      K.AXLE_Z + cz)
    body = body.cut(trough)

    # Relief for the plate's bearing bosses. The boss (dia 11 at X +/-14.75)
    # reaches inboard from Y 37 to 27; the cradle corner occupies X up to 11.5
    # over that Y range, so a clearance scallop is cut at each corner.
    for sx in (-1.0, 1.0):
        body = body.cut(_cyl_y(K.BOSS_D + 0.4, yt - K.BOSS_T - 1.0, yt + 1.0,
                               x=sx * K.X_AXLE, z=K.AXLE_Z))
        body = body.cut(_cyl_y(K.BOSS_D + 0.4, -yt - 1.0, -yt + K.BOSS_T + 1.0,
                               x=sx * K.X_AXLE, z=K.AXLE_Z))

    if not lower:
        # Encoder cable exit. Both motors face inboard and their leads come off
        # the rear of the encoder PCB, in the gap between the two motor backs.
        # Printed trough-up this is a bed-level pocket, so it needs no support.
        gap = K.Y_MOTOR_FACE - K.MOT_BODY_REAL     # 4.30 half-gap
        body = body.cut(_box(-K.CABLE_SLOT_X / 2.0, K.CABLE_SLOT_X / 2.0,
                             -gap, gap,
                             K.AXLE_Z + cz - 0.01, K.TUBE_Z1 + 1.0))

    # clamp screws, vertical in the print -> no support
    for x in (-K.TUBE_CLAMP_X, K.TUBE_CLAMP_X):
        for y in K.TUBE_CLAMP_Y:
            d = K.M2_TAP if lower else K.M2_CLEAR
            body = body.cut(_cyl(d, z1 - z0 + 2.0, x, y, z0 - 1.0))

    if lower:
        # THE board interface: M3 down into the PCB's H1..H4 (PCB-DERIVED).
        # Those holes sit at X +/-9.00, |Y| 32.75, which is inside this part's
        # footprint -- the cradle is the only structure with board under it.
        for (dx, dy) in K.DECK_HOLES:
            for sy in (-1.0, 1.0):
                body = body.cut(_cyl(K.M3_TAP, z1 - z0 + 2.0,
                                     dx, sy * dy, z0 - 1.0))

    # end-face screws into the inner plates
    for (x, z) in K.TUBE_SCREW_PTS:
        if not (z0 < z < z1):
            continue
        body = body.cut(_cyl_y(K.M2_TAP, yt - 7.0, yt + 1.0, x=x, z=z))
        body = body.cut(_cyl_y(K.M2_TAP, -yt - 1.0, -yt + 7.0, x=x, z=z))
    return body


def motor_tube_lower():
    return motor_tube_half(lower=True)


def motor_tube_upper():
    return motor_tube_half(lower=False)


def motor_tube():
    """Both halves as one solid, for the assembly and the clash check."""
    return motor_tube_lower().union(motor_tube_upper())




# ------------------------------------------------------- small turned parts
def shim(od, idia, t):
    return _cyl(od, t).cut(_cyl(idia, t + 2.0, z=-1.0))


def standoff():
    return shim(4.0, K.M2_CLEAR, K.STANDOFF_L)


def d_axle(length=None):
    L = length or K.AXLE_LEN
    flat = K.AXLE_D / 2.0 - (K.AXLE_D - K.AXLE_FLAT)
    s = _cyl(K.AXLE_D, L)
    return s.cut(cq.Workplane("XY").center(flat + K.AXLE_D, 0.0)
                 .rect(2 * K.AXLE_D, 2 * K.AXLE_D).extrude(L))


# ------------------------------------------------- purchased-part stand-ins
def bearing_f683():
    b = _cyl(K.BRG_OD, K.BRG_W, z=K.BRG_FL_W)
    b = b.union(_cyl(K.BRG_FL_OD, K.BRG_FL_W))
    return b.cut(_cyl(K.BRG_ID, K.BRG_W + K.BRG_FL_W + 2.0, z=-1.0))


def wheel_placeholder():
    """
    The mini-sumo wheel, rebuilt as a solid from the dimensions sliced out of
    miniSumoWheel.3mf: flanges dia 26.52, silicone channel dia 23.31, width
    19.06, 6 x dia 3.587 on a 16.05 bolt circle, dia 2.85 centre bore, hub
    plate at ONE end (~4.5 thick, mounted inboard = local z 0). Plus the
    user's silicone band bringing the rolling dia to WHEEL_DIA.
    """
    w = K.WHEEL_W
    fl = K.WHEEL_FLANGE_W
    body = _cyl(K.WHEEL_FLANGE_D, fl)                       # inboard flange
    body = body.union(_cyl(K.WHEEL_CHAN_D, w - 2 * fl, z=fl))
    body = body.union(_cyl(K.WHEEL_FLANGE_D, fl, z=w - fl)) # outboard flange
    # silicone band in the channel, up to the rolling diameter
    body = body.union(_cyl(K.WHEEL_DIA, w - 2 * fl, z=fl))
    # hollow shell: bore out everything outboard of the 4.5 hub plate
    body = body.cut(_cyl(K.WHEEL_CHAN_D - 3.0, w - 4.5 + 1.0, z=4.5))
    # bolt pattern through the hub plate
    for k in range(6):
        a = math.radians(60 * k)
        body = body.cut(_cyl(K.WHEEL_BC_HOLE, 6.0,
                             K.WHEEL_BC_R * math.cos(a),
                             K.WHEEL_BC_R * math.sin(a), -0.5))
    # centre bore, press on the 3 mm shaft
    body = body.cut(_cyl(K.WHEEL_BORE, 6.0, z=-0.5))
    return body


_MOTOR_CACHE = [None]
_PCB_CACHE = [None]


def n20_encoder_motor():
    """
    The REAL vendor model that ships with the PCB project:
        xiao/design/n20.3dshapes/N20_Motor_Encoder.step
    7 solids, 3800.8 mm3. Local frame: faceplate at x = 0, shaft dia 3 running
    0..10 along +X, body back to x = -32.70, axis at local (y=0, z=5).
    """
    if _MOTOR_CACHE[0] is None:
        _MOTOR_CACHE[0] = cq.importers.importStep(K.MOTOR_STEP)
    return _MOTOR_CACHE[0]


def place_motor(y_face=None, trim_shaft=True):
    """
    Rotate the vendor model so its shaft runs +Y and its axis lands on the
    wheel-axle line, with the faceplate at the PCB-derived Y.

    trim_shaft: the vendor shaft is 10 mm. At a 34 mm wheelbase the wheels
    reach back to X = +/-1, so the last ~1.5 mm of shaft fouls the tyre. Cut
    it to K.MOT_SHAFT_USED on assembly; this models that cut.
    """
    y_face = K.Y_MOTOR_FACE if y_face is None else y_face
    m = (n20_encoder_motor()
         .rotate((0, 0, 0), (0, 0, 1), 90)
         .translate((0, y_face, K.AXLE_Z - K.MOTOR_AXIS_Z_LOCAL)))
    if trim_shaft:
        m = m.cut(_box(-60, 60, y_face + K.MOT_SHAFT_USED, y_face + 60,
                       -60, 120))
    return m


def _motor_section(y0, y1):
    """
    Measure the motor's real cross-section between two Y planes, straight off
    the vendor solid. Used to size the plate slot and the tube channel so they
    can never disagree with the actual part -- an assumed 10x12 gearbox (it is
    really 12x10, rotated) cost 65.9 mm3 of interference before this existed.
    """
    sec = place_motor(trim_shaft=False).intersect(
        _box(-60, 60, y0, y1, -60, 120))
    b = sec.val().BoundingBox()
    return b.xlen, b.zlen


def motor_slot_section():
    return _motor_section(K.Y_IN_IN, K.Y_IN_OUT)


def motor_channel_section():
    return _motor_section(-K.Y_TUBE, K.Y_TUBE)


def pcb_board(drop_motors=True):
    """
    The REAL board export, xiao/design/fab/micromouse-pcb-simplified.step.

    KiCad negates board y on export (sy = -by), verified against the XT60 at
    board (83,114). Rotating +90 about Z maps STEP +x -> +Y and +y -> -X, which
    is exactly board_to_Y / board_to_X, so the transform is a pure rotation --
    no mirror. The motor solids are dropped because we place the real motors
    ourselves at the mechanical height; KiCad stands them on the board face.
    """
    if _PCB_CACHE[0] is None:
        _PCB_CACHE[0] = cq.importers.importStep(K.PCB_STEP)
    wp = _PCB_CACHE[0]

    solids = wp.solids().vals()
    if drop_motors:
        keep = []
        for s in solids:
            b = s.BoundingBox()
            cx, cy = (b.xmin + b.xmax) / 2.0, (b.ymin + b.ymax) / 2.0
            in_band = abs(cy + K.BOARD_MOTOR_Y) < 7.1
            in_body = (12.0 < cx < 47.0) or (53.0 < cx < 88.0)
            if in_band and in_body and b.zmax > K.PCB_STEP_SUBSTRATE_T:
                continue
            keep.append(s)
        solids = keep

    comp = cq.Compound.makeCompound(solids)
    return (cq.Workplane("XY").newObject([comp])
            .rotate((0, 0, 0), (0, 0, 1), 90)
            .translate((-K.BOARD_MOTOR_Y, -K.BOARD_CX, K.BOARD_Z)))
