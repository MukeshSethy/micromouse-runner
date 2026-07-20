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
#
# Rev-6 ANTENNA NOTCH (user: "no part of any component outside pcb
# dimensions... cut space in PCB for esp32 antenna if required"): the WROOM-1
# now sits FULLY on the board and its PCB-antenna end hangs over a U-shaped
# notch cut into the rear edge -- exactly the Espressif hardware-design-guide
# fallback ("cut off the base board on both sides of the antenna and below
# it"; hollowing out mid-board is explicitly prohibited, an edge cutout is
# the sanctioned form). Module body ends at y~119.45 (fp pos 106.7);
# the antenna section (last 6mm) spans the notch. Notch: x 24.9..45.6
# (antenna 18mm + ~1.3mm margin each side), y 113.8..120. Antenna tip at
# y=119.83 -- INSIDE the board dimensions (user req 8). Internal corners get the
# fab's >=1mm mill radius automatically; notch width 20.7mm >> 1mm min slot.
# Shifted +2.75mm toward centre (2-layer, user): moves the ESP off the left
# wheel (0.75mm -> ~3.5mm clearance). U3 + the antenna ribbon keepout move to
# match. (Full dead-centre would need relocating the buzzer that packs the
# rear-centre; this is the max shift the buzzer allows.)
# Centred (2-layer, user): ESP fully centred on the board, antenna notch dead-
# centre. Buzzer + USB-C + indicator LEDs relocated off the centre-rear to free
# it, using the space freed by removing the line array + mux.
ANT_NOTCH_X1, ANT_NOTCH_X2, ANT_NOTCH_Y = 39.65, 60.35, 113.8
BOARD_OUTLINE = [
    (CHAMF, 0), (BOARD_W - CHAMF, 0), (BOARD_W, CHAMF),
    (BOARD_W, NOTCH_Y1), (FACE_R, NOTCH_Y1), (FACE_R, NOTCH_Y2), (BOARD_W, NOTCH_Y2),
    (BOARD_W, BOARD_H),
    (ANT_NOTCH_X2, BOARD_H), (ANT_NOTCH_X2, ANT_NOTCH_Y),
    (ANT_NOTCH_X1, ANT_NOTCH_Y), (ANT_NOTCH_X1, BOARD_H),
    (0, BOARD_H),
    (0, NOTCH_Y2), (FACE_L, NOTCH_Y2), (FACE_L, NOTCH_Y1), (0, NOTCH_Y1),
    (0, CHAMF),
]

# Keep-out over the antenna notch (router margin source, like WHEEL_NOTCHES)
ANTENNA_NOTCH = (ANT_NOTCH_X1, ANT_NOTCH_Y, ANT_NOTCH_X2, BOARD_H)

# Keep-out rectangles covering the notch volumes (router margin source);
# same shape the old interior slots protected, extended to the board edge.
# Rev 6: the ANTENNA notch joins this list -- semantically these are "board
# absence" rectangles and every routing/healing script derives its edge
# keepouts from this one name.
WHEEL_NOTCHES = [
    (0, NOTCH_Y1, FACE_L, NOTCH_Y2),
    (FACE_R, NOTCH_Y1, BOARD_W, NOTCH_Y2),
    ANTENNA_NOTCH,
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
