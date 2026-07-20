"""Generates the project-local N20 motor library: a pad-less MECHANICAL
footprint (fab outline + courtyard at true size) plus a hand-authored VRML 3D
model, so the motors render true-size in the 3D viewer. Stock KiCad ships NO
N20 motor library (checked: Motors.pretty holds one vibration motor), so this
is project-local by necessity.

Dimensions verified against Pololu's official micro-metal-gearmotor drawing
0J949 / datasheet 0J1487 (research pass 2026-07-15):
  gearbox 12.0 x 10.0 x 9.0 long (+0.7 faceplate, bulges to 13.6 near front)
  motor can: dia 12 flatted to 10, length 15.4 (HPCB)
  rear boss dia 5 x ~1; encoder board + magnet extension ~8 (VENDOR-DEPENDENT:
    Indian GA12-N20-EN style boards vary ~5-12 -- verify your unit)
  shaft: dia 3.0 D-flat, 10 protruding
Footprint origin = faceplate center, +X = shaft direction. KiCad VRML models
use 1 unit = 2.54mm (0.1 inch) -- everything below is divided by 2.54.
"""
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PRETTY = os.path.join(BASE, "n20.pretty")
SHAPES = os.path.join(BASE, "n20.3dshapes")
os.makedirs(PRETTY, exist_ok=True)
os.makedirs(SHAPES, exist_ok=True)

S = 2.54  # mm per VRML unit

def box(cx, cy, cz, dx, dy, dz, rgb):
    return f"""    Transform {{
      translation {cx/S:.4f} {cy/S:.4f} {cz/S:.4f}
      children Shape {{
        appearance Appearance {{ material Material {{ diffuseColor {rgb} }} }}
        geometry Box {{ size {dx/S:.4f} {dy/S:.4f} {dz/S:.4f} }}
      }}
    }}"""

def cyl_x(cx, cy, cz, dia, length, rgb):
    # cylinder along +X (VRML cylinders are Y-axis -> rotate about Z by -90deg)
    return f"""    Transform {{
      translation {cx/S:.4f} {cy/S:.4f} {cz/S:.4f}
      rotation 0 0 1 -1.5708
      children Shape {{
        appearance Appearance {{ material Material {{ diffuseColor {rgb} }} }}
        geometry Cylinder {{ radius {dia/2/S:.4f} height {length/S:.4f} }}
      }}
    }}"""

# Model: origin at faceplate center, +X = shaft. Z up; motor axis at z=+5
# (half the 10mm gearbox height -- the body sits ON the board via a bracket,
# so the model rests its 10mm face on z=0).
AXIS_Z = 5.0
parts = []
# shaft (steel)
parts.append(cyl_x(5.0, 0, AXIS_Z, 3.0, 10.0, "0.85 0.85 0.88"))
# faceplate (brass)
parts.append(box(-0.35, 0, AXIS_Z, 0.7, 12.0, 10.0, "0.78 0.65 0.25"))
# gearbox (brass, 12 wide x 10 high x 9 long; slight front bulge modeled flat)
parts.append(box(-0.7 - 4.5, 0, AXIS_Z, 9.0, 12.0, 10.0, "0.72 0.6 0.24"))
# motor can (silver flatted cylinder: cylinder dia 12 + boxes cheat the flats)
parts.append(cyl_x(-0.7 - 9.0 - 7.7, 0, AXIS_Z, 12.0, 15.4, "0.75 0.76 0.78"))
# rear boss (black plastic)
parts.append(cyl_x(-0.7 - 9.0 - 15.4 - 0.5, 0, AXIS_Z, 5.0, 1.0, "0.15 0.15 0.15"))
# encoder PCB + magnet disc (green board + dark disc, vendor-typical 8mm)
parts.append(box(-0.7 - 9.0 - 15.4 - 1.0 - 0.8, 0, AXIS_Z, 1.6, 14.0, 12.0, "0.05 0.35 0.15"))
parts.append(cyl_x(-0.7 - 9.0 - 15.4 - 1.0 - 1.6 - 2.5, 0, AXIS_Z, 9.0, 5.0, "0.2 0.2 0.2"))

wrl = "#VRML V2.0 utf8\n# N20 micro metal gearmotor with encoder (project-generated)\nGroup { children [\n" + "\n".join(parts) + "\n] }\n"
with open(os.path.join(SHAPES, "N20_Motor_Encoder.wrl"), "w", newline="\n") as f:
    f.write(wrl)

# Footprint: pad-less mechanical reference. Outline on F.Fab, courtyard covers
# body + encoder (33.4 long x 13.6 widest), shaft direction marked.
TOTAL_BACK = 0.7 + 9.0 + 15.4 + 1.0 + 1.6 + 5.0   # faceplate..magnet = 32.7
fp = f"""(footprint "N20_Motor_Encoder"
  (version 20240108)
  (generator "gen_n20_lib")
  (layer "F.Cu")
  (descr "N20 micro metal gearmotor + encoder, MECHANICAL reference only (no pads). Origin=faceplate center, +X=shaft. Dims per Pololu 0J949; encoder extension vendor-dependent.")
  (attr exclude_from_pos_files exclude_from_bom)
  (fp_text reference "REF**" (at 0 -8.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
  (fp_text value "N20_Motor_Encoder" (at 0 8.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
  (fp_rect (start -{TOTAL_BACK:.2f} -6.8) (end 0 6.8) (stroke (width 0.12) (type default)) (layer "F.Fab"))
  (fp_rect (start 0 -1.5) (end 10 1.5) (stroke (width 0.12) (type default)) (layer "F.Fab"))
  (fp_rect (start -{TOTAL_BACK + 0.5:.2f} -7.05) (end 10.25 7.05) (stroke (width 0.05) (type default)) (layer "F.CrtYd"))
  (fp_text user "shaft ->" (at 5 -3) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
  (model "${{KIPRJMOD}}/n20.3dshapes/N20_Motor_Encoder.wrl"
    (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
)
"""
with open(os.path.join(PRETTY, "N20_Motor_Encoder.kicad_mod"), "w", newline="\n") as f:
    f.write(fp)

print("wrote n20.pretty/N20_Motor_Encoder.kicad_mod + n20.3dshapes/N20_Motor_Encoder.wrl")
