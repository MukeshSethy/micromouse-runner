"""Overnight completion pass on top of the user's manually-placed + Freerouting
-routed board. Loads the CURRENT saved .kicad_pcb as-is (never re-runs
build_pcb.py -- that would clobber the user's manual placement edits), then:

  1. Closes the one remaining unrouted long-haul connection Freerouting left
     (WALL_SL_SENSE: Q6/R21's local cluster was connected to each other but
     never routed out to U3's ADC pin, a ~62mm span).
  2. Reports on GND zone fill/fragmentation (handled by a separate script,
     gnd_stitch_xiao.py, run after this one).

Same load()/retry_edge() pattern as heal_xiao_stragglers.py (already proven
on this exact board earlier this session).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")


def load():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
    g.setup_design_rules()
    g.LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
    g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
    g._nets = {}
    for code, ni in g.board.GetNetsByNetcode().items():
        if ni.GetNetname():
            g._nets[ni.GetNetname()] = ni
    g._outline_pts = list(BOARD_OUTLINE)
    g._extra_keepouts = []
    for (sx1, sy1, sx2, sy2) in WHEEL_NOTCHES:
        g._extra_keepouts.append((sx1 - 0.6, sy1 - 0.6, sx2 + 0.6, sy2 + 0.6))
    for (hx, hy, hr) in MOUNT_HOLES:
        m = hr + 0.75
        g._extra_keepouts.append((hx - m, hy - m, hx + m, hy + m))
    g._pads_geo_cache = None
    g._track_segs, g._vias = [], []
    for t in g.board.GetTracks():
        net = t.GetNet().GetNetname()
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            g._vias.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), net,
                            pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        elif t.GetClass() == "PCB_TRACK":
            a, b = t.GetStart(), t.GetEnd()
            g._track_segs.append(((pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)),
                                  (pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)), net,
                                  pcbnew.ToMM(t.GetWidth()) / 2, t.GetLayer()))
    return g


def main():
    g = load()
    # Free end of the WALL_SL_SENSE stub (a via, per direct board query) ->
    # U3's ADC pad for this channel.
    a = (21.8669, 40.3212)
    b = (58.255, 106.9825)
    routed = False
    for (width, clr, grid, maxexp) in (
        (0.25, 0.18, 0.2, 400000),
        (0.25, 0.15, 0.15, 600000),
        (0.2, 0.15, 0.1, 800000),
        (0.2, 0.13, 0.1, 1000000),
    ):
        if g.retry_edge("WALL_SL_SENSE", a, b, width_mm=width, clearance_mm=clr,
                         grid_mm=grid, max_expansions=maxexp):
            routed = True
            print(f"OK WALL_SL_SENSE routed at width={width} clr={clr} grid={grid}")
            break
        else:
            print(f"  attempt width={width} clr={clr} grid={grid}: no path")
    if not routed:
        print("FAILED to route WALL_SL_SENSE -- needs manual attention")
    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
