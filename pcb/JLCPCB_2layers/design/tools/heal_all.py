"""Convergent connectivity healer. Loops: DRC -> heal every unconnected item
-> refill -> save -> DRC, until clean or no progress.

Strategies per gap:
  pair of copper items  -> A* micro-route between the two positions
                           (retry_edge; subsumes straight-line heals and can
                           dogleg through fine-pitch fields / drop vias)
  pour-net item         -> fallback: stitch via down to its plane, position
                           laddered until legal
  zone fragment         -> the zone's non-largest filled outlines are
                           fragments; drop a via where same-net F/B copper
                           overlies the fragment (via joins the clusters)

Fixing one cluster split often reveals the next (connectivity is global), so
one DRC pass per round is re-run after refill until stable.
"""
import sys, os, re, json, math, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BOARD = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\micromouse-pcb.kicad_pcb"
NETLIST = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\netlist.net"
DRC = r"D:\Projects\micromouse-pcb\pcb_drc.json"
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
POUR_RECTS = {"VM_BATT": (16, 44, 64, 113), "VM_6V": (66, 44, 99, 100)}
POUR_NETS = ("GND", "PLUS3V3", "VM_BATT", "VM_6V")
LAYER = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu,
         "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu}


def load():
    g = PcbGen(NETLIST)
    g.board = pcbnew.LoadBoard(BOARD)
    g.setup_design_rules()
    g.LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
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
    g._unrouted = []
    return g


def run_drc():
    subprocess.run([CLI, "pcb", "drc", "--severity-error", "--format", "json",
                    "--output", DRC, BOARD], capture_output=True)
    return json.load(open(DRC))


def parse(raw):
    desc = raw.get("description", "")
    m = re.search(r"\[([^\]]+)\]", desc)
    m2 = re.search(r" on (F\.Cu|B\.Cu|In\d\.Cu)", desc)
    return {"desc": desc, "net": m.group(1) if m else None,
            "zone": desc.startswith("Zone"),
            "layer": LAYER.get(m2.group(1)) if m2 else None,
            "pos": (raw["pos"]["x"], raw["pos"]["y"])}


def via_stitch(g, net, pos, layer):
    # a same-net via already here means a previous round tried this and it
    # did NOT fix connectivity -- another one just stacks duplicates
    if any(vn == net and abs(vx - pos[0]) < 0.3 and abs(vy - pos[1]) < 0.3
           for (vx, vy, vn, vr) in g._vias):
        return False
    for d in (0.0, 0.35, 0.5, 0.7, 1.0, 1.3):
        for k in range(16 if d else 1):
            th = k * math.pi / 8
            v = (round(pos[0] + d * math.cos(th), 3),
                 round(pos[1] + d * math.sin(th), 3))
            _pr = POUR_RECTS.get(net)
            if _pr and not (_pr[0] <= v[0] <= _pr[2] and _pr[1] <= v[1] <= _pr[3]):
                continue
            L = layer if layer is not None else pcbnew.F_Cu
            segs = [] if d == 0.0 else [(pos, v, L)]
            if g._verify_geo(segs, [v], net, 0.125) is None:
                for (a, b, LL) in segs:
                    g.add_track(a, b, LL, net, 0.25)
                    g._track_segs.append((a, b, net, 0.125, LL))
                g.add_via(v, net)
                return True
    return False


def bridge_fragments(g, net, zlayer):
    zone = None
    for z in g.board.Zones():
        if z.GetNetname() == net and z.GetLayer() == zlayer:
            zone = z
    if zone is None:
        return 0
    poly = zone.GetFilledPolysList(zlayer)
    if poly.OutlineCount() <= 1:
        return 0
    areas = [(abs(poly.Outline(i).Area()), i) for i in range(poly.OutlineCount())]
    main = max(areas)[1]
    n = 0
    for (_, fi) in areas:
        if fi == main:
            continue
        chain = poly.Outline(fi)
        done = False
        for (a, b, tn, hw, L) in list(g._track_segs):
            if tn != net or L not in (pcbnew.F_Cu, pcbnew.B_Cu) or done:
                continue
            ln = math.hypot(b[0] - a[0], b[1] - a[1])
            for s in range(int(ln / 0.4) + 2):
                t_ = min(1.0, s * 0.4 / ln) if ln else 0
                p = (round(a[0] + (b[0] - a[0]) * t_, 3),
                     round(a[1] + (b[1] - a[1]) * t_, 3))
                pv = pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))
                if not chain.PointInside(pv, 0, True):
                    continue
                # a same-net via already here means a previous round tried
                # this exact bridge and it did NOT join the clusters -- do not
                # stack another (this looped for 6 rounds once); leave the
                # fragment for the micro-route path instead
                if any(vn == net and abs(vx - p[0]) < 0.2 and abs(vy - p[1]) < 0.2
                       for (vx, vy, vn, vr) in g._vias):
                    continue
                if g._verify_geo([], [p], net, 0.125) is None:
                    g.add_via(p, net)
                    print(f"  fragment({net}/{fi}) bridge via @ {p}")
                    done = True
                    n += 1
                    break
        if not done:
            # fallback: drop a via INSIDE the island and micro-route from it
            # to the nearest same-net pad (the TCRT hole clusters shred In1
            # into pad-anchored islands with no overlying same-net track)
            bb = chain.BBox()
            cx = (pcbnew.ToMM(bb.GetLeft()) + pcbnew.ToMM(bb.GetRight())) / 2
            cy = (pcbnew.ToMM(bb.GetTop()) + pcbnew.ToMM(bb.GetBottom())) / 2
            best = None
            for pad in g._pads_geo():
                if pad["net"] != net:
                    continue
                dd = math.hypot(pad["cx"] - cx, pad["cy"] - cy)
                if dd > 0.5 and (best is None or dd < best[0]):
                    best = (dd, (pad["cx"], pad["cy"]))
            placed = None
            for ddx in (0.0, 0.6, -0.6, 1.2, -1.2):
                if placed:
                    break
                for ddy in (0.0, 0.6, -0.6, 1.2, -1.2):
                    v = (round(cx + ddx, 3), round(cy + ddy, 3))
                    pv2 = pcbnew.VECTOR2I(pcbnew.FromMM(v[0]), pcbnew.FromMM(v[1]))
                    if not chain.PointInside(pv2, 0, True):
                        continue
                    if any(vn == net and abs(vx - v[0]) < 0.3 and abs(vy - v[1]) < 0.3
                           for (vx, vy, vn, vr) in g._vias):
                        continue
                    if g._verify_geo([], [v], net, 0.125) is None:
                        g.add_via(v, net)
                        placed = v
                        break
            if placed and best and g.retry_edge(net, placed, best[1], width_mm=0.25,
                                                clearance_mm=0.18, grid_mm=0.1,
                                                max_expansions=600000):
                print(f"  fragment({net}/{fi}) island via {placed} -> routed to {best[1]}")
                done = True
                n += 1
            else:
                print(f"  fragment({net}/{fi}) NO bridge -- bbox "
                      f"({pcbnew.ToMM(bb.GetLeft()):.1f},{pcbnew.ToMM(bb.GetTop()):.1f})-"
                      f"({pcbnew.ToMM(bb.GetRight()):.1f},{pcbnew.ToMM(bb.GetBottom()):.1f})")
    return n


ZNAME = {pcbnew.In1_Cu: "In1.Cu", pcbnew.In2_Cu: "In2.Cu", pcbnew.B_Cu: "B.Cu"}
for rnd in range(1, 7):
    d = run_drc()
    un = d.get("unconnected_items", [])
    print(f"== round {rnd}: {len(d.get('violations', []))} violations, {len(un)} unconnected")
    if not un:
        break
    g = load()
    acted = 0
    for pair in un:
        items = [parse(r) for r in pair.get("items", [])]
        zones = [it for it in items if it["zone"]]
        plain = [it for it in items if not it["zone"]]
        if zones:
            m3 = re.search(r" on (F\.Cu|B\.Cu|In\d\.Cu)", zones[0]["desc"])
            zl = LAYER[m3.group(1)] if m3 else pcbnew.In1_Cu
            acted += bridge_fragments(g, zones[0]["net"], zl)
            continue
        if len(plain) == 2 and plain[0]["net"] == plain[1]["net"]:
            net, A, B = plain[0]["net"], plain[0]["pos"], plain[1]["pos"]
            ok = (g.retry_edge(net, A, B, width_mm=0.25, clearance_mm=0.3,
                               grid_mm=0.1, max_expansions=400000)
                  or g.retry_edge(net, A, B, width_mm=0.25, clearance_mm=0.18,
                                  grid_mm=0.1, max_expansions=1200000))
            if ok:
                print(f"  micro-route {net} {A}->{B}: OK")
                acted += 1
                continue
            if net in POUR_NETS:
                for it in plain:
                    if via_stitch(g, net, it["pos"], it["layer"]):
                        print(f"  via-drop {net} @ {it['pos']}")
                        acted += 1
            else:
                print(f"  UNHEALED {net} {A}->{B}")
    print("  zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, g.board)
    if acted == 0:
        print("  no progress -- stopping")
        break
print("heal loop finished")
