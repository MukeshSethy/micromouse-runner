"""After flipping U8/U2 to the bottom layer (LR-mirror around each
footprint's own anchor), the OLD tracks that used to reach their
PRE-flip pad positions are still sitting on the board -- Flip() only
moves the footprint/pads, it does not touch or drag connected copper.
Those old stubs are now genuinely dangling (nothing remains at the old
XY for that net). Remove exactly those stub segments -- not the whole
net -- so heal_all.py's retry_edge reconnects cleanly from wherever the
stub is cut back to, out to the pad's NEW (mirrored) position, instead
of leaving old dead copper cluttering the board.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")

FLIPPED = {"U8": (50.0, 59.0), "U2": (50.0, 72.0)}


def main():
    board = pcbnew.LoadBoard(BOARD)

    old_positions = []  # (net, oldx, oldy)
    for ref, (cx, cy) in FLIPPED.items():
        for fp in board.GetFootprints():
            if fp.GetReference() != ref:
                continue
            for pad in fp.Pads():
                n = pad.GetNetname()
                if not n:
                    continue
                p = pad.GetPosition()
                newx, newy = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
                oldx, oldy = 2 * cx - newx, newy
                old_positions.append((n, oldx, oldy))

    current_pad_nets = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pp = pad.GetPosition()
            key = (round(pcbnew.ToMM(pp.x), 3), round(pcbnew.ToMM(pp.y), 3))
            current_pad_nets.setdefault(key, set()).add(pad.GetNetname())

    to_remove = []
    seen_ids = set()
    for (n, ox, oy) in old_positions:
        key = (round(ox, 3), round(oy, 3))
        if n in current_pad_nets.get(key, set()):
            continue
        for t in board.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetNet().GetNetname() != n:
                continue
            s, e = t.GetStart(), t.GetEnd()
            sx, sy = pcbnew.ToMM(s.x), pcbnew.ToMM(s.y)
            ex, ey = pcbnew.ToMM(e.x), pcbnew.ToMM(e.y)
            if (abs(sx - ox) < 0.02 and abs(sy - oy) < 0.02) or \
               (abs(ex - ox) < 0.02 and abs(ey - oy) < 0.02):
                tid = t.m_Uuid.AsString() if hasattr(t, "m_Uuid") else id(t)
                if tid not in seen_ids:
                    seen_ids.add(tid)
                    to_remove.append(t)

    print(f"removing {len(to_remove)} orphaned stub tracks (post-flip dead copper)")
    for t in to_remove:
        board.Remove(t)

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
