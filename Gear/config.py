"""
config.py - Single source of truth for the Micromouse 4WD 3:1 drivetrain.

Rev 2 (2026-08-10): re-toothed to 15T/20T/45T = 3.00:1 and re-registered onto
the real PCB, pcb/JLCPCB_2layers_simplified/xiao/design/
micromouse-pcb-simplified.kicad_pcb (2-layer XIAO, no line sensor).

Board frame -> drivetrain frame:
    board x (0..100, lateral)      ->  Y = 50 - x        (+Y = robot left)
    board y (0..120, longitudinal) ->  X = y - 84        (0 = motor axis)
    board z                        ->  Z, 0 = ground

Everything the PCB fixes is tagged PCB-DERIVED and must not be hand-edited:
motor faceplate lateral position, motor axis longitudinal position, and the
H1..H4 deck mounting hole pattern.
"""

import math

# ============================================================ PCB (measured)
BOARD_W, BOARD_L, BOARD_T = 100.0, 120.0, 1.6
BOARD_CX, BOARD_MOTOR_Y = 50.0, 84.0        # PCB-DERIVED
MOTOR_BOARD_X = 13.0                        # PCB-DERIVED, MOT1; MOT2 at 87
DECK_HOLES_BOARD = [(17.25, 75.0), (82.75, 75.0),
                    (17.25, 93.0), (82.75, 93.0)]   # PCB-DERIVED H1..H4
DECK_HOLE_D = 3.2


import os

# Real geometry shipped with the PCB project - use these, do not re-model.
PCB_DIR = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "pcb",
    "JLCPCB_2layers_simplified", "xiao", "design"))
MOTOR_STEP = os.path.join(PCB_DIR, "n20.3dshapes", "N20_Motor_Encoder.step")
PCB_STEP = os.path.join(PCB_DIR, "fab", "micromouse-pcb-simplified.step")

# The KiCad STEP export negates board y (sy = -by), confirmed against the
# XT60 at board (83,114) -> STEP (83,-114). Board substrate sits at sz 0..1.51.
PCB_STEP_SUBSTRATE_T = 1.51
MOTOR_AXIS_Z_LOCAL = 5.0        # motor STEP: axis at local (y=0, z=5)
MOTOR_FACE_X_LOCAL = 0.0        # faceplate plane, shaft runs 0..10 along +X


def board_to_Y(bx):
    """+Y follows board +x. Chosen so the drivetrain frame is RIGHT-handed
    with respect to the KiCad STEP export; the earlier `BOARD_CX - bx` made it
    left-handed, which would have silently mirrored the imported board."""
    return bx - BOARD_CX


def board_to_X(by):
    return by - BOARD_MOTOR_Y


# ---------------------------------------------------------------- gear train
MODULE = 0.5
PRESSURE_ANGLE = 20.0
# 3-GEAR layout: the pinion meshes BOTH wheel gears directly.
# Set N_IDLER to an int to go back to the 5-gear layout (idler per wheel).
# Rev 6: re-picked for the REAL mini-sumo wheel (rolling dia ~27). Bolting the
# gear to the wheel's 16.05 bolt circle was checked and REJECTED: it forces the
# root dia outside the holes, >=47T at m0.5, tip r 12.25 vs axle Z 13.5 ->
# 1.25 mm ground clearance (wheel_study.py, section A). Gear on the shaft
# instead; the wheel presses on beside it.
N_MOTOR = 19           # motor pinion, 3 mm D-bore
N_IDLER = None         # None -> 3 gears per side
N_WHEEL = 40           # wheel axle gear, 3 mm D-bore
RATIO = float(N_WHEEL) / N_MOTOR        # 2.105 : 1 reduction
GEARS_PER_SIDE = 3 if N_IDLER is None else 5
BACKLASH = 0.05
ADDENDUM_C = 1.00
DEDENDUM_C = 1.25
FILLET_C = 0.25
GEAR_TIP_CHAMFER = 0.15      # tip-edge break, as a cut POM gear would have

#   C = m * (N1 + N2) / 2
X_MOTOR = 0.0
if N_IDLER is None:
    C_MOTOR_WHEEL = MODULE * (N_MOTOR + N_WHEEL) / 2.0     # 17.00
    C_MOTOR_IDLER = C_IDLER_WHEEL = None
    X_IDLER = None
    X_AXLE = C_MOTOR_WHEEL
    RA_IDLER = None
else:
    C_MOTOR_IDLER = MODULE * (N_MOTOR + N_IDLER) / 2.0
    C_IDLER_WHEEL = MODULE * (N_IDLER + N_WHEEL) / 2.0
    C_MOTOR_WHEEL = None
    X_IDLER = C_MOTOR_IDLER
    X_AXLE = C_MOTOR_IDLER + C_IDLER_WHEEL
    RA_IDLER = MODULE * (N_IDLER + 2) / 2.0

WHEELBASE = 2.0 * X_AXLE                               # 34.00
RA_MOTOR = MODULE * (N_MOTOR + 2) / 2.0
RA_WHEEL = MODULE * (N_WHEEL + 2) / 2.0

# ------------------------------------------------------------ wheels / axles
# REAL wheel: the mini-sumo wheel, measured off miniSumoWheel.3mf by plane
# slicing (see git history for the extraction scripts):
#   flanges dia 26.52, tyre channel dia 23.31 x ~16 wide, overall width 19.06,
#   6 holes dia 3.587 on a 16.05 bolt circle, centre bore dia 2.85 (press on a
#   3 mm shaft), hub plate at ONE end only (mounted inboard here).
# Rolling diameter with the user's 1.5-2 mm silicone band: ~27.
WHEEL_DIA = 27.0                       # rolling dia, silicone included
WHEEL_W = 19.06
WHEEL_FLANGE_D, WHEEL_CHAN_D = 26.52, 23.31
WHEEL_FLANGE_W = 1.5                   # each flange, channel between
WHEEL_BORE = 2.85
WHEEL_BC_R, WHEEL_BC_HOLE = 8.026, 3.587
AXLE_Z = WHEEL_DIA / 2.0               # 13.5
AXLE_D, AXLE_FLAT = 3.0, 2.5
GEAR_GND_CLR = AXLE_Z - RA_WHEEL       # 4.25 under the 45T

# ----------------------------------------------------------------- bearings
BRG_ID, BRG_OD, BRG_W = 3.0, 7.0, 3.0
BRG_FL_OD, BRG_FL_W = 8.2, 0.5
BRG_PRESS = 6.95
BRG_FL_CB = 8.5

# ------------------------------------------- N20 + encoder (Robu / footprint)
# Footprint N20_Motor_Encoder: origin = faceplate centre, +X = shaft.
# Courtyard X -33.20..+10.25, Y +/-7.05. Shaft rect 0..10 x +/-1.5.
# The motor solid itself is IMPORTED (MOTOR_STEP), and the plate slot / cradle
# channel sections are MEASURED off it at build time by chassis_lib. Only the
# few numbers the geometry cannot supply live here. An earlier hand-built
# envelope kept a full set of section constants; they disagreed with the real
# part (gearbox is 12x10, not 10x12) and have been removed rather than left to
# rot -- edit the vendor STEP, not a duplicate number.
MOT_SHAFT_D, MOT_SHAFT_L = 3.0, 10.0        # Robu "Output Shaft 3 x 10mm, D"

# --------------------------------------------------------- lateral Y stack
Y_MOTOR_FACE = abs(board_to_Y(MOTOR_BOARD_X))   # 37.0  PCB-DERIVED
PLATE_IN_T = 3.5
Y_IN_OUT = Y_MOTOR_FACE                      # 37.0 inner plate OUTBOARD face
Y_IN_IN = Y_IN_OUT - PLATE_IN_T              # 33.5

GEAR_FW = 4.0
Y_GEAR = Y_IN_OUT + 0.5                      # 37.5 .. 41.5, all three gears
IDLER_FW = GEAR_FW + 0.4                     # bridges with 0.2 float per side
Y_IDLER = Y_GEAR - 0.2

# Rev 6: NO OUTER PLATE. The 19.06 wide wheel would push an outer plate to
# Y ~65 and the track to ~131 mm; without it the track is 122.1. The axle is a
# CANTILEVER instead: both bearings sit in a boss that extends INBOARD from the
# inner plate (the pinion plane is pinned at 37.5..41.5 by the motor shaft, so
# there is no room for bearings outboard of the gear). Loads are micromouse-
# scale: bearing pair span ~6.5, overhang to wheel centre ~14.6, ratio 2.2 --
# a 2 N cornering load sees ~4.5 N at the outer race, trivial for an F683ZZ.
BOSS_T = 10.0                                # boss length inboard of the plate
Y_BOSS_IN = Y_IN_OUT - BOSS_T - PLATE_IN_T   # 23.5, the boss's inboard END
BOSS_D = 11.0
WHEEL_SHIM_T = 0.5
Y_WHEEL = Y_GEAR + GEAR_FW + WHEEL_SHIM_T    # 42.0 wheel inboard face (hub end)
TRACK_OUTER = 2.0 * (Y_WHEEL + WHEEL_W)      # 122.12

AXLE_SHIM_T = 0.5
Y_AXLE_IN = Y_BOSS_IN + 0.5
AXLE_LEN = (Y_WHEEL + WHEEL_W - 1.0) - Y_AXLE_IN
IDLER_DOWEL_D, IDLER_DOWEL_L = 3.0, 10.0

# ------------------------------------------------------------- side plates
_SO_R, _SO_CLR = 2.0, 0.5
_SO_KEEPOUT = RA_WHEEL + _SO_R + _SO_CLR

# LOW-PROFILE STACK (rev 5). The PCB is the lowest structural item, sitting
# just under the drivetrain, and the wheels pass through side notches. Putting
# the board ON the axle line would be flatter only in theory: the motors sit on
# that line too (axis Z 17, body Z 11..23, |Y| 4.3..37), so the board would need
# a ~14 x 74 slot through its middle. Robot height is set by the wheel either
# way, so this gives the same 34 mm with an intact board.
BOARD_Z = 5.0                                # PCB underside = ground clearance
PL_Z0 = BOARD_Z + BOARD_T                    # plates stand on the board top
PL_X = X_AXLE + BOSS_D / 2.0 + 2.5           # covers the bearing bosses
PL_Z1 = AXLE_Z + BRG_FL_CB / 2.0 + 3.0       # clears the flange counterbore
PL_R = 3.0
GROUND_CLEAR = BOARD_Z
# No standoffs: with the outer plate gone there is nothing to tie. The plate
# hangs off the cradle end screws alone.
STANDOFF_PTS = []

M2_CLEAR, M2_TAP = 2.20, 1.70
M3_TAP = 2.50                                # deck ledge, PCB uses M3 (H1..H4)
# Slot and channel sections are MEASURED off the vendor STEP at build time
# (chassis_lib.motor_slot_section / motor_channel_section); only clearances live here.
MOT_SLOT_CL, MOT_SLOT_R = 0.20, 1.0
TUBE_CHAN_CL = 0.40
MOT_SHAFT_USED = 4.8        # trim the 10 mm vendor shaft: the pinion plane
                            # ends at Y 41.5 and the wheel face is at 42.0
MOT_BODY_REAL = 32.70       # vendor STEP: body runs x -32.70..0
CABLE_SLOT_X = 12.0         # encoder lead exit in the top of the motor tube
BRG_LEAD_IN = 0.30          # chamfer at the mouth of every bearing bore
MOT_RELIEF_D = 2 * RA_MOTOR + 1.0
MOT_RELIEF_T = 0.3
MOT_SHAFT_CLR_D = MOT_SHAFT_D + 2.0          # tip pokes through the outer plate

# ------------------------------------------------------------- motor tube
# (declared before the deck block: the deck gussets must clear TUBE_X)
TUBE_X, TUBE_Z0, TUBE_Z1 = 11.5, PL_Z0, 20.5  # Z0 = board top; axis at Z 13.5
# plate now spans Z 6.6..20.75, so the screws move inside it
TUBE_SCREW_PTS = [(-9.0, 18.0), (9.0, 18.0), (-9.0, 9.0), (9.0, 9.0)]
# Cradle is split on the axle plane and bolted; clamp screws clear both the
# channel (half-width ~7.2) and the end-face screws at Y = +/-26.5..33.5.
TUBE_CLAMP_X = 9.3
TUBE_CLAMP_Y = (-20.0, 0.0, 20.0)

# Deck ledge now sits at the BOTTOM of the inner plate and bolts DOWN onto the
# board's H1..H4, instead of carrying the board above it.
DECK_HOLES = [(board_to_X(by), abs(board_to_Y(bx)))
              for (bx, by) in DECK_HOLES_BOARD]
DECK_HOLE_X = sorted(set(round(abs(x), 3) for (x, _) in DECK_HOLES))[0]   # 9.0
DECK_LEDGE_Y = min(y for (_, y) in DECK_HOLES)                            # 32.75
DECK_FLANGE_X = 20.0
DECK_FLANGE_L = (Y_IN_IN - DECK_LEDGE_Y) + 4.0
DECK_GUSSET_H = 7.0          # gusset depth down the plate face
DECK_GUSSET_T = 2.5          # gusset thickness
# Gussets must clear the motor tube (half-width TUBE_X), so they flank the M3
# holes rather than sitting on them.
DECK_GUSSET_X = (TUBE_X + DECK_GUSSET_T / 2.0 + 0.75, DECK_FLANGE_X - DECK_GUSSET_T - 1.0)

Y_TUBE = Y_IN_IN                             # tube ends butt the inner plates

# ------------------------------------------------------------------ colours
COL = {
    "plate": (0.882, 0.102, 0.153, 1.0),
    "tube": (0.643, 0.263, 0.098, 1.0),
    "gear": (0.929, 0.671, 0.212, 1.0),
    "idler": (0.667, 0.647, 0.196, 1.0),
    "hw": (0.502, 0.502, 0.502, 1.0),
    "brg": (0.800, 0.800, 0.800, 1.0),
    "dark": (0.200, 0.200, 0.200, 1.0),
    "pcb": (0.200, 0.325, 0.176, 1.0),
}


def summary():
    return "\n".join([
        "PCB              : xiao 2-layer, %.0f x %.0f, motors @ board "
        "(%.0f/%.0f, %.0f)" % (BOARD_W, BOARD_L, MOTOR_BOARD_X,
                               BOARD_W - MOTOR_BOARD_X, BOARD_MOTOR_Y),
        "Module / angle   : m%.1f / %.0f deg" % (MODULE, PRESSURE_ANGLE),
        "Train            : %s   ratio %.3f : 1   %d gears/side"
        % ("%dT -> %dT" % (N_MOTOR, N_WHEEL) if N_IDLER is None
           else "%dT -> %dT -> %dT" % (N_MOTOR, N_IDLER, N_WHEEL),
           RATIO, GEARS_PER_SIDE),
        "Centre distance  : %.4f mm" % (C_MOTOR_WHEEL if N_IDLER is None
                                        else C_MOTOR_IDLER),
        "Axle X           : %+.2f / %+.2f  (board y %.2f / %.2f)"
        % (-X_AXLE, X_AXLE, BOARD_MOTOR_Y - X_AXLE, BOARD_MOTOR_Y + X_AXLE),
        "Idler X          : %s" % ("none (3-gear layout)" if X_IDLER is None
                                   else "%+.2f / %+.2f" % (-X_IDLER, X_IDLER)),
        "Wheelbase        : %.2f mm   tyre gap %.2f" % (WHEELBASE,
                                                        WHEELBASE - WHEEL_DIA),
        "Axle line Z      : %.2f   gear ground clr %.2f" % (AXLE_Z,
                                                            GEAR_GND_CLR),
        "Motor faceplate Y: %+.2f (PCB-derived)   shaft %.1f long"
        % (Y_MOTOR_FACE, MOT_SHAFT_L),
        "Gear plane Y     : %.2f .. %.2f" % (Y_GEAR, Y_GEAR + GEAR_FW),
        "Plates           : %.1f x %.1f, Z %.1f..%.1f"
        % (2 * PL_X, PL_Z1 - PL_Z0, PL_Z0, PL_Z1),
        "Track (outer)    : %.2f mm   PCB underside Z %.2f"
        % (TRACK_OUTER, BOARD_Z),
    ])


if __name__ == "__main__":
    print(summary())
