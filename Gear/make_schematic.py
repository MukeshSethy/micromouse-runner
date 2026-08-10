"""
make_schematic.py - dimensioned 2D structural schematic (SVG, 1:1 at 6 px/mm).

Panel A  side elevation: the five parallel axle holes on one common axis line.
Panel B  lateral section through one wheel axle: the bearing / gear / wheel stack.
"""

import os

import config as K

S = 6.0                      # px per mm
ML, MR, MT = 95.0, 185.0, 88.0
XMIN, XMAX = -42.0, 42.0
W = (XMAX - XMIN) * S + ML + MR
A_BASE = MT + 36.0 * S       # screen y of ground line in panel A
A_H = A_BASE + 200.0
B_TOP = A_H + 60.0
H = B_TOP + 360.0

RED = "#e11a27"
BLK = "#000000"
GRY = "#808080"
FONT = "Aptos, Segoe UI, sans-serif"

out = []


def _wrap(s, n):
    words, lines, cur = s.split(" "), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def px(x):
    return ML + (x - XMIN) * S


def py(z):
    return A_BASE - z * S


def add(s):
    out.append(s)


def txt(x, y, s, size=9, anchor="middle", fill=BLK, weight="normal", rot=None):
    tr = ' transform="rotate(%s %.1f %.1f)"' % (rot, x, y) if rot else ""
    add('<text x="%.1f" y="%.1f" font-family="%s" font-size="%d" fill="%s"'
        ' text-anchor="%s" font-weight="%s"%s>%s</text>'
        % (x, y, FONT, size, fill, anchor, weight, tr, s))


def line(x1, y1, x2, y2, stroke=BLK, w=0.8, dash=None):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    add('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s"'
        ' stroke-width="%.2f"%s/>' % (x1, y1, x2, y2, stroke, w, d))


def circ(cx, cy, r, stroke=BLK, w=0.8, dash=None, fill="none"):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    add('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s" stroke="%s"'
        ' stroke-width="%.2f"%s/>' % (cx, cy, r, fill, stroke, w, d))


def rect(x, y, w_, h_, stroke=BLK, sw=0.8, fill="none", rx=0):
    add('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f"'
        ' fill="%s" stroke="%s" stroke-width="%.2f"/>'
        % (x, y, w_, h_, rx, fill, stroke, sw))


def hdim(x1, x2, y, label, tick=4.0):
    line(x1, y - tick, x1, y + tick, BLK, 0.6)
    line(x2, y - tick, x2, y + tick, BLK, 0.6)
    line(x1, y, x2, y, BLK, 0.6)
    txt((x1 + x2) / 2.0, y - 4.0, label, 9)


def vdim(y1, y2, x, label, tick=4.0):
    line(x - tick, y1, x + tick, y1, BLK, 0.6)
    line(x - tick, y2, x + tick, y2, BLK, 0.6)
    line(x, y1, x, y2, BLK, 0.6)
    txt(x + 5.0, (y1 + y2) / 2.0, label, 9, anchor="start")


# ============================================================ panel A
def panel_a():
    txt(ML, MT - 30, "A &#8212; SIDE ELEVATION (one side plate pair, viewed "
        "from outboard)", 12, anchor="start", fill=RED, weight="bold")
    txt(ML, MT - 16, "All %d axes are collinear on the wheel-axle line. "
        "Scale 1:1 at %.0f px/mm. Dimensions in mm."
        % (K.GEARS_PER_SIDE, S), 9, anchor="start", fill=GRY)

    # plate outline
    rect(px(-K.PL_X), py(K.PL_Z1), 2 * K.PL_X * S, (K.PL_Z1 - K.PL_Z0) * S,
         BLK, 1.4, rx=K.PL_R * S)

    # ground + axle centre line
    line(px(XMIN) - 10, py(0), px(XMAX) + 10, py(0), BLK, 1.2)
    for i in range(0, 46):
        gx = px(XMIN) - 10 + i * 12
        line(gx, py(0), gx - 6, py(0) + 6, BLK, 0.4)
    txt(px(XMAX) + 14, py(0) + 3, "GROUND", 8, anchor="start", fill=GRY)
    line(px(XMIN) - 4, py(K.AXLE_Z), px(XMAX) + 4, py(K.AXLE_Z),
         RED, 0.7, dash="10,3,2,3")

    # wheels
    for sx in (-1.0, 1.0):
        circ(px(sx * K.X_AXLE), py(K.AXLE_Z), K.WHEEL_DIA / 2.0 * S,
             GRY, 0.7, dash="4,3")

    axes = [(-K.X_AXLE, K.N_WHEEL, "AXLE", "&#8709;3 D live axle, 2x F683ZZ"),
            (0.0, K.N_MOTOR, "MOTOR", "N20+encoder, &#8709;3 D shaft"),
            (K.X_AXLE, K.N_WHEEL, "AXLE", "&#8709;3 D live axle, 2x F683ZZ")]
    if K.X_IDLER is not None:
        axes += [(-K.X_IDLER, K.N_IDLER, "IDLER", "&#8709;3 dowel"),
                 (K.X_IDLER, K.N_IDLER, "IDLER", "&#8709;3 dowel")]

    for (x, n, name, note) in axes:
        cx, cy = px(x), py(K.AXLE_Z)
        circ(cx, cy, K.MODULE * (n + 2) / 2.0 * S, BLK, 0.7)       # tip
        circ(cx, cy, K.MODULE * n / 2.0 * S, RED, 1.0, dash="6,3")  # pitch
        circ(cx, cy, K.AXLE_D / 2.0 * S, BLK, 1.0)                 # 3 mm bore
        line(cx - 9, cy, cx + 9, cy, BLK, 0.5)
        line(cx, cy - 9, cx, cy + 9, BLK, 0.5)
        # names/notes go in the axis table below, not on top of the circles
        # keep both lines inside the gap between the plate edge and the ground
        txt(cx, py(K.PL_Z0) + 12, "%s %dT" % (name.split()[0], n), 8,
            weight="bold")
        txt(cx, py(K.PL_Z0) + 23, "X = %+.2f" % x, 8, fill=RED)

    # motor slot
    import chassis_lib as C
    slot_x, slot_z = C.motor_slot_section()
    slot_x += K.MOT_SLOT_CL
    slot_z += K.MOT_SLOT_CL
    rect(px(-slot_x / 2.0), py(K.AXLE_Z + slot_z / 2.0),
         slot_x * S, slot_z * S, BLK, 0.7, rx=K.MOT_SLOT_R * S)

    # fastener holes
    for (x, z) in K.STANDOFF_PTS:
        circ(px(x), py(z), K.M2_CLEAR / 2.0 * S, BLK, 0.7)
        line(px(x) - 5, py(z), px(x) + 5, py(z), BLK, 0.4)
        line(px(x), py(z) - 5, px(x), py(z) + 5, BLK, 0.4)
    for (x, z) in K.TUBE_SCREW_PTS:
        circ(px(x), py(z), K.M2_CLEAR / 2.0 * S, BLK, 0.7)

    # dimension stack
    y1 = py(0) + 34
    if K.X_IDLER is None:
        spans = ((-K.X_AXLE, 0.0), (0.0, K.X_AXLE))
    else:
        spans = ((-K.X_AXLE, -K.X_IDLER), (-K.X_IDLER, 0.0),
                 (0.0, K.X_IDLER), (K.X_IDLER, K.X_AXLE))
    for (a, b) in spans:
        hdim(px(a), px(b), y1, "%.2f" % (b - a))
    hdim(px(-K.X_AXLE), px(K.X_AXLE), y1 + 26,
         "%.2f  WHEELBASE" % K.WHEELBASE)
    hdim(px(-K.PL_X), px(K.PL_X), y1 + 52, "%.2f  plate length" % (2 * K.PL_X))

    # axis table, in the gap between the two panels
    ty = y1 + 90
    txt(ML, ty, "AXIS TABLE", 9.5, anchor="start", weight="bold", fill=RED)
    cols = (0, 78, 156, 216, 292)
    hdr = ("X", "board y", "teeth", "tip &#8709;", "shaft / bearing")
    for c, h in zip(cols, hdr):
        txt(ML + c, ty + 15, h, 8, anchor="start", fill=GRY)
    line(ML, ty + 19, ML + 430, ty + 19, BLK, 0.5)
    for i, (x, n, name, note) in enumerate(sorted(axes)):
        r = ty + 32 + i * 13
        vals = ("%+.2f" % x, "%.2f" % (K.BOARD_MOTOR_Y + x), "%dT" % n,
                "%.2f" % (K.MODULE * (n + 2)), note)
        for c, v in zip(cols, vals):
            txt(ML + c, r, v, 8, anchor="start")

    xv = px(K.PL_X) + 26
    vdim(py(0), py(K.AXLE_Z), xv, "%.2f  axle line" % K.AXLE_Z)
    vdim(py(0), py(K.PL_Z0), xv + 52, "%.2f  clear" % K.PL_Z0)
    vdim(py(K.PL_Z0), py(K.PL_Z1), xv + 96, "%.2f" % (K.PL_Z1 - K.PL_Z0))


# ============================================================ panel B
def panel_b():
    y0 = B_TOP
    txt(ML, y0 - 26, "B &#8212; LATERAL SECTION THROUGH ONE WHEEL AXLE "
        "(robot centreline at Y = 0, left side shown)", 12,
        anchor="start", fill=RED, weight="bold")
    txt(ML, y0 - 12, "Both wheel axles use this identical stack. "
        "Y datum = robot centreline.", 9, anchor="start", fill=GRY)

    # scale panel B to whatever the lateral stack actually spans
    y_max = K.Y_WHEEL + K.WHEEL_W
    sy = (W - ML - 55.0) / y_max

    def bx(y):
        return ML + y * sy

    band = 80.0
    line(bx(0), y0, bx(0), y0 + band + 60, RED, 1.0, dash="10,3,2,3")
    txt(bx(0), y0 - 2, "&#8676; centreline", 8, anchor="start", fill=RED)

    items = [("motor cradle", 0.0, K.Y_TUBE, "#eddad1"),
             ("inner plate %.1f" % K.PLATE_IN_T, K.Y_TUBE, K.Y_IN_OUT,
              "#f9d1d3"),
             ("gear plane %.1f" % K.GEAR_FW, K.Y_GEAR, K.Y_GEAR + K.GEAR_FW,
              "#fbeed7"),
             ("wheel %.1f" % K.WHEEL_W, K.Y_WHEEL, K.Y_WHEEL + K.WHEEL_W,
              "#E0E0E0")]
    for (lbl, a, b, fill) in items:
        rect(bx(a), y0, (b - a) * sy, band, BLK, 0.9, fill=fill)
        cx, cy = (bx(a) + bx(b)) / 2.0, y0 + band / 2.0
        txt(cx, cy + 3, lbl, 8.5, rot="-90")
        txt(bx(a), y0 + band + 12, "%.2f" % a, 7.5, fill=RED)
    txt(bx(K.Y_WHEEL + K.WHEEL_W), y0 + band + 12,
        "%.2f" % (K.Y_WHEEL + K.WHEEL_W), 7.5, fill=RED)

    # the axle itself
    rect(bx(K.Y_AXLE_IN), y0 + band + 34,
         K.AXLE_LEN * sy, 12, BLK, 1.0, fill="#CCCCCC")
    txt(bx(K.Y_AXLE_IN) + K.AXLE_LEN * sy / 2.0, y0 + band + 43,
        "&#8709;3 D live axle, L = %.1f" % K.AXLE_LEN, 8)

    notes = [
        "Motor faceplate Y = %.2f is PCB-DERIVED (board x = %.0f / %.0f on "
        "micromouse-pcb-simplified.kicad_pcb). Do not move it."
        % (K.Y_MOTOR_FACE, K.MOTOR_BOARD_X, K.BOARD_W - K.MOTOR_BOARD_X),
        "All three gears share ONE plane, Y %.2f..%.2f - the N20's 10 mm "
        "shaft is long enough that the pinion needs no separate plane."
        % (K.Y_GEAR, K.Y_GEAR + K.GEAR_FW),
        "F683ZZ #1 pressed into the inner plate, flange counterbored on the "
        "INBOARD face, inner race flush at Y = %.2f" % K.Y_IN_OUT,
        "F683ZZ #2 pressed into the outer plate, flange counterbored 1.0 deep "
        "from the OUTBOARD face so the rotating hub clears it",
        "0.5 shim between the inner-plate race and the axle gear; 0.8 shim "
        "between the outer-plate race and the wheel hub",
        "Deck ledge tapped M3 at X = +/-%.2f, Y = %.2f - lands under the "
        "PCB's H1..H4. PCB underside sits at Z = %.2f."
        % (K.DECK_HOLE_X, K.DECK_LEDGE_Y, K.BOARD_Z),
        "Wheel is the mini-sumo wheel measured from miniSumoWheel.3mf: "
        "&#8709;%.1f rolling (silicone in a &#8709;%.2f channel), %.2f wide, "
        "6 x &#8709;%.2f on a &#8709;%.2f bolt circle, &#8709;%.2f bore."
        % (K.WHEEL_DIA, K.WHEEL_CHAN_D, K.WHEEL_W, K.WHEEL_BC_HOLE,
           2 * K.WHEEL_BC_R, K.WHEEL_BORE),
        "Motor cradle is SPLIT on the axle plane and bolted: both halves print "
        "trough-up with no supports, and the motors drop in rather than being "
        "threaded through a sealed bore.",
        "Overall track over the wheel hubs = %.2f" % K.TRACK_OUTER,
    ]
    row = 0
    for n in notes:
        for j, seg in enumerate(_wrap(n, 118)):
            txt(ML + (0 if j == 0 else 10), y0 + band + 74 + row * 13,
                ("&#8226; " if j == 0 else "") + seg, 8.5, anchor="start")
            row += 1
        row += 0.35


def main():
    add('<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" '
        'viewBox="0 0 %.0f %.0f">' % (W, H, W, H))
    rect(0, 0, W, H, "none", 0, fill="#ffffff")
    txt(W / 2.0, 24, "Micromouse 4WD %.2f:1 Drivetrain &#8212; Parallel Axle "
        "Mounting Layout" % K.RATIO, 15, weight="bold")
    train = ("%dT &#8594; %dT" % (K.N_MOTOR, K.N_WHEEL) if K.N_IDLER is None
             else "%dT &#8594; %dT &#8594; %dT"
             % (K.N_MOTOR, K.N_IDLER, K.N_WHEEL))
    txt(W / 2.0, 40, "Module 0.5 / 20&#176; involute / POM &#183; %s "
        "(%d gears/side) &#183; registered to xiao 2-layer PCB "
        "&#183; 2026-08-10" % (train, K.GEARS_PER_SIDE), 9, fill=GRY)
    panel_a()
    panel_b()
    add('</svg>')

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "parallel_axle_layout.svg")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("wrote %s (%.1f kB)" % (p, os.path.getsize(p) / 1024.0))


if __name__ == "__main__":
    main()
