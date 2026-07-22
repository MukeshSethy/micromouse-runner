"""Rev 8 follow-up (2026-07-21): the first SMD switch choice (TL3301AF160QG,
via swap_switches_smd.py) turned out to be physically too wide for this
board's 10mm button pitch -- its ~11.2mm gull-wing lead span overlapped and
shorted adjacent SW1/SW2/SW3 pads (caught via DRC courtyard/shorting errors
before committing). This script swaps the CURRENTLY-PLACED TL3301 footprints
for the corrected part, C&K KMR221NGLFS (~5mm pad span, fits with margin).

Unlike swap_switches_smd.py, no position-offset math is needed here: TL3301's
anchor already sits at its true body center (its 4 pads are placed
symmetrically at +-4.55,+-2.25 around 0,0), and KMR2's anchor does too
(pads at +-2.05,+-0.8) -- so this is a straight swap at the same point.
Both footprints share the same pad-name scheme ("1","1","2","2"), so nets
carry over by name exactly as before.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import FP_DIR

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")

NEW_FP_LIB = "Button_Switch_SMD"
NEW_FP_NAME = "SW_Push_1P1T_NO_CK_KMR2"


def main():
    board = pcbnew.LoadBoard(BOARD)
    by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    lib_dir = os.path.join(FP_DIR, f"{NEW_FP_LIB}.pretty")

    for ref in ("SW1", "SW2", "SW3", "SW4"):
        old_fp = by_ref[ref]
        rot = old_fp.GetOrientation()
        pos = old_fp.GetPosition()
        assert old_fp.GetLayer() == pcbnew.F_Cu, f"{ref} unexpectedly not on F.Cu"

        net_by_padnum = {}
        for pad in old_fp.Pads():
            net_by_padnum.setdefault(pad.GetNumber(), pad.GetNet())
        assert set(net_by_padnum) == {"1", "2"}, f"{ref} unexpected pad numbers: {net_by_padnum}"

        board.Remove(old_fp)
        new_fp = pcbnew.FootprintLoad(lib_dir, NEW_FP_NAME)
        if new_fp is None:
            raise SystemExit(f"footprint not found: {NEW_FP_LIB}:{NEW_FP_NAME}")
        new_fp.SetReference(ref)
        new_fp.SetPosition(pos)
        new_fp.SetOrientation(rot)
        board.Add(new_fp)
        for pad in new_fp.Pads():
            pad.SetNet(net_by_padnum[pad.GetNumber()])
        print(f"{ref}: TL3301 -> KMR2 at ({pcbnew.ToMM(pos.x):.3f},{pcbnew.ToMM(pos.y):.3f}), "
              f"nets {[n.GetNetname() for n in net_by_padnum.values()]}")

    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
