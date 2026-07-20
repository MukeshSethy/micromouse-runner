"""Hand-route the tight power nets the autorouter can't thread (SW_6V, VM_6V,
VM_BATT) with EXPLICIT, geometry-verified polylines + vias -- the same
technique the SMD board used for its USB-C pad field.

Each net is given a corridor (list of (layer, [pts]) polylines + via drops).
Every segment is checked with g._verify_geo before it is added; a rejected
segment prints its reason so the corridor can be nudged. Save is gated on the
pcbnew ratsnest not increasing.

The CORRIDORS dict is filled after inspecting the routed board's pad
coordinates (run diag first). Widths: 0.5mm power (robu 0.23A stall -> ample).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
import board_geom

BASE = r"D:\Projects\micromouse-pcb\tht-assembly\pcb"
BOARD = os.path.join(BASE, "micromouse-tht.kicad_pcb")
LAYER = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu, "In1": pcbnew.In1_Cu, "In2": pcbnew.In2_Cu}

def load():
    g = PcbGen(os.path.join(BASE, "netlist.net"))
    g.board = pcbnew.LoadBoard(BOARD)
    try:
        _ = [fp.GetReference() for fp in g.board.GetFootprints()]
    except TypeError:
        raise SystemExit("DEGRADED LOAD -- retry")
    g.setup_design_rules()
    g.LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    g._placed = {fp.GetReference(): fp for fp in g.board.GetFootprints()}
    g._nets = {}
    for code, ni in g.board.GetNetsByNetcode().items():
        if ni.GetNetname():
            g._nets[ni.GetNetname()] = ni
    g._extra_keepouts = []
    for (hx, hy, hr) in board_geom.MOUNT_HOLES:
        m = hr + 0.75
        g._extra_keepouts.append((hx - m, hy - m, hx + m, hy + m))
    g._outline_pts = None
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
    g._unrouted = []
    return g

def pad(g, ref, num):
    for p in g._pads_geo():
        if p["ref"] == ref and p["num"] == str(num):
            return (p["cx"], p["cy"])
    raise KeyError(f"{ref}.{num}")

# filled after diag: net -> list of ("layer", [(x,y),...]) polylines, and
# list of (x,y) via positions
CORRIDORS = {}
VIAS = {}

def run():
    g = load()
    g.board.BuildConnectivity()
    rn0 = g.board.GetConnectivity().GetUnconnectedCount(True)
    print("ratsnest before:", rn0)
    for net, lines in CORRIDORS.items():
        for (lname, pts) in lines:
            L = LAYER[lname]
            segs = [(pts[i], pts[i+1], L) for i in range(len(pts)-1)]
            rej = g._verify_geo(segs, VIAS.get(net, []), net, 0.25)
            if rej:
                print(f"{net} [{lname}]: REJECT {rej}")
                continue
            for (a, b, _) in segs:
                g.add_track(a, b, L, net, 0.5)
                g._track_segs.append((a, b, net, 0.25, L))
            print(f"{net} [{lname}]: {len(segs)} segs OK")
        for v in VIAS.get(net, []):
            g.add_via(v, net)
            g._vias.append((v[0], v[1], net, 0.3))
    print("zone fill:", g.fill_zones())
    g.board.BuildConnectivity()
    rn = g.board.GetConnectivity().GetUnconnectedCount(True)
    print("ratsnest after:", rn)
    if rn <= rn0:
        pcbnew.SaveBoard(BOARD, g.board)
        print("SAVED")
    else:
        print("NOT SAVED (ratsnest rose)")

if __name__ == "__main__":
    run()
