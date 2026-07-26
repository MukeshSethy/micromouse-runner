"""Generic post-route straggler healer for the 4-layer routing pass. Loads the
CURRENT board (already routed by route_all_4l.py, ~3000 track/via items),
finds every net whose pads are not all mutually reachable (real ratsnest
gaps -- excludes netcode 0, KiCad's "no net" bucket for mechanical/NC pads),
groups pads into connected clusters via the live connectivity graph, and
routes a nearest-cluster MST with escalating search budgets using the same
retry_edge() used by complete_routing.py/heal_xiao_stragglers.py earlier in
this project. Unlike route_all_4l.py (from-scratch MST per net), this never
touches a net that's already fully connected -- only the real gaps.
"""
import sys, os, math, subprocess, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from gen_pcb import PcbGen
from board_geom import BOARD_OUTLINE, WHEEL_NOTCHES, MOUNT_HOLES

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(BASE, "micromouse-pcb-simplified.kicad_pcb")
NETLIST = os.path.join(BASE, "netlist.net")


def find_gaps():
    """Fresh subprocess: returns [(net_name, [(x_mm,y_mm), ...clusters...])]
    for every real (non-netcode-0) net that isn't fully connected yet."""
    code = r'''
import pcbnew, json
b = pcbnew.LoadBoard(r"%s")
b.BuildConnectivity()
conn = b.GetConnectivity()
pads_by_net = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == 0:
            continue
        pads_by_net.setdefault(pad.GetNetCode(), []).append(pad)
out = []
for code_, pads in pads_by_net.items():
    if len(pads) < 2:
        continue
    name = pads[0].GetNetname()
    unassigned = list(pads)
    clusters = []
    while unassigned:
        seed = unassigned.pop(0)
        reach = {(x.GetPosition().x, x.GetPosition().y)
                 for x in conn.GetConnectedItems(seed) if x.GetClass() == "PAD"}
        reach.add((seed.GetPosition().x, seed.GetPosition().y))
        in_cluster = [seed]
        rest = []
        for p in unassigned:
            if (p.GetPosition().x, p.GetPosition().y) in reach:
                in_cluster.append(p)
            else:
                rest.append(p)
        unassigned = rest
        # rep MUST be an exact pad center (not a centroid average) --
        # retry_edge()'s layers_at() resolves legal start/end layers by
        # matching the anchor point against a real pad/track/via position;
        # an averaged point matches nothing and falls back to "all layers
        # legal", which can silently start the route on a copper-less inner
        # layer with no via (a known failure mode noted in gen_pcb.py).
        clusters.append({
            "rep": (pcbnew.ToMM(in_cluster[0].GetPosition().x), pcbnew.ToMM(in_cluster[0].GetPosition().y)),
            "n": len(in_cluster),
        })
    if len(clusters) > 1:
        out.append({"net": name, "clusters": clusters})
print("GAPS_JSON:" + json.dumps(out))
''' % BOARD
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    for ln in r.stdout.splitlines():
        if ln.startswith("GAPS_JSON:"):
            return json.loads(ln[len("GAPS_JSON:"):])
    raise SystemExit(f"find_gaps failed: {r.stderr[-1000:]}")


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
    return g


def cluster_mst(clusters):
    """MST edges over cluster reps (Prim's), same idea as route_net's MST."""
    n = len(clusters)
    in_tree = [False] * n
    in_tree[0] = True
    edges = []
    for _ in range(n - 1):
        best = None
        for i in range(n):
            if not in_tree[i]:
                continue
            for j in range(n):
                if in_tree[j]:
                    continue
                d = math.hypot(clusters[i]["rep"][0] - clusters[j]["rep"][0],
                                clusters[i]["rep"][1] - clusters[j]["rep"][1])
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        in_tree[j] = True
        edges.append((i, j))
    return edges


def main():
    gaps = find_gaps()
    print(f"nets with gaps: {len(gaps)}")
    g = load()
    ok, fail = [], []
    for entry in gaps:
        net = entry["net"]
        clusters = entry["clusters"]
        edges = cluster_mst(clusters)
        for (i, j) in edges:
            a, b = clusters[i]["rep"], clusters[j]["rep"]
            d = math.hypot(a[0] - b[0], a[1] - b[1])
            routed = False
            for (width, clr, grid, maxexp) in (
                (0.25, 0.18, 0.2, 300000),
                (0.2, 0.15, 0.15, 500000),
                (0.2, 0.13, 0.1, 800000),
            ):
                if g.retry_edge(net, a, b, width_mm=width, clearance_mm=clr,
                                 grid_mm=grid, max_expansions=maxexp):
                    routed = True
                    break
            if routed:
                print(f"  OK {net}: {a} <-> {b}  d={d:.1f}mm")
                ok.append((net, a, b))
            else:
                print(f"  FAIL {net}: {a} <-> {b}  d={d:.1f}mm")
                fail.append((net, a, b))
    print(f"\nhealed {len(ok)}/{len(ok)+len(fail)}")
    if fail:
        print("still failing:")
        for f in fail:
            print("  ", f)
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
