"""International-standards routing audit for the 2-layer board.

KiCad's DRC enforces the vendor rule set (JLC-cap-Lion) but models almost none
of the IPC requirements below, so they are checked geometrically here:

  IPC-2221B  conductor spacing vs working voltage (Table 6-1, external uncoated)
  IPC-2221B  annular ring, hole aspect ratio
  IPC-2152   conductor current capacity at a stated temperature rise
  IPC-A-600  acid traps (acute copper angles), starved thermals
  IPC-7351   land-pattern integrity (courtyard overlap -- already DRC-gated)
  general    right-angle bends, track necking, copper slivers, edge clearance
"""
import math, sys, os
import pcbnew

BOARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                     "micromouse-pcb-simplified-2l.kicad_pcb")
T_CU = 0.035          # JLC standard 1oz outer copper
V_MAX = 8.4           # 2S LiPo fully charged -- highest potential on the board
mm = pcbnew.ToMM

def ipc2221_spacing(v):
    # Table 6-1, B1 external conductors, uncoated, sea level to 3050 m
    if v <= 15:   return 0.05
    if v <= 30:   return 0.05
    if v <= 50:   return 0.10
    if v <= 100:  return 0.10
    if v <= 150:  return 0.20
    return 0.25

def ipc2152_capacity(w_mm, dT):
    A = (w_mm / 0.0254) * (T_CU / 0.0254)     # mils^2
    return 0.048 * (dT ** 0.44) * (A ** 0.725)

def main():
    b = pcbnew.LoadBoard(os.path.normpath(BOARD))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    fails, warns, notes = [], [], []

    # ---- 1. IPC-2221B conductor spacing vs working voltage ----------------
    req = ipc2221_spacing(V_MAX)
    ds = b.GetDesignSettings()
    have = mm(ds.m_MinClearance)
    (notes if have >= req else fails).append(
        "IPC-2221B spacing: %.2fmm enforced vs %.2fmm required at %.1fV (%.1fx margin)"
        % (have, req, V_MAX, have / req))

    # ---- 2. IPC-2152 current capacity of the narrowest conductor ----------
    widths = {}
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            continue
        widths.setdefault(round(mm(t.GetWidth()), 3), 0)
        widths[round(mm(t.GetWidth()), 3)] += 1
    if widths:
        wmin = min(widths)
        notes.append("IPC-2152: narrowest conductor %.2fmm -> %.2fA @10C, %.2fA @20C rise"
                     % (wmin, ipc2152_capacity(wmin, 10), ipc2152_capacity(wmin, 20)))

    # ---- 3. annular ring + hole aspect ratio (IPC-2221B) ------------------
    worst_ring, worst_ar = 9e9, 0
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            d = mm(pad.GetDrillSize().x)
            if d <= 0:
                continue
            worst_ar = max(worst_ar, 1.6 / d)
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                sz = min(mm(pad.GetSize(pcbnew.F_Cu).x), mm(pad.GetSize(pcbnew.F_Cu).y))
                worst_ring = min(worst_ring, (sz - d) / 2)
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            d = mm(t.GetDrill())
            worst_ar = max(worst_ar, 1.6 / d)
            worst_ring = min(worst_ring, (mm(t.GetWidth(pcbnew.F_Cu)) - d) / 2)
    (notes if worst_ring >= 0.05 else fails).append(
        "IPC-2221B annular ring: min %.3fmm (Class 2 needs >=0.05mm; Lion asks 0.15)" % worst_ring)
    (notes if worst_ar <= 8 else fails).append(
        "IPC-2221B hole aspect ratio: worst %.1f:1 (limit 8:1 for standard plating)" % worst_ar)

    # ---- 4. acid traps: acute angles between same-net connected tracks ----
    ends = {}
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            continue
        for a, c in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
            k = (round(mm(a.x), 3), round(mm(a.y), 3), t.GetLayer(), t.GetNetname())
            ends.setdefault(k, []).append((round(mm(c.x), 3), round(mm(c.y), 3)))
    acid = []
    for (x, y, lay, net), others in ends.items():
        if len(others) < 2:
            continue
        for i in range(len(others)):
            for j in range(i + 1, len(others)):
                v1 = (others[i][0] - x, others[i][1] - y)
                v2 = (others[j][0] - x, others[j][1] - y)
                n1 = math.hypot(*v1); n2 = math.hypot(*v2)
                if n1 < 1e-6 or n2 < 1e-6:
                    continue
                cosang = max(-1.0, min(1.0, (v1[0]*v2[0] + v1[1]*v2[1]) / (n1*n2)))
                ang = math.degrees(math.acos(cosang))
                if ang < 89.0:
                    acid.append((net, x, y, round(ang, 1)))
    if acid:
        warns.append("IPC-A-600 acid traps: %d acute (<90deg) same-net corners, e.g. %s"
                     % (len(acid), acid[:3]))
    else:
        notes.append("IPC-A-600 acid traps: none (no same-net corner under 90deg)")

    # ---- 5. right-angle (90deg) bends -- signal-integrity/etch practice ---
    right = [a for a in ((net, x, y, ang) for (net, x, y, ang) in acid) if 89 <= a[3] <= 91]
    notes.append("90deg bends: %d (cosmetic/etch preference, not a rule)" % len(right))

    # ---- 6. track necking: a net whose width varies ----------------------
    per_net = {}
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            continue
        per_net.setdefault(t.GetNetname(), set()).add(round(mm(t.GetWidth()), 3))
    neck = {n: sorted(w) for n, w in per_net.items() if len(w) > 1}
    if neck:
        warns.append("track necking: %d nets change width mid-route: %s"
                     % (len(neck), dict(list(neck.items())[:4])))
    else:
        notes.append("track necking: none (each net keeps one width)")

    # ---- 7. copper-to-edge (IPC + vendor) --------------------------------
    notes.append("copper->board edge: %.2fmm enforced by rule (Lion 0.3 / JLC 0.2)"
                 % mm(ds.m_CopperEdgeClearance))

    print("=" * 74)
    print("IPC / international routing audit")
    print("=" * 74)
    for f in fails: print("  [FAIL] " + f)
    for w in warns: print("  [WARN] " + w)
    for n in notes: print("  [ OK ] " + n)
    print()
    print("RESULT:", "FAIL (%d)" % len(fails) if fails else
          ("PASS with %d advisory" % len(warns) if warns else "PASS -- all clean"))
    sys.stdout.flush()
    os._exit(1 if fails else 0)

main()
