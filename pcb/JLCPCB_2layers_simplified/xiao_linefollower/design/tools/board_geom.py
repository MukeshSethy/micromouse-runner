"""Board geometry for the XIAO nRF52840-based micromouse variant.

Per user request: SAME overall dimensions and mechanical geometry as the
ORIGINAL board (pcb/JLCPCB_2layers/design/tools/board_geom.py) -- 100x120mm,
same wheel edge-notches, motor keepouts, same UKMARS/Pololu bracket mounting
holes -- with the front corner treatment changed to a smooth curve (kept from
the ESP32 2-layer variant this was forked from).

XIAO REVISION: the rear-edge ANTENNA NOTCH (a U-shaped cutout sized for the
old ESP32-S3-WROOM-1's overhanging PCB antenna) is REMOVED. The XIAO
nRF52840 Sense Plus uses a small internal ceramic chip antenna that needs no
board cutout at all -- the rear edge is now a plain straight line at
y=BOARD_H across the span the notch used to occupy. Everything else here is
unchanged (no dimensions rescaled).
"""
import math

BOARD_W = 100
BOARD_H = 120

# Rev 12 (user request, further revised): motor moved 15mm toward the front
# (was AXLE_Y=84), wheel diameter bumped to the real vendor part (34mm, was
# a 32mm placeholder -- see n20.pretty/N20_Wheel.wrl's own flagged mismatch
# note). Wheel-notch extra clearance is 5mm TOTAL, split evenly (2.5mm each
# side) so the wheel/motor sits properly CENTERED in its notch (the earlier
# back-only asymmetric version looked off-center, per user feedback).
AXLE_Y = 84 - 15                       # 69
CX = BOARD_W / 2
WHEEL_THK = 9
WHEEL_DIA = 34
WHEEL_INSET = 4
WHEEL_CLEARANCE_EXTRA = 2.5             # extra notch clearance, EACH side (5mm total)

FACE_L = WHEEL_INSET + WHEEL_THK              # 13  (left gearbox faceplate x)
FACE_R = BOARD_W - WHEEL_INSET - WHEEL_THK    # 87

NOTCH_Y1 = AXLE_Y - WHEEL_DIA / 2 - WHEEL_CLEARANCE_EXTRA      # 49.5
NOTCH_Y2 = AXLE_Y + WHEEL_DIA / 2 + WHEEL_CLEARANCE_EXTRA      # 91.5

# Rev 12: front outline is a large full-width rounded nose (popular-
# micromouse "bullet nose" style), instead of the old two small 16mm corner
# fillets + straight front edge. A LITERAL semicircle (sagitta = BOARD_W/2 =
# 50mm) would now overlap the re-centered notch (NOTCH_Y1=49.5) by 0.5mm
# with zero buffer -- backed off slightly to a 44mm-deep arc (barely
# shallower, still spans the full width, visually still the "huge" bullet
# nose) so there's real (5.5mm) clearance to the notch. Depth is a sagitta:
# given a chord of BOARD_W and desired depth FRONT_ARC_DEPTH, the circle
# radius satisfying "passes through (0,D) and (BOARD_W,D), tip at (CX,0)"
# is R = (BOARD_W^2/4 + D^2) / (2*D) (standard sagitta formula).
FRONT_ARC_DEPTH = 44.0
FRONT_ARC_R = (CX ** 2 + FRONT_ARC_DEPTH ** 2) / (2 * FRONT_ARC_DEPTH)
FRONT_ARC_CY = FRONT_ARC_R             # nose tip at y = CY - R = 0
_FRONT_ARC_HALF_ANGLE = math.degrees(math.asin((FRONT_ARC_R - FRONT_ARC_DEPTH) / FRONT_ARC_R))
FRONT_ARC_T0 = 180 + _FRONT_ARC_HALF_ANGLE   # angle at (0, FRONT_ARC_DEPTH)
FRONT_ARC_T1 = 360 - _FRONT_ARC_HALF_ANGLE   # angle at (BOARD_W, FRONT_ARC_DEPTH)
FRONT_ARC_SEGS = 32  # samples along the front nose arc; plenty smooth


def front_arc_half_width(y):
    """Board half-width (distance from CX to the edge) at a given Y, for Y
    within the front arc's span [0, FRONT_ARC_DEPTH]. Used to place/verify
    front-nose components against the REAL curved boundary instead of
    assuming full board width. Returns None if y is outside the arc's span
    (board is full width there, up to the wheel notches)."""
    if y < 0 or y > FRONT_ARC_DEPTH:
        return None
    dy = FRONT_ARC_CY - y
    return math.sqrt(max(FRONT_ARC_R ** 2 - dy ** 2, 0.0))


def _front_arc():
    """Points along the front nose arc, from (0, FRONT_ARC_DEPTH) through the
    nose tip (CX, 0) to (BOARD_W, FRONT_ARC_DEPTH) -- FRONT_ARC_T0 -> T1
    around (CX, FRONT_ARC_CY) at radius FRONT_ARC_R."""
    pts = []
    for i in range(FRONT_ARC_SEGS + 1):
        t = FRONT_ARC_T0 + (FRONT_ARC_T1 - FRONT_ARC_T0) * i / FRONT_ARC_SEGS
        rad = math.radians(t)
        pts.append((round(CX + FRONT_ARC_R * math.cos(rad), 4),
                    round(FRONT_ARC_CY + FRONT_ARC_R * math.sin(rad), 4)))
    return pts


# Antenna notch REMOVED (XIAO revision): the XIAO nRF52840 Sense Plus's
# internal chip antenna needs no board cutout. The rear edge (y=BOARD_H) is
# now a single straight segment across the full width -- no ANT_NOTCH_*
# constants, no ANTENNA_NOTCH keepout.

# Perimeter walk: huge front semicircle (rev 11) -> right edge -> right wheel
# notch -> right edge -> rear-right corner (sharp, as in the original) ->
# plain rear edge (no antenna notch) -> rear-left corner (sharp) -> left
# edge -> left wheel notch -> left edge -> (closes back to the semicircle's
# own start point).
BOARD_OUTLINE = (
    _front_arc()
    + [(BOARD_W, NOTCH_Y1), (FACE_R, NOTCH_Y1), (FACE_R, NOTCH_Y2), (BOARD_W, NOTCH_Y2)]
    + [(BOARD_W, BOARD_H)]
    + [(0, BOARD_H)]
    + [(0, NOTCH_Y2), (FACE_L, NOTCH_Y2), (FACE_L, NOTCH_Y1), (0, NOTCH_Y1)]
)

# "Board absence" rectangles (wheel notches only -- antenna notch removed) --
# every routing/healing script derives its edge keepouts from this one name.
WHEEL_NOTCHES = [
    (0, NOTCH_Y1, FACE_L, NOTCH_Y2),
    (FACE_R, NOTCH_Y1, BOARD_W, NOTCH_Y2),
]

# Motor body + bracket keep-out rectangles (components stay out; tracks OK) --
# identical shape/size to the original (real motor/gearbox dimensions).
MOTOR_KEEPOUTS = [
    (FACE_L, AXLE_Y - 7, FACE_L + 33, AXLE_Y + 7),
    (FACE_R - 33, AXLE_Y - 7, FACE_R, AXLE_Y + 7),
    (FACE_L, AXLE_Y - 13.3, FACE_L + 12.5, AXLE_Y + 13.3),
    (FACE_R - 12.5, AXLE_Y - 13.3, FACE_R, AXLE_Y + 13.3),
]

# Mounting holes: UKMARS/Pololu bracket pattern (D3.2 NPTH, 18.0 c-c, 4.25mm
# inboard of each faceplate) + the front castor -- identical to the original.
MOUNT_HOLES = (
    [(FACE_L + 4.25, AXLE_Y - 9, 1.6), (FACE_L + 4.25, AXLE_Y + 9, 1.6),
     (FACE_R - 4.25, AXLE_Y - 9, 1.6), (FACE_R - 4.25, AXLE_Y + 9, 1.6),
     (CX, 4, 1.5)]
)
