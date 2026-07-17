"""Single source of truth for the board's mechanical geometry.

build_pcb.py (placement) and route_loaded.py (routing) BOTH import from here.
History: the two files carried private copies of the axle position, wheel
slots and mounting holes, and every mechanical revision desynced them -- in
rev 5 the router was blocking phantom keep-outs where the USB cluster now
lives while leaving the real bracket holes unprotected. Never duplicate
these numbers again.
"""

BOARD_W = 100
BOARD_H = 120   # +6 rev-5c: the rear service panel needed a real fan-out band
CX = BOARD_W / 2

AXLE_Y = 84
WHEEL_THK = 9
WHEEL_DIA = 32
WHEEL_INSET = 4
CHAMF = 16

FACE_L = WHEEL_INSET + WHEEL_THK              # 13  (left gearbox faceplate x)
FACE_R = BOARD_W - WHEEL_INSET - WHEEL_THK    # 87

NOTCH_Y1 = AXLE_Y - WHEEL_DIA / 2      # 68
NOTCH_Y2 = AXLE_Y + WHEEL_DIA / 2      # 100

# Rev-5.3: the wheel openings are EDGE NOTCHES, not interior slots -- the
# 4mm outboard strips were removed (user request) so wheel/tyre width is no
# longer constrained by the board. Notch floors sit at the gearbox
# faceplates (x=13 / x=87).
BOARD_OUTLINE = [
    (CHAMF, 0), (BOARD_W - CHAMF, 0), (BOARD_W, CHAMF),
    (BOARD_W, NOTCH_Y1), (FACE_R, NOTCH_Y1), (FACE_R, NOTCH_Y2), (BOARD_W, NOTCH_Y2),
    (BOARD_W, BOARD_H), (0, BOARD_H),
    (0, NOTCH_Y2), (FACE_L, NOTCH_Y2), (FACE_L, NOTCH_Y1), (0, NOTCH_Y1),
    (0, CHAMF),
]

# Keep-out rectangles covering the notch volumes (router margin source);
# same shape the old interior slots protected, extended to the board edge.
WHEEL_NOTCHES = [
    (0, NOTCH_Y1, FACE_L, NOTCH_Y2),
    (FACE_R, NOTCH_Y1, BOARD_W, NOTCH_Y2),
]

# Motor body + bracket keep-out rectangles (components stay out; tracks OK)
MOTOR_KEEPOUTS = [
    (FACE_L, AXLE_Y - 6, FACE_L + 33, AXLE_Y + 6),
    (FACE_R - 33, AXLE_Y - 6, FACE_R, AXLE_Y + 6),
    (FACE_L, AXLE_Y - 13.3, FACE_L + 12.5, AXLE_Y + 13.3),
    (FACE_R - 12.5, AXLE_Y - 13.3, FACE_R, AXLE_Y + 13.3),
]

# Mounting holes: (x, y, radius_mm). UKMARS/Pololu bracket pattern (D3.2 NPTH,
# 18.0 c-c, 4.25mm inboard of each faceplate) + the front castor.
MOUNT_HOLES = (
    [(FACE_L + 4.25, AXLE_Y - 9, 1.6), (FACE_L + 4.25, AXLE_Y + 9, 1.6),
     (FACE_R - 4.25, AXLE_Y - 9, 1.6), (FACE_R - 4.25, AXLE_Y + 9, 1.6),
     (CX, 4, 1.5)]
)
