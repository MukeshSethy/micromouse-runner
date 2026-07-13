"""Operate IN PLACE on the user's hand-edited board: preserve every component
position, strip only the tracks/vias, apply routing rules (incl. the no-trace-
between-THT-pins clearance), and re-export a DSN for Freerouting. NEVER
regenerates placement -- build_pcb.py is not run, so the user's manual layout
is kept exactly."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BOARD = r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb"
DSN = r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.dsn"

b = pcbnew.LoadBoard(BOARD)

# 1. Design rules FIRST (accessing GetDesignSettings after removing tracks
# corrupts the proxy in this build -- set rules before touching tracks).
# The key new rule: NO TRACE BETWEEN THROUGH-HOLE PINS. THT
# socket pins are 2.54mm pitch with ~1.7mm pads -> ~0.84mm gap between adjacent
# pins. With a 0.25mm trace, a clearance of 0.3mm makes an in-gap trace need
# 0.3+0.25+0.3 = 0.85mm > 0.84mm, so no trace can squeeze between two adjacent
# THT pins -> no solder-bridge risk during hand assembly. (Slightly reduces
# routability, acceptable trade for a hand-soldered board.)
bds = b.GetDesignSettings()
bds.m_MinClearance = pcbnew.FromMM(0.3)
bds.m_TrackMinWidth = pcbnew.FromMM(0.2)
bds.m_ViasMinSize = pcbnew.FromMM(0.5)
bds.m_MinThroughDrill = pcbnew.FromMM(0.3)
try:
    bds.m_HoleToHoleMin = pcbnew.FromMM(0.2)
    bds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
except Exception:
    pass
for setter in (
    lambda: bds.m_NetSettings.GetDefaultNetclass().SetClearance(pcbnew.FromMM(0.3)),
    lambda: [nc.SetClearance(pcbnew.FromMM(0.3)) for nc in b.GetAllNetClasses().values()],
):
    try:
        setter()
    except Exception:
        pass

# 2. NOW strip existing tracks + vias (we re-route); KEEP footprints/zones/edges.
removed = 0
for t in list(b.GetTracks()):
    b.Remove(t); removed += 1
print("stripped", removed, "track/via items; footprints kept at their positions")

pcbnew.SaveBoard(BOARD, b)
ok = pcbnew.ExportSpecctraDSN(b, DSN)
print("saved board (positions preserved, tracks stripped) + DSN export:", ok)
