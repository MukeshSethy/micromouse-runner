"""Project-local TCRT5000 footprint + 3D models (KiCad ships none -- checked
Sensor_Optical + OptoDevice; CNY70's square grid does NOT fit TCRT5000).

All numbers from the Vishay datasheet 83760 drawing (verified 2026-07-16):
  body 10.2 x 5.8 x 7.0mm; leads 0.95x0.4 flat, tip coined to D0.9;
  lead grid (origin = package center, X along the 10.2 length):
    collector (-2.75, +1.27)   anode   (+2.75, +1.27)   <- 5.5mm row
    emitter   (-2.325, -1.27)  cathode (+2.325, -1.27)  <- 4.65mm row
  two snap pegs: D2.5 holes at (0, +/-1.9), 3.8mm apart.
Pad NUMBERS follow the Isolator:PC817 base symbol used in the schematic:
  1 = LED anode, 2 = LED cathode, 3 = PT emitter, 4 = PT collector
(left half of the package = phototransistor, right half = LED; the LED dome
is blue-translucent, the PT dome black = the daylight filter).
Drills D1.1 (lead diagonal ~1.03), pads D2.0.
"""
import os
from gen_step_models import Step, wrl_box_file

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PRETTY = os.path.join(BASE, "n20.pretty")
SHAPES = os.path.join(BASE, "n20.3dshapes")

PADS = [  # num, x, y
    ("1", 2.75, 1.27),     # A
    ("2", 2.325, -1.27),   # K
    ("3", -2.325, -1.27),  # E
    ("4", -2.75, 1.27),    # C
]

pads = "\n".join(
    f'  (pad "{n}" thru_hole circle (at {x} {y}) (size 2.0 2.0) (drill 1.1) '
    f'(layers "*.Cu" "*.Mask"))' for (n, x, y) in PADS)
pegs = "\n".join(
    f'  (pad "" np_thru_hole circle (at 0 {y}) (size 2.5 2.5) (drill 2.5) '
    f'(layers "F&B.Cu" "*.Mask"))' for y in (1.9, -1.9))

fp = f"""(footprint "TCRT5000"
  (version 20240108)
  (generator "gen_tcrt5000_lib")
  (layer "F.Cu")
  (descr "Vishay TCRT5000 reflective optical sensor, 10.2x5.8x7.0mm, lead grid 5.5/4.65 x 2.54mm + 2x D2.5 snap pegs (datasheet 83760). Pads numbered per Isolator:PC817 (1=A 2=K 3=E 4=C). Right half = LED (blue dome), left half = phototransistor (black dome).")
  (attr through_hole)
  (fp_text reference "REF**" (at 0 -4.3) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
  (fp_text value "TCRT5000" (at 0 4.3) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
{pads}
{pegs}
  (fp_rect (start -5.1 -2.9) (end 5.1 2.9) (stroke (width 0.12) (type default)) (layer "F.Fab"))
  (fp_rect (start -5.35 -3.15) (end 5.35 3.15) (stroke (width 0.05) (type default)) (layer "F.CrtYd"))
  (fp_line (start 5.35 -3.15) (end 5.35 3.15) (stroke (width 0.3) (type default)) (layer "F.SilkS"))
  (fp_text user "LED" (at 3.6 -3.9) (layer "F.SilkS") (effects (font (size 0.7 0.7) (thickness 0.12))))
  (fp_text user "PT" (at -3.6 -3.9) (layer "F.SilkS") (effects (font (size 0.7 0.7) (thickness 0.12))))
  (model "${{KIPRJMOD}}/n20.3dshapes/TCRT5000.wrl"
    (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
)
"""
with open(os.path.join(PRETTY, "TCRT5000.kicad_mod"), "w", newline="\n") as f:
    f.write(fp)
print("wrote n20.pretty/TCRT5000.kicad_mod")

# 3D: body box + two dome-ish stubs (box-true is enough for fit checks)
st = Step("TCRT5000")
st.box(-5.1, -2.9, 0.0, 5.1, 2.9, 6.3)      # molded body (shoulder height)
st.box(-3.9, -1.5, 6.3, -1.4, 1.5, 7.0)     # PT dome (black)
st.box(1.4, -1.5, 6.3, 3.9, 1.5, 7.0)       # LED dome (blue)
st.write(os.path.join(SHAPES, "TCRT5000.step"))
wrl_box_file(os.path.join(SHAPES, "TCRT5000.wrl"),
             [(-5.1, -2.9, 0.0, 5.1, 2.9, 6.3, "0.12 0.12 0.14"),
              (-3.9, -1.5, 6.3, -1.4, 1.5, 7.0, "0.05 0.05 0.05"),
              (1.4, -1.5, 6.3, 3.9, 1.5, 7.0, "0.25 0.35 0.75")])
