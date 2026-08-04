"""Close out the 2-layer conversion route (micromouse-pcb-simplified-2l):
phased, crash-isolated (one phase per process; os._exit skips SWIG teardown).

  import   ImportSpecctraSES onto the true-edge 2L board + fill + save
  report   residual by net (kicad-cli DRC; board must be filled+saved first)
  healsig  A* retry of any unrouted SIGNAL edges (vias allowed)
  stitch   GND fragments -> opposite-layer main pour (gnd_stitch_xiao logic)
  chain    GND fragment -> ANY opposite-layer fragment (multi-hop merge)
  dedupe   drop redundant GND stitch vias (<1.3mm neighbors)

All phases reuse heal_all's loader with BOARD repointed at the -2l file.
"""
import os
import re
import sys
import json
import math
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
import heal_all

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified-2l.kicad_pcb")
SES = os.path.join(BASE, "micromouse-pcb-simplified-2l.ses")
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
heal_all.BOARD = BOARD          # repoint the shared loader at the 2L copy

PHASE = sys.argv[1] if len(sys.argv) > 1 else "report"


def fill_save(b):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(BOARD, b)


if PHASE == "preroute":
    # Pre-route the recurring Freerouting failures on the EMPTY (just-stripped)
    # board -- the guaranteed-path trick from the main 2-layer board. Longest /
    # most-constrained first. Run AFTER convert_2layer.py strip, BEFORE dsn.
    import route_all
    route_all.BOARD = BOARD
    HARD = ["WALL_DL_SENSE", "WALL_DR_SENSE", "WALL_EMIT_FRONT", "WALL_EMIT_DIAG",
            "WALL_EMIT_SIDE", "BUZZ_CTRL", "AIN1", "AIN2", "BIN1", "BIN2",
            "ENC1_A", "ENC1_B", "SCL", "EMIT_SIDE_K", "WALL_FL_LED", "WALL_SL_LED",
            "Net-(U1-BST)", "Net-(Q45-Pin_1)", "Net-(Q46-Pin_1)"]
    g = route_all.load()
    left = 0
    for net in HARD:
        g._unrouted = []
        try:
            g.route_net(net, width_mm=0.25, clearance_mm=0.2, max_expansions=400000)
            n = len(g._unrouted)
        except Exception as e:
            print("  %s: ERROR %s" % (net, e), flush=True)
            n = 99
        left += n
        print("  pre-route %-18s unrouted-edges left = %d" % (net, n), flush=True)
    g.save(BOARD)
    print("preroute done: %d edges still open across %d nets" % (left, len(HARD)), flush=True)
    os._exit(0)

if PHASE == "import":
    b = pcbnew.LoadBoard(BOARD)
    ok = pcbnew.ImportSpecctraSES(b, SES)
    nt = sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_TRACK")
    nv = sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_VIA")
    fill_save(b)
    print("ImportSpecctraSES:", ok, "| tracks", nt, "| vias", nv, flush=True)
    os._exit(0)

if PHASE == "report":
    drc = os.path.join(os.environ.get("TEMP", r"D:\tmp"), "xiao2l_drc.json")
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "--output", drc, BOARD],
                   capture_output=True)
    d = json.load(open(drc))
    gnd = 0
    sig = []
    for it in d.get("unconnected_items", []):
        ds = " ".join(x.get("description", "") for x in it["items"])
        m = re.findall(r"\[([^\]]+)\]", ds)
        net = m[0] if m else "?"
        if net == "GND":
            gnd += 1
        else:
            sig.append((net, [(round(x["pos"]["x"], 2), round(x["pos"]["y"], 2))
                              for x in it["items"][:2]]))
    errs = [v for v in d.get("violations", []) if v["severity"] == "error"]
    from collections import Counter
    print("errors:", len(errs), dict(Counter(v["type"] for v in errs)), flush=True)
    print("unconnected: GND", gnd, "| signal", len(sig), flush=True)
    for net, pos in sig[:12]:
        print("   ", net, pos, flush=True)
    os._exit(0)

if PHASE == "healsig":
    drc = os.path.join(os.environ.get("TEMP", r"D:\tmp"), "xiao2l_drc.json")
    d = json.load(open(drc))
    edges = []
    for it in d.get("unconnected_items", []):
        ds = " ".join(x.get("description", "") for x in it["items"])
        m = re.findall(r"\[([^\]]+)\]", ds)
        net = m[0] if m else ""
        if net and net != "GND" and len(it["items"]) >= 2:
            edges.append((net,
                          (round(it["items"][0]["pos"]["x"], 3), round(it["items"][0]["pos"]["y"], 3)),
                          (round(it["items"][1]["pos"]["x"], 3), round(it["items"][1]["pos"]["y"], 3))))
    g = heal_all.load()
    for (x, y, ds) in json.load(open("D:/tmp/x2l_spots.json")):
        g._extra_keepouts.append((x - 0.7, y - 0.7, x + 0.7, y + 0.7))
    print("  (%d blind-spot keepouts ACTIVE)" % len(g._extra_keepouts), flush=True)
    done = 0
    # board DRC min clearance is 0.2mm -- NEVER route tighter (r6 lesson: a
    # 0.15mm heal 'succeeded' into 7 clearance errors). Escalate budget only.
    # r7 lesson: healing at exactly the 0.2 rule lands marginally under
    # KiCad's clearance measure -- keep >= 0.22 and escalate BUDGET only.
    LADDER = [dict(width_mm=0.25, clearance_mm=0.25, grid_mm=0.1, max_expansions=400000),
              dict(width_mm=0.2, clearance_mm=0.22, grid_mm=0.1, max_expansions=900000),
              dict(width_mm=0.2, clearance_mm=0.22, grid_mm=0.08, max_expansions=900000)]
    for (net, pa, pb) in edges:
        ok = False
        for att in LADDER:
            for (p1, p2) in ((pa, pb), (pb, pa)):
                ok = g.retry_edge(net, p1, p2, **att)
                if ok:
                    break
            if ok:
                print("  retry_edge %s: ROUTED @ clr %.2f" % (net, att["clearance_mm"]), flush=True)
                break
        if not ok:
            print("  retry_edge %s %s->%s: FAILED (full ladder)" % (net, pa, pb), flush=True)
        done += ok
    fill_save(g.board)
    print("healsig: %d/%d routed" % (done, len(edges)), flush=True)
    os._exit(0)


def gnd_chains(b, layer):
    out = []
    for z in b.Zones():
        if z.GetNetname() == "GND" and not z.GetIsRuleArea() and z.IsOnLayer(layer):
            pl = z.GetFilledPolysList(layer)
            for i in range(pl.OutlineCount()):
                out.append(pl.Outline(i))
    return out


if PHASE in ("stitch", "chain"):
    g = heal_all.load()
    g.fill_zones()
    b = g.board
    F = gnd_chains(b, pcbnew.F_Cu)
    B = gnd_chains(b, pcbnew.B_Cu)
    if not F or not B:
        print("no GND pour on one side?!", flush=True)
        os._exit(1)
    Fmain = max(F, key=lambda c: abs(c.Area()))
    Bmain = max(B, key=lambda c: abs(c.Area()))
    added = 0
    # PTH hole centers: a stitch via landing <0.8mm from a plated hole trips
    # hole_to_hole/clearance (r7: J5/J6 pad-5/6) -- keep clear of ALL of them
    pth = []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetDrillSize().x > 0:
                c = pad.GetPosition()
                pth.append((pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)))

    def targets(layer):
        # stitch: fragments -> opposite MAIN only; chain: -> any opposite frag
        if PHASE == "stitch":
            return [Bmain] if layer == pcbnew.F_Cu else [Fmain]
        return B if layer == pcbnew.F_Cu else F

    for (layer, chains, main) in ((pcbnew.F_Cu, F, Fmain), (pcbnew.B_Cu, B, Bmain)):
        for ch in chains:
            if ch is main:
                continue
            bb = ch.BBox()
            x0, x1 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())
            y0, y1 = pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())
            placed = False
            xi = x0 + 0.5
            while xi < x1 - 0.5 and not placed:
                yi = y0 + 0.5
                while yi < y1 - 0.5 and not placed:
                    p = (round(xi, 2), round(yi, 2))
                    pv = pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))
                    if any(abs(hx - p[0]) < 0.8 and abs(hy - p[1]) < 0.8 for hx, hy in pth):
                        yi += 0.45
                        continue
                    if ch.PointInside(pv, 0, True) and any(
                            t.PointInside(pv, 0, True) for t in targets(layer)):
                        if not any(vn == "GND" and abs(vx - p[0]) < 1.0 and abs(vy - p[1]) < 1.0
                                   for (vx, vy, vn, vr) in g._vias):
                            if g._verify_geo([], [p], "GND", 0.2) is None:
                                g.add_via(p, "GND")
                                g._vias.append((p[0], p[1], "GND", 0.3))
                                added += 1
                                placed = True
                    yi += 0.45
                xi += 0.45
    fill_save(b)
    b2 = pcbnew.LoadBoard(BOARD)
    b2.BuildConnectivity()
    print("%s: +%d vias -> ratsnest %d" % (PHASE, added,
          b2.GetConnectivity().GetUnconnectedCount(True)), flush=True)
    os._exit(0)

if PHASE == "dedupe":
    b = pcbnew.LoadBoard(BOARD)
    gv = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    kept = []
    rm = 0
    for v in gv:
        p = v.GetPosition()
        x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        if any(math.hypot(x - kx, y - ky) < 1.3 for kx, ky in kept):
            b.Remove(v)
            rm += 1
        else:
            kept.append((x, y))
    fill_save(b)
    b2 = pcbnew.LoadBoard(BOARD)
    b2.BuildConnectivity()
    print("dedupe: -%d vias -> ratsnest %d" % (rm,
          b2.GetConnectivity().GetUnconnectedCount(True)), flush=True)
    os._exit(0)

print("unknown phase", PHASE)
os._exit(2)
