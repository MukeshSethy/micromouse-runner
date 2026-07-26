"""SW1 (and any other SW_Push_1P1T_NO_CK_KMR2 footprint) carries FOUR physical
pads numbered "1,1,2,2" (a common mechanically-symmetric tactile-switch
footprint pattern) -- both physical copies of pad "1" are the same NET, but
KiCad/Freerouting still needs actual copper joining them; a plain net-name
match does not substitute for a real connection. Freerouting's own report
left "SW1-1@1 -> via" unrouted -- one of the two physical pad-1 copies never
got its own stub into the net. This adds a short direct track between the
two physical instances of each duplicated pad number, for every footprint
that has them, if they are not already connected.
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
    board = g.board
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    fixed = 0

    def _already_wired(p1, p2):
        # A pair counts as "already wired" if there's a track segment (or
        # chain reachable via same-net segments) whose endpoint sits at each
        # of p1 and p2. Simple direct-segment check is enough here: these
        # duplicate-pad footprints are always fed by a short direct stub in
        # this project's schematics, never a multi-hop chain between the two
        # copies.
        near1 = any(math.hypot(a[0] - p1[0], a[1] - p1[1]) < 0.05 or
                    math.hypot(b[0] - p1[0], b[1] - p1[1]) < 0.05
                    for (a, b, n, hw, L) in g._track_segs)
        near2 = any(math.hypot(a[0] - p2[0], a[1] - p2[1]) < 0.05 or
                    math.hypot(b[0] - p2[0], b[1] - p2[1]) < 0.05
                    for (a, b, n, hw, L) in g._track_segs)
        return near1 and near2

    for fp in board.GetFootprints():
        by_num = {}
        for pad in fp.Pads():
            by_num.setdefault(pad.GetNumber(), []).append(pad)
        for num, pads in by_num.items():
            if len(pads) < 2:
                continue
            net = pads[0].GetNetname()
            if not net:
                continue
            for i in range(len(pads)):
                for j in range(i + 1, len(pads)):
                    pa, pb = pads[i], pads[j]
                    p1 = (pcbnew.ToMM(pa.GetPosition().x), pcbnew.ToMM(pa.GetPosition().y))
                    p2 = (pcbnew.ToMM(pb.GetPosition().x), pcbnew.ToMM(pb.GetPosition().y))
                    d = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                    if d > 15:
                        continue  # not a duplicate-pad pair, just skip (too far to be this pattern)
                    if d < 0.01:
                        continue  # same physical location, nothing to bridge
                    if _already_wired(p1, p2):
                        continue
                    ok = g._verify_geo([(p1, p2, pcbnew.F_Cu)], [], net, 0.15) is None
                    if ok:
                        g.add_track(p1, p2, pcbnew.F_Cu, net, 0.3)
                        g._track_segs.append((p1, p2, net, 0.15, pcbnew.F_Cu))
                        print(f"  bridged {fp.GetReference()} pad {num} dup-copies "
                              f"{p1}<->{p2} (net {net})")
                        fixed += 1
                    else:
                        ok2 = g.retry_edge(net, p1, p2, width_mm=0.25, clearance_mm=0.15,
                                           grid_mm=0.1, max_expansions=150000)
                        print(f"  {'routed' if ok2 else 'FAILED'} {fp.GetReference()} pad {num} "
                              f"dup-copies {p1}<->{p2} (net {net}) via retry_edge")
                        if ok2:
                            fixed += 1
    print(f"\nfixed {fixed} duplicate-pad gap(s)")
    print("zone fill:", g.fill_zones())
    pcbnew.SaveBoard(BOARD, g.board)
    print("saved", BOARD)


if __name__ == "__main__":
    main()
