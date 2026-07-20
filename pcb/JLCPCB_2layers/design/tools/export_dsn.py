"""Regenerate the placement-only board (footprints + GND pours, no tracks) and
export it to Specctra DSN for Freerouting. Routing from a clean placement lets
Freerouting solve the whole board at once, rather than working around the
partial routes my in-house router left. gen_pcb.py's router is kept as the
independent/regenerable fallback; Freerouting is the completion path."""
import sys, os, runpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

# Run placement (build_pcb.py saves the placement-only board to disk).
ns = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_pcb.py"))
g = ns["g"]
g.setup_design_rules()
g.save(r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\micromouse-pcb.kicad_pcb")

ok = pcbnew.ExportSpecctraDSN(g.board, r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\micromouse-pcb.dsn")
print("DSN export:", ok)
