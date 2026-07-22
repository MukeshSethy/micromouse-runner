"""Rev 8 (2026-07-21): add silkscreen pin-name labels at every user-facing
connector/switch/LED, so the physical board is self-documenting without a
schematic in hand. Purely additive F.SilkS text -- no electrical/routing
impact. Pin functions confirmed directly from board pad->net names, not
guessed (notably D1-D6: pad "1" nets end "_K" = CATHODE, pad "2" is the
anode -- opposite of the naive default LED-symbol assumption).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")

SIZE_SMALL = 0.5   # mm, for tight-pitch connector rows
THICK_SMALL = 0.08


def add_text(board, text, x_mm, y_mm, size_mm=SIZE_SMALL, thickness_mm=THICK_SMALL,
             rot_deg=0, layer=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)))
    t.SetLayer(layer if layer is not None else pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size_mm), pcbnew.FromMM(size_mm)))
    t.SetTextThickness(pcbnew.FromMM(thickness_mm))
    t.SetTextAngle(pcbnew.EDA_ANGLE(rot_deg, pcbnew.DEGREES_T))
    board.Add(t)


def main():
    board = pcbnew.LoadBoard(BOARD)

    # J5 (motor A): pins 1-6 at x=33.0..40.5 step 1.5, y=69.1, rot 0
    j5_labels = ["M+", "VC", "C1", "C2", "GN", "M-"]
    for i, lbl in enumerate(j5_labels):
        add_text(board, lbl, 33.0 + i * 1.5, 66.9, rot_deg=90)

    # J6 (motor B): pins 1-6 at x=67.0..59.5 step -1.5, y=70.0, rot 180 (mirrored order)
    j6_labels = ["M+", "VC", "C1", "C2", "GN", "M-"]
    for i, lbl in enumerate(j6_labels):
        add_text(board, lbl, 67.0 - i * 1.5, 72.2, rot_deg=90)

    # J1 (battery JST-XH): pin1=+ at (89,114), pin2=- at (91.5,114)
    add_text(board, "+", 89.0, 111.8)
    add_text(board, "-", 91.5, 111.8)

    # J10 (XT60): pin1=+ at (85.68,104.8), pin2=- at (92.88,104.8)
    add_text(board, "+", 85.68, 102.6)
    add_text(board, "-", 92.88, 102.6)

    # SW5 (PWR ALL): pad1=GND(OFF) at local -x, pad3=NC(ON) at local +x, center (6.0,116.4)
    add_text(board, "OFF", 3.0, 119.6)
    add_text(board, "ON", 8.5, 119.6)

    # SW6 (PWR MOTORS): pad1=GND(OFF), pad3=NC(ON), center (15.5,116.4)
    add_text(board, "OFF", 12.5, 119.6)
    add_text(board, "ON", 18.0, 119.6)

    # D1-D6 (IR emitter LEDs): pad "1" = cathode (K), pad "2" = anode (A) --
    # confirmed from board net names (EMIT_*_K on pad 1), not assumed.
    leds = {
        "D1": (21.43, 16.27, 90.0), "D2": (78.57, 16.27, 90.0),
        "D3": (16.972, 28.668, 45.0), "D4": (81.232, 26.872, -45.0),
        "D5": (15.0, 45.47, 90.0), "D6": (85.0, 42.93, -90.0),
    }
    for ref, (x, y, rot) in leds.items():
        # offset the two labels perpendicular to the lead axis so they don't
        # sit on top of the pads themselves
        import math
        rad = math.radians(rot)
        ox, oy = -math.sin(rad) * 2.2, -math.cos(rad) * 2.2
        add_text(board, "K", x + ox, y + oy, rot_deg=rot)
        add_text(board, "A", x - ox, y - oy, rot_deg=rot)

    pcbnew.SaveBoard(BOARD, board)
    print("added pin labels for J5, J6, J1, J10, SW5, SW6, D1-D6")


if __name__ == "__main__":
    main()
