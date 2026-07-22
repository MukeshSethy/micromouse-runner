"""One-off cleanup after the switch footprint swaps: heal_all.py's earlier
GND fragment-bridging pass (run while SW1-4 still had the oversized,
overlapping TL3301 footprint) dropped 5 GND vias that land inside a keepout
zone -- invalid placements, caught by DRC's "items not allowed (keepout
area)". Removes exactly those 5 vias (by net + position match) and refills
zones so clearance recomputes against the current (KMR2) footprint
geometry, which is stale from before the swap.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")

BAD_VIA_POSITIONS_MM = [
    (50.046, 111.552), (50.646, 111.552), (51.846, 111.552),
    (51.246, 111.552), (49.446, 111.552),
]


def main():
    board = pcbnew.LoadBoard(BOARD)
    removed = 0
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_VIA" or t.GetNet().GetNetname() != "GND":
            continue
        p = t.GetPosition()
        x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        if any(abs(x - bx) < 0.01 and abs(y - by) < 0.01 for (bx, by) in BAD_VIA_POSITIONS_MM):
            board.Remove(t)
            removed += 1
    print(f"removed {removed} keepout-violating vias (expected {len(BAD_VIA_POSITIONS_MM)})")

    g = PcbGen(NETLIST)
    g.board = board
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
