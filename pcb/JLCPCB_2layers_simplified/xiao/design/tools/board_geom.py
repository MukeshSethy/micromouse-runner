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

AXLE_Y = 84
CX = BOARD_W / 2
WHEEL_THK = 9
WHEEL_DIA = 32
WHEEL_INSET = 4

FACE_L = WHEEL_INSET + WHEEL_THK              # 13  (left gearbox faceplate x)
FACE_R = BOARD_W - WHEEL_INSET - WHEEL_THK    # 87

NOTCH_Y1 = AXLE_Y - WHEEL_DIA / 2      # 48
NOTCH_Y2 = AXLE_Y + WHEEL_DIA / 2      # 80

CORNER_R = 16.0     # smooth-curve fillet radius, replacing the original's
                    # 16mm straight 45-deg chamfer -- same size, curved instead
ARC_SEGS = 16        # segments per quarter-circle-ish fillet; plenty smooth


def _corner_arc(cx, cy, start_deg, end_deg):
    """Points along a CORNER_R arc centered at (cx, cy), start_deg->end_deg."""
    pts = []
    for i in range(ARC_SEGS + 1):
        t = start_deg + (end_deg - start_deg) * i / ARC_SEGS
        rad = math.radians(t)
        pts.append((round(cx + CORNER_R * math.cos(rad), 4),
                    round(cy + CORNER_R * math.sin(rad), 4)))
    return pts


# Antenna notch REMOVED (XIAO revision): the XIAO nRF52840 Sense Plus's
# internal chip antenna needs no board cutout. The rear edge (y=BOARD_H) is
# now a single straight segment across the full width -- no ANT_NOTCH_*
# constants, no ANTENNA_NOTCH keepout.

# Perimeter walk: smooth front-left curve -> top edge -> smooth front-right
# curve -> right edge -> right wheel notch -> right edge -> rear-right corner
# (sharp, as in the original) -> plain rear edge (no antenna notch) ->
# rear-left corner (sharp) -> left edge -> left wheel notch -> left edge ->
# (closes back to the front-left curve's start).
BOARD_OUTLINE = (
    _corner_arc(CORNER_R, CORNER_R, 180, 270)                  # front-left smooth curve
    # NOTE: no explicit (BOARD_W-CORNER_R, 0) point here -- the front-right
    # arc's own first point (at start_deg=270) is exactly that coordinate, so
    # inserting it separately created a duplicate consecutive point, which
    # gen_pcb.py's outline walk turned into a zero-length Edge.Cuts segment
    # (KiCad DRC: "malformed outline / self-intersecting"). Removed.
    + _corner_arc(BOARD_W - CORNER_R, CORNER_R, 270, 360)      # front-right smooth curve
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
