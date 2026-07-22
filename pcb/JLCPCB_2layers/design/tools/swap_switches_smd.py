"""Rev 8 (2026-07-21): renumber SW1-4 and swap their footprint THT -> SMD, IN
PLACE on the live, already-routed board -- do NOT run build_pcb.py (see
PROJECT_NOTES.md: it regenerates placement from scratch and clobbers the
board's hand-tuned routing). This script only touches the 4 switch
footprints; every other footprint/track/via/zone is left untouched.

Renumber (pure designator rename, nets unchanged -- see build_schematic.py):
    old SW2 (RESET/ESP_EN)   -> SW4
    old SW3 (BTN_B/USER_BTN2) -> SW2
    old SW4 (BTN_C/USER_BTN3) -> SW3
    SW1 (BTN_A/USER_BTN) unchanged

Footprint swap: Button_Switch_THT:SW_PUSH_6mm -> Button_Switch_SMD:
SW_Push_1P1T_NO_E-Switch_TL3301NxxxxxG (PTS645VL582LFS went out of stock;
TL3301AF160QG confirmed in stock at both JLCPCB/LCSC and lioncircuits.com).
Both footprints use the identical pad-name scheme (two pads named "1", two
named "2" -- the standard shorted-pair tactile-switch topology), so nets
carry over by pad NAME, verified pad-by-pad below rather than assumed.

Position: the THT footprint's anchor is NOT at its visual/body center (its
F.CrtYd box is local X[-1.5,8] Y[-1.5,6], center (3.25, 2.25) from anchor --
see the CPL work earlier this session). The new SMD footprint's anchor IS
its center (pads at +-4.55,+-2.25). To keep each button in the exact same
physical spot on the board, the new footprint is placed at
old_anchor + R(old_rotation)*(3.25, 2.25), not at old_anchor directly.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen, FP_DIR

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")

NEW_FP_LIB = "Button_Switch_SMD"
NEW_FP_NAME = "SW_Push_1P1T_NO_E-Switch_TL3301NxxxxxG"
CENTER_OFFSET_MM = (3.25, 2.25)   # THT anchor -> true body center, local frame

RENAME_CYCLE = [("SW4", "SW_TMP_RENAME"), ("SW2", "SW4"), ("SW3", "SW2"),
                ("SW_TMP_RENAME", "SW3")]


def world_offset(local_xy, rot_deg):
    lx, ly = local_xy
    s, c = math.sin(rot_deg * math.pi / 180.0), math.cos(rot_deg * math.pi / 180.0)
    # Same convention validated against this board in gen_jlc_positions.py.
    return (lx * c + ly * s, -lx * s + ly * c)


def main():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
    by_ref = {fp.GetReference(): fp for fp in g.board.GetFootprints()}

    # 1) renumber SW2/SW3/SW4 via a temp name to avoid ref collisions
    for old, new in RENAME_CYCLE:
        fp = by_ref.pop(old)
        fp.SetReference(new)
        by_ref[new] = fp
        print(f"renamed {old} -> {new}")

    # 2) swap footprint for SW1-4, preserving true center + rotation + nets
    lib_dir = os.path.join(FP_DIR, f"{NEW_FP_LIB}.pretty")
    old_pad_world = {}   # ref -> [(pad_num, (x_mm, y_mm), net_name), ...] for track cleanup
    for ref in ("SW1", "SW2", "SW3", "SW4"):
        old_fp = by_ref[ref]
        rot = old_fp.GetOrientation().AsDegrees()
        pos = old_fp.GetPosition()
        layer = old_fp.GetLayer()
        assert layer == pcbnew.F_Cu, f"{ref} unexpectedly not on F.Cu"

        net_by_padnum = {}
        pads_mm = []
        for pad in old_fp.Pads():
            net = pad.GetNet()
            net_by_padnum.setdefault(pad.GetNumber(), net)
            p = pad.GetPosition()
            pads_mm.append((pad.GetNumber(), (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)),
                            net.GetNetname()))
        old_pad_world[ref] = pads_mm
        assert set(net_by_padnum) == {"1", "2"}, f"{ref} unexpected pad numbers: {net_by_padnum}"

        dx, dy = world_offset(CENTER_OFFSET_MM, rot)
        new_pos = pcbnew.VECTOR2I(pos.x + pcbnew.FromMM(dx), pos.y + pcbnew.FromMM(dy))

        g.board.Remove(old_fp)
        new_fp = pcbnew.FootprintLoad(lib_dir, NEW_FP_NAME)
        if new_fp is None:
            raise SystemExit(f"footprint not found: {NEW_FP_LIB}:{NEW_FP_NAME}")
        new_fp.SetReference(ref)
        new_fp.SetPosition(new_pos)
        new_fp.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
        g.board.Add(new_fp)
        for pad in new_fp.Pads():
            pad.SetNet(net_by_padnum[pad.GetNumber()])
        print(f"{ref}: swapped footprint, center ({pcbnew.ToMM(pos.x):.3f},"
              f"{pcbnew.ToMM(pos.y):.3f}) -> ({pcbnew.ToMM(new_pos.x):.3f},"
              f"{pcbnew.ToMM(new_pos.y):.3f}), rot {rot} deg, "
              f"nets {[n.GetNetname() for n in net_by_padnum.values()]}")

    # 3) clear routing that terminated at the OLD pad locations, so the healer
    #    (heal_all.py) has a clean unconnected pad to route to.
    #    - dedicated 2-terminal signal nets (USER_BTN/2/3, ESP_EN): remove
    #      every track/via on that net outright (nothing else uses them).
    #    - GND: it's the shared pour net -- only remove the specific stub
    #      segment(s) that touch an OLD pad position (tight 0.2mm radius),
    #      leaving the rest of the GND network completely untouched.
    signal_nets = set()
    gnd_old_positions = []
    for ref, pads in old_pad_world.items():
        for (_num, xy, netname) in pads:
            if netname == "GND":
                gnd_old_positions.append(xy)
            else:
                signal_nets.add(netname)

    removed = 0
    for t in list(g.board.GetTracks()):
        net = t.GetNet().GetNetname()
        if net in signal_nets:
            g.board.Remove(t)
            removed += 1
        elif net == "GND":
            a, b = t.GetStart(), t.GetEnd()
            a_mm = (pcbnew.ToMM(a.x), pcbnew.ToMM(a.y))
            b_mm = (pcbnew.ToMM(b.x), pcbnew.ToMM(b.y))
            if any(math.hypot(a_mm[0] - gx, a_mm[1] - gy) < 0.2 or
                   math.hypot(b_mm[0] - gx, b_mm[1] - gy) < 0.2
                   for (gx, gy) in gnd_old_positions):
                g.board.Remove(t)
                removed += 1
    print(f"removed {removed} stale track/via items on nets {sorted(signal_nets)} + GND stubs")

    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
