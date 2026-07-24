"""Compute JLC-correct placement (Mid X/Y/Rotation/Layer) straight from the
board via pcbnew -- kicad-cli's own `pcb export pos` is NOT sufficient for
JLC assembly, and this replaces it as the CPL source for export_jlcpcb.py.

MUST run under KiCad's bundled Python (it ships the pcbnew module; a plain
system `python` cannot import it):
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" gen_jlc_positions.py

Why kicad-cli's raw pos export is wrong for THT parts (verified against this
board, 2026-07-21):
  kicad-cli reports each footprint's KiCad *anchor* point, not the physical
  center of the part. For SMD footprints the anchor already sits at the true
  pad-center by KiCad convention, so passing it through is correct. Many THT
  library footprints anchor wherever the library author put it -- e.g. this
  board's own "Button_Switch_THT:SW_PUSH_6mm": its F.CrtYd box is local
  X[-1.5,8] Y[-1.5,6], centered at local (3.25, 2.25) -- NOT at the (0,0)
  anchor kicad-cli reports. JLC's pick-and-place needs the real body center,
  so THT parts are recomputed from the copper-pad bounding box instead.

Why bottom-side rotation isn't just "kicad_rotation": JLC defines Rotation
"as viewed from above the component". A bottom-side footprint's stored
KiCad orientation is already the mirrored view, so the correct JLC value is
(180 - orientation) -- coincides with orientation+180 only when orientation
is itself a multiple of 180, which is why plain passthrough looked "mostly
right" for this board's many rot=0 bottom passives but is not the general
rule (see e.g. R81 at 270 deg, C8 at 90 deg -- both map to themselves under
this formula, not under a flat +180).

ROTATION_CORRECTIONS below covers packages whose 0 deg reference differs
between KiCad's library footprint and JLC's own mounter library, independent
of the above -- restricted to the subset that matches a footprint actually
used on this board. Sourced from the community-maintained
bennymeg/Fabrication-Toolkit plugins/transformations.csv (MIT licensed);
each entry that fires here was cross-checked against this board's before/
after diff and confirmed to reproduce the same, expected correction.
"""
import csv
import math
import os
import re

import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PCB = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
OUT = os.path.join(BASE, "fab", "micromouse-pcb-simplified.jlc-positions.csv")

ROTATION_CORRECTIONS = [
    (re.compile(r"^CP_Elec_"), 180),      # C30 (electrolytic cap)
    (re.compile(r"^SOT-23-6"), 180),      # U7 -- falls under the generic SOT-23 rule below too;
                                           # listed explicitly since there's no dedicated upstream
                                           # 6-pin entry (flag for re-check against JLC's preview)
    (re.compile(r"^SOT-23"), 180),        # Q1, Q16-18, Q28-33 (3-pin SOT-23)
    (re.compile(r"^TSOT-23"), 180),       # U1
    (re.compile(r"^SSOP-"), 270),         # U2
]


def rotation_offset(fp_name):
    for pat, deg in ROTATION_CORRECTIONS:
        if pat.match(fp_name):
            return deg
    return 0.0


def _cast(item):
    if hasattr(pcbnew, "Cast_to_FOOTPRINT"):
        return pcbnew.Cast_to_FOOTPRINT(item)
    return item.Cast()


def _pad_bbox_center(pads):
    bbox = pads[0].GetBoundingBox()
    for p in pads:
        bbox.Merge(p.GetBoundingBox())
    return bbox.GetCenter()


def footprint_position(fp):
    """World-frame (position, rotation_deg): anchor for SMD, true pad-bbox
    center for THT (rotation-aware, since an axis-aligned world-frame bbox
    of individually-rotated pads is only meaningful at 0/90/180/270 deg)."""
    is_smd = bool(fp.GetAttributes() & pcbnew.FP_SMD)
    rot = fp.GetOrientation().AsDegrees()
    if is_smd:
        return fp.GetPosition(), rot

    pads = fp.Pads()
    if not pads:
        return fp.GetPosition(), rot

    if abs(rot % 90.0) > 1e-6:
        dup = _cast(fp.Duplicate(False))
        dup.SetOrientationDegrees(0)
        center = _pad_bbox_center(dup.Pads())
        raw = dup.GetPosition()  # Duplicate() doesn't move the anchor
        rel = (center[0] - raw[0], center[1] - raw[1])
        # KiCad's internal Y-down frame makes this the -rot rotation matrix,
        # not the textbook +rot one -- confirmed against this board's own
        # D3/D4/Q4/Q5 (45/315 deg mounted sensors), the only footprints where
        # the sign is even observable (everything else sits at a 90 deg
        # multiple, where +rot and -rot agree).
        s, c = math.sin(rot * math.pi / 180.0), math.cos(rot * math.pi / 180.0)
        rel = (rel[0] * c + rel[1] * s, -rel[0] * s + rel[1] * c)
        return (raw[0] + rel[0], raw[1] + rel[1]), rot

    return _pad_bbox_center(pads), rot


def footprint_name_of(fp):
    try:
        return str(fp.GetFPID().GetFootprintName())
    except AttributeError:
        return str(fp.GetFPID().GetLibItemName())


def main():
    board = pcbnew.LoadBoard(PCB)
    aux = board.GetDesignSettings().GetAuxOrigin()

    rows = [["Ref", "PosX", "PosY", "Rot", "Side"]]
    for fp in board.GetFootprints():
        if fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES:
            continue
        pos, rot = footprint_position(fp)
        x = (pos[0] - aux[0]) / 1e6
        y = (pos[1] - aux[1]) * -1.0 / 1e6  # JLC Y is up; KiCad internal Y is down

        is_bottom = fp.GetLayer() == pcbnew.B_Cu
        if is_bottom:
            rot = 180.0 - rot  # JLC rotation is "as viewed from above"
        rot = (rot + rotation_offset(footprint_name_of(fp))) % 360.0

        rows.append([fp.GetReference(), f"{x:.4f}", f"{y:.4f}", f"{rot:.4f}",
                     "Bottom" if is_bottom else "Top"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        csv.writer(f).writerows(rows)
    print(f"wrote {len(rows) - 1} placements -> {OUT}")


if __name__ == "__main__":
    main()
