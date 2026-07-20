"""Generate rev-6 project-local footprints into n20.pretty (+ simple box STEP
models into n20.3dshapes):

  BNO055      -- Bosch LGA-28 (3.8 x 5.2 x 1.13 mm). No stock KiCad footprint
                 exists for this package. Pad geometry lifted VERBATIM from the
                 Adafruit BNO055 breakout Eagle package (shipped on millions of
                 boards): corner/long-edge pads 0.25x0.475 mm, short-edge pads
                 0.375x0.25 mm, pitch 0.5 mm. Pin 1 at top-left corner
                 (x=-2.25, y=+1.5625 in Eagle Y-up => y=-1.5625 KiCad Y-down).
  SRP4020TA   -- Bourns 4.45 x 4.06 x 1.8 mm shielded power inductor.
                 Bourns recommended land: two 1.7 x 1.2 mm pads at +/-1.475 mm
                 (SRP4020TA datasheet land pattern: pad 1.7 W x 1.2 L,
                 gap 1.75 -> centers +/- (1.75/2 + 1.2/2) = +/-1.475).

Run with KiCad's python (pcbnew not required -- pure text emission).
"""
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "n20.pretty")
SHAPES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "n20.3dshapes")
os.makedirs(OUT, exist_ok=True)
os.makedirs(SHAPES, exist_ok=True)

# (pad, x_eagle, y_eagle, dx, dy) -- Eagle is Y-up; KiCad is Y-down => y flips.
BNO_PADS = [
    (1, -2.25, 1.5625, 0.25, 0.475), (2, -2.3125, 0.75, 0.375, 0.25),
    (3, -2.3125, 0.25, 0.375, 0.25), (4, -2.3125, -0.25, 0.375, 0.25),
    (5, -2.3125, -0.75, 0.375, 0.25), (6, -2.25, -1.5625, 0.25, 0.475),
    (7, -1.75, -1.5625, 0.25, 0.475), (8, -1.25, -1.5625, 0.25, 0.475),
    (9, -0.75, -1.5625, 0.25, 0.475), (10, -0.25, -1.5625, 0.25, 0.475),
    (11, 0.25, -1.5625, 0.25, 0.475), (12, 0.75, -1.5625, 0.25, 0.475),
    (13, 1.25, -1.5625, 0.25, 0.475), (14, 1.75, -1.5625, 0.25, 0.475),
    (15, 2.25, -1.5625, 0.25, 0.475), (16, 2.3125, -0.75, 0.375, 0.25),
    (17, 2.3125, -0.25, 0.375, 0.25), (18, 2.3125, 0.25, 0.375, 0.25),
    (19, 2.3125, 0.75, 0.375, 0.25), (20, 2.25, 1.5625, 0.25, 0.475),
    (21, 1.75, 1.5625, 0.25, 0.475), (22, 1.25, 1.5625, 0.25, 0.475),
    (23, 0.75, 1.5625, 0.25, 0.475), (24, 0.25, 1.5625, 0.25, 0.475),
    (25, -0.25, 1.5625, 0.25, 0.475), (26, -0.75, 1.5625, 0.25, 0.475),
    (27, -1.25, 1.5625, 0.25, 0.475), (28, -1.75, 1.5625, 0.25, 0.475),
]


def pad_smd(num, x, y, w, h):
    return (f'\t(pad "{num}" smd roundrect (at {x} {y}) (size {w} {h}) '
            f'(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))\n')


def fp_header(name, descr):
    return (f'(footprint "{name}"\n\t(version 20240108)\n\t(generator "gen_rev6_libs")\n'
            f'\t(layer "F.Cu")\n\t(descr "{descr}")\n'
            f'\t(attr smd)\n')


def text_items(refname, y_ref, y_val):
    return (f'\t(fp_text reference "{refname}" (at 0 {y_ref}) (layer "F.SilkS")\n'
            f'\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))\n\t)\n'
            f'\t(fp_text value "VAL" (at 0 {y_val}) (layer "F.Fab")\n'
            f'\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))\n\t)\n')


def rect(layer, x1, y1, x2, y2, w=0.1):
    return (f'\t(fp_rect (start {x1} {y1}) (end {x2} {y2}) '
            f'(stroke (width {w}) (type solid)) (fill none) (layer "{layer}"))\n')


def line(layer, x1, y1, x2, y2, w=0.12):
    return (f'\t(fp_line (start {x1} {y1}) (end {x2} {y2}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}"))\n')


def circle(layer, cx, cy, r, w=0.12):
    return (f'\t(fp_circle (center {cx} {cy}) (end {cx + r} {cy}) '
            f'(stroke (width {w}) (type solid)) (fill solid) (layer "{layer}"))\n')


def box_step(path, dx, dy, dz):
    """Minimal rectangular STEP solid centered at origin, dz tall."""
    x, y = dx / 2, dy / 2
    v = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0),
         (-x, -y, dz), (x, -y, dz), (x, y, dz), (-x, y, dz)]
    lines = ["ISO-10303-21;", "HEADER;",
             "FILE_DESCRIPTION(('box'),'2;1');",
             "FILE_NAME('box.step','2026-07-17',(''),(''),'','','');",
             "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));", "ENDSEC;", "DATA;"]
    n = [0]

    def add(s):
        n[0] += 1
        lines.append(f"#{n[0]}={s};")
        return n[0]

    pts = [add(f"CARTESIAN_POINT('',({a:.3f},{b:.3f},{c:.3f}))") for (a, b, c) in v]
    # 6 faces as simple polygons via ADVANCED_BREP is heavy; emit a faceted
    # shell (MANIFOLD_SOLID_BREP is overkill for a viewer box) -- use the
    # same trick as gen_step_models.py: closed shell of POLY_LOOPs.
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    face_ids = []
    for f in faces:
        loop_pts = [pts[i] for i in f]
        pl = add("POLYLINE('',(" + ",".join(f"#{p}" for p in (loop_pts + [loop_pts[0]])) + "))")
        # STEP viewers in KiCad accept faceted BREP via POLY_LOOP:
        vloop = add("POLY_LOOP('',(" + ",".join(f"#{p}" for p in loop_pts) + "))")
        fb = add(f"FACE_OUTER_BOUND('',#{vloop},.T.)")
        pln_pt = pts[f[0]]
        ax = add(f"AXIS2_PLACEMENT_3D('',#{pln_pt},$,$)")
        pl2 = add(f"PLANE('',#{ax})")
        face_ids.append(add(f"ADVANCED_FACE('',(#{fb}),#{pl2},.T.)"))
    sh = add("CLOSED_SHELL('',(" + ",".join(f"#{i}" for i in face_ids) + "))")
    br = add(f"MANIFOLD_SOLID_BREP('box',#{sh})")
    ctx = add("(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#1))GLOBAL_UNIT_ASSIGNED_CONTEXT(())REPRESENTATION_CONTEXT('',''))")
    add(f"ADVANCED_BREP_SHAPE_REPRESENTATION('',(#{br}),#{ctx})")
    lines += ["ENDSEC;", "END-ISO-10303-21;"]
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(lines))


# ---------------- BNO055 LGA-28 ----------------
s = fp_header("BNO055", "Bosch BNO055 LGA-28 3.8x5.2mm; pads verbatim from the Adafruit breakout Eagle package")
s += text_items("REF**", -3.4, 3.4)
# body: 3.8 wide (x) x 5.2 long (y)? Eagle pads: x spans +/-2.3 -> the 5.2mm
# axis is X here, 3.8mm is Y. Body rect 5.2 x 3.8 in this orientation.
s += rect("F.Fab", -2.6, -1.9, 2.6, 1.9, 0.1)
s += rect("F.CrtYd", -2.85, -2.15, 2.85, 2.15, 0.05)
# silk: two long-edge strokes clear of pads + pin-1 dot OUTSIDE the body,
# top-left (pin 1 pad at (-2.25, -1.5625) after Y flip)
s += line("F.SilkS", -2.72, -1.95, -2.72, -1.0)
s += line("F.SilkS", 2.72, -1.95, 2.72, 1.95)
s += circle("F.SilkS", -3.1, -1.5625, 0.12)
for (num, ex, ey, dx, dy) in BNO_PADS:
    s += pad_smd(num, ex, -ey, dx, dy)   # Y flip Eagle->KiCad
s += (f'\t(model "${{KIPRJMOD}}/n20.3dshapes/BNO055.step"\n'
      f'\t\t(offset (xyz 0 0 0))\n\t\t(scale (xyz 1 1 1))\n\t\t(rotate (xyz 0 0 0))\n\t)\n')
s += ")\n"
with open(os.path.join(OUT, "BNO055.kicad_mod"), "w", newline="\n") as f:
    f.write(s)
box_step(os.path.join(SHAPES, "BNO055.step"), 5.2, 3.8, 1.13)

# ---------------- Bourns SRP4020TA ----------------
s = fp_header("L_Bourns_SRP4020TA", "Bourns SRP4020TA shielded inductor 4.45x4.06x1.8mm; land per Bourns datasheet (1.2x1.7 pads, 1.75 gap)")
s += text_items("REF**", -3.0, 3.0)
s += rect("F.Fab", -2.225, -2.03, 2.225, 2.03, 0.1)
s += rect("F.CrtYd", -2.5, -2.3, 2.5, 2.3, 0.05)
s += line("F.SilkS", -2.35, -2.15, 2.35, -2.15)
s += line("F.SilkS", -2.35, 2.15, 2.35, 2.15)
s += pad_smd(1, -1.475, 0, 1.2, 1.7)
s += pad_smd(2, 1.475, 0, 1.2, 1.7)
s += (f'\t(model "${{KIPRJMOD}}/n20.3dshapes/SRP4020TA.step"\n'
      f'\t\t(offset (xyz 0 0 0))\n\t\t(scale (xyz 1 1 1))\n\t\t(rotate (xyz 0 0 0))\n\t)\n')
s += ")\n"
with open(os.path.join(OUT, "L_Bourns_SRP4020TA.kicad_mod"), "w", newline="\n") as f:
    f.write(s)
box_step(os.path.join(SHAPES, "SRP4020TA.step"), 4.45, 4.06, 1.8)

print("wrote BNO055.kicad_mod + L_Bourns_SRP4020TA.kicad_mod + STEP boxes")
