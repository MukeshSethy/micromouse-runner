"""Rev 8 silkscreen fixes (2026-07-21), per user render review:
  1. The old per-button "A"/"B"/"C" letters (at ~74/84/94, y=111.9) are
     leftovers from an earlier board revision where the buttons lived on the
     rear panel -- stale, nowhere near the current front-mounted buttons.
     Same for "RST" (frozen at the old RESET switch's old position, now
     sitting on top of "BATT 2S 8.4V MAX" instead of near SW4). Removed and
     replaced with fresh labels at each switch's actual current position.
  2. J5's pin labels were placed above the connector, directly under J5's
     own reference-designator text -> visual collision. Moved below, to
     match J6's placement.
  3. Every label add_pin_labels.py added (J1/J10 +/-, J5/J6 pin names,
     SW5/SW6 ON/OFF, D1-D6 A/K) used a uniform 0.5mm text -- too small per
     multiple user reports. Bumped to legible sizes (tight-pitch J5/J6 pin
     labels get less room than the rest).

Run in two steps (separate processes -- pcbnew's GetDrawings() iterator
goes stale after board.Add() calls within the same process, same issue hit
earlier this session with GetFootprints()):
    python fix_silk_labels.py step1
    python fix_silk_labels.py step2
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")


def set_size(t, size_mm, thickness_mm=None):
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size_mm), pcbnew.FromMM(size_mm)))
    t.SetTextThickness(pcbnew.FromMM(thickness_mm if thickness_mm else max(0.1, size_mm * 0.15)))


def add_text(board, text, x_mm, y_mm, size_mm, rot_deg=0, thickness_mm=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)))
    t.SetLayer(pcbnew.F_SilkS)
    set_size(t, size_mm, thickness_mm)
    t.SetTextAngle(pcbnew.EDA_ANGLE(rot_deg, pcbnew.DEGREES_T))
    board.Add(t)
    return t


def step1():
    board = pcbnew.LoadBoard(BOARD)

    STALE_POS = [(74.25, 111.9, "A"), (84.25, 111.9, "B"), (94.25, 111.9, "C"),
                 (67.1, 96.8, "RST")]
    removed = 0
    for d in board.GetDrawings():
        if not isinstance(d, pcbnew.PCB_TEXT):
            continue
        p = d.GetPosition()
        x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        for (sx, sy, stext) in STALE_POS:
            if d.GetText() == stext and abs(x - sx) < 0.1 and abs(y - sy) < 0.1:
                board.Remove(d)
                removed += 1
    print(f"removed {removed} stale button-letter/RST texts")

    add_text(board, "A", 44.45, 33.7, size_mm=2.0)
    add_text(board, "B", 53.25, 33.7, size_mm=2.0)
    add_text(board, "C", 63.25, 33.7, size_mm=2.0)
    add_text(board, "RST", 67.25, 108.0, size_mm=1.6)

    pcbnew.SaveBoard(BOARD, board)
    print("step1 saved", BOARD)


def step2():
    board = pcbnew.LoadBoard(BOARD)

    # move J5 pin labels below the connector (matches J6), enlarge
    for d in board.GetDrawings():
        if not isinstance(d, pcbnew.PCB_TEXT):
            continue
        p = d.GetPosition()
        x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        if abs(y - 66.9) < 0.05 and 32 <= x <= 41 and d.GetText() in (
                "M+", "VC", "C1", "C2", "GN", "M-"):
            d.SetPosition(pcbnew.VECTOR2I(p.x, pcbnew.FromMM(71.3)))
            set_size(d, 0.8)

    # J6 pin labels: already below the connector, just too small
    J6_LABELS = {("M+", 67.0, 72.2), ("VC", 65.5, 72.2), ("C1", 64.0, 72.2),
                 ("C2", 62.5, 72.2), ("GN", 61.0, 72.2), ("M-", 59.5, 72.2)}
    D_AK_POS = [
        (23.63, 16.27), (19.23, 16.27), (80.77, 16.27), (76.37, 16.27),
        (18.53, 30.22), (15.42, 27.11), (79.68, 28.43), (82.79, 25.32),
        (17.2, 45.47), (12.8, 45.47), (82.8, 42.93), (87.2, 42.93),
    ]
    for d in board.GetDrawings():
        if not isinstance(d, pcbnew.PCB_TEXT):
            continue
        p = d.GetPosition()
        x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        txt = d.GetText()
        if any(txt == t and abs(x - ex) < 0.15 and abs(y - ey) < 0.15
               for (t, ex, ey) in J6_LABELS):
            set_size(d, 0.8)
        elif txt in ("+", "-") and (abs(x - 85.68) < 0.1 or abs(x - 92.88) < 0.1
                                     or abs(x - 89.0) < 0.1 or abs(x - 91.5) < 0.1):
            set_size(d, 1.2)
        elif txt in ("ON", "OFF") and 115 <= y <= 121:
            set_size(d, 1.0)
        elif txt in ("A", "K") and any(
                abs(x - ex) < 0.1 and abs(y - ey) < 0.1 for (ex, ey) in D_AK_POS):
            set_size(d, 0.8)

    pcbnew.SaveBoard(BOARD, board)
    print("step2 saved", BOARD)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "step2":
        step2()
    else:
        step1()
