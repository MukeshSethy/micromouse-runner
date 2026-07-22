"""Compute Lion-Circuits-correct CPL positions directly from the board via
pcbnew. Sibling to gen_jlc_positions.py but for Lion Circuits' own,
differently-formatted centroid file -- see that script's docstring for the
full reasoning on why kicad-cli's raw `pcb export pos` isn't good enough on
its own (THT anchor != true body center).

MUST run under KiCad's bundled Python (has the pcbnew module):
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" gen_lion_positions.py

Where this DIFFERS from gen_jlc_positions.py, and why:
  - Position: same true-body-center logic (SMD=anchor, THT=pad-bbox-center,
    rotation-aware for non-90-multiple angles) -- that's a physical-reality
    correction, not a JLC-specific convention, so it applies here too.
  - Rotation: passed through RAW (no bottom-side 180-rot flip, no per-package
    rotation-correction table). Lion Circuits' own docs
    (lioncircuits.com/faq/pcb-assembly/what-is-centroid-file-aka-pick-and-place-file)
    only state "positive rotation = counterclockwise" -- the standard KiCad/
    math convention -- with no documented bottom-layer or per-footprint
    quirk table (unlike JLC's well-known mounter-library mismatches). Absent
    evidence of a Lion-specific quirk, inventing one would be a guess; their
    own KiCad export guide just says "export Pcbnew's Footprint Position
    File," implying raw KiCad rotation is what they expect.
  - Y axis: NOT flipped. Lion's guide directs users to KiCad's own default
    Footprint Position File export with no mention of flipping Y to match a
    Y-up convention (unlike JLC's documented Y-up expectation) -- so this
    keeps KiCad's native Y-down sign.
  ASSUMPTION FLAG: Lion's coordinate-origin and Y-axis convention are not
  explicitly documented anywhere public (checked 2026-07-21) -- this is the
  most defensible default given their docs, but sanity-check the first real
  Lion order's own placement/DFM preview before trusting it blindly.
"""
import csv
import math
import os

import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PCB = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
OUT = os.path.join(BASE, "fab", "micromouse-pcb.lion-positions.csv")


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
    """World-frame (position, rotation_deg) -- identical physical-center
    logic to gen_jlc_positions.py (see that file for the derivation and the
    board-specific courtyard verification behind it)."""
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
        raw = dup.GetPosition()
        rel = (center[0] - raw[0], center[1] - raw[1])
        s, c = math.sin(rot * math.pi / 180.0), math.cos(rot * math.pi / 180.0)
        rel = (rel[0] * c + rel[1] * s, -rel[0] * s + rel[1] * c)
        return (raw[0] + rel[0], raw[1] + rel[1]), rot

    return _pad_bbox_center(pads), rot


def main():
    board = pcbnew.LoadBoard(PCB)
    aux = board.GetDesignSettings().GetAuxOrigin()

    rows = [["Designator", "X Data", "Y Data", "Layer", "Rotation"]]
    for fp in board.GetFootprints():
        if fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES:
            continue
        pos, rot = footprint_position(fp)
        x = (pos[0] - aux[0]) / 1e6
        y = (pos[1] - aux[1]) / 1e6   # NOT flipped -- see module docstring
        is_bottom = fp.GetLayer() == pcbnew.B_Cu
        rot = rot % 360.0
        rows.append([fp.GetReference(), f"{x:.4f}", f"{y:.4f}",
                     "Bottom" if is_bottom else "Top", f"{rot:.4f}"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        csv.writer(f).writerows(rows)
    print(f"wrote {len(rows) - 1} placements -> {OUT}")


if __name__ == "__main__":
    main()
