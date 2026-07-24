"""Import Freerouting's .ses session back onto the placement board, applying
all the routed tracks/vias, and save. The board on disk (micromouse-pcb-simplified.kicad_pcb)
is the exact placement board that was exported to DSN, so the SES applies cleanly."""
import os
import pcbnew

_BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(_BASE, "micromouse-pcb-simplified.kicad_pcb")
SES = os.path.join(_BASE, "micromouse-pcb-simplified.ses")

board = pcbnew.LoadBoard(BOARD)
ok = pcbnew.ImportSpecctraSES(board, SES)
print("ImportSpecctraSES:", ok)

tracks = board.GetTracks()
n_tracks = sum(1 for t in tracks if t.GetClass() == "PCB_TRACK")
n_vias = sum(1 for t in tracks if t.GetClass() == "PCB_VIA")
print(f"After import: {n_tracks} track segments, {n_vias} vias")

pcbnew.SaveBoard(BOARD, board)
print("Saved.")
