"""Post-route finalization -> a DRC-clean board (0 errors AND 0 warnings).

Rev 6 added the user requirement "0 errors and 0 warnings from KiCad". The
router/healer leave three classes of cosmetic-but-flagged residue that no
earlier rev counted (they only ever ran DRC at --severity-error):

  1. dangling copper   -- redundant fan-out stubs on already-connected pads
                          and one-layer (orphaned) vias
  2. hole artifacts    -- healer via-drops co-located with / <0.2mm from a hole
  3. silkscreen        -- 175 footprints' auto-placed reference designators
                          overlap each other / copper / the board edge in the
                          dense sensor + power clusters

Fixes, all reproducible (a pipeline stage, not a hand-edit):
  1/2. free-end graph fixpoint over the copper (pads+vias are anchors; a track
       with a truly-free end is redundant -- unconnected==0 with pours filled
       proves the pours already reach every pad, so removal isolates nothing)
  3.   move every component REFDES + VALUE to the fab layer; the physical silk
       then carries only the INTENTIONAL functional annotations from
       build_pcb.py (bent-sensor outlines, 0/45/90 callouts, BATT/PWR/MOT,
       A/B/C/RST). Refdes still ship in the fab/assembly drawing. Standard
       dense-board practice.

SWIG note: this pcbnew build degrades the PCB_TRACK proxies the moment
GetFootprints()/GetDrawings() is touched, so ALL track geometry is cached to
plain tuples up front; the live object is used only for board.Remove().

Run after route_loaded.py + heal_all.py. Two independent phases (silk copper),
each its own board load. Idempotent.
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BOARD = r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb"
DRC = r"D:\Projects\micromouse-pcb\pcb_drc.json"
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
MM = pcbnew.ToMM


def _q(x, y):
    return (round(x, 3), round(y, 3))


# ---- Phase 1: silkscreen -----------------------------------------------------
def phase_silk():
    """Physical silk keeps ONLY the intentional board-level annotations from
    build_pcb.py: the bent-sensor U-outlines (0.15mm segments) + the angle
    NUMBER labels + the BATT/PWR/MOT/A/B/C/RST labels. Everything else -- all
    footprint body silk (ref, value, part outlines, the TCRT 'LED'/'PT'
    markers) and the decorative angle RAYS (0.12mm segments) -- moves to the
    fabrication drawing or is dropped. That number+outline conveys each sensor
    angle precisely without the ray clutter that overlaps at this density."""
    board = pcbnew.LoadBoard(BOARD)
    drawings = list(board.GetDrawings())   # FIRST -- GetFootprints() degrades this proxy
    moved = 0
    SILK = (pcbnew.F_SilkS, pcbnew.B_SilkS)
    for fp in board.GetFootprints():
        fab = pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab
        for txt in (fp.Reference(), fp.Value()):
            if txt.GetLayer() in SILK:
                txt.SetLayer(fab)
                moved += 1
        for gi in fp.GraphicalItems():
            if gi.GetLayer() in SILK:
                gi.SetLayer(pcbnew.B_Fab if gi.GetLayer() == pcbnew.B_SilkS else pcbnew.F_Fab)
                moved += 1
    # drop the angle RAYS (board-level F.SilkS segments authored at 0.12mm;
    # the U-outlines are 0.15mm and stay)
    dropped = 0
    for dw in drawings:
        if (dw.GetLayer() == pcbnew.F_SilkS and dw.GetClass() == "PCB_SHAPE"
                and dw.GetShape() == pcbnew.SHAPE_T_SEGMENT
                and abs(MM(dw.GetWidth()) - 0.12) < 0.02):
            board.Remove(dw)
            dropped += 1
    # reposition my own labels clear of pads / outlines (the routed board still
    # carries build_pcb's original spots; these targets are also written back
    # into build_pcb so a fresh rebuild lands here too). Angle numbers go to a
    # side pocket per cluster; button letters sit left of each 6mm button.
    # clear-spot positions (scanned >=1.6mm from every pad, >=1.4mm from silk),
    # one per cluster: front-L/R, diag-L/R, side-L/R
    ANGLE_POS = [(30.6, 13.03), (68.7, 13.03), (10.7, 27.52), (89.3, 27.52),
                 (18.15, 37.16), (88.2, 36.6)]
    LETTER_POS = {"A": (65.5, 113.7), "B": (75.5, 113.7), "C": (85.5, 113.7)}
    reloc = 0
    for dw in drawings:
        if dw.GetLayer() != pcbnew.F_SilkS or dw.GetClass() != "PCB_TEXT":
            continue
        t = dw.GetText()
        if "°" in t:                       # an angle number
            p = dw.GetPosition()
            cx, cy = MM(p.x), MM(p.y)
            tgt = min(ANGLE_POS, key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)
            dw.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(tgt[0]), pcbnew.FromMM(tgt[1])))
            reloc += 1
        elif t in LETTER_POS:
            tgt = LETTER_POS[t]
            dw.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(tgt[0]), pcbnew.FromMM(tgt[1])))
            reloc += 1
    pcbnew.SaveBoard(BOARD, board)
    print(f"phase silk: {moved} footprint silk -> fab, {dropped} rays dropped, {reloc} labels relocated")


# ---- Phase 2: copper cleanup -------------------------------------------------
def run_drc():
    subprocess.run([CLI, "pcb", "drc", "--severity-warning", "--format",
                    "json", "--output", DRC, BOARD], capture_output=True)
    return json.load(open(DRC))


def _collect(d, types):
    out = []
    for v in d["violations"]:
        if v["type"] in types:
            for it in v.get("items", []):
                p = it.get("pos")
                if p:
                    out.append((p["x"], p["y"]))
    return out


def _ratsnest(path):
    b = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    return b.GetConnectivity().GetUnconnectedCount(True)


def phase_copper():
    # SAFETY GATE (rev 6.1): the strip is only sound on a FULLY-routed board.
    # kicad-cli's "unconnected" is unreliable headless, so gate on the pcbnew
    # RATSNEST. A non-zero ratsnest here means routing is incomplete and the
    # strip would cascade through partial routes (this exact bug over-stripped
    # a board from 7 to 51 unconnected once) -- refuse to strip.
    rn0 = _ratsnest(BOARD)
    if rn0 != 0:
        raise SystemExit(f"finalize ABORT: ratsnest = {rn0} (routing incomplete); "
                         "route to zero before finalizing")
    d = run_drc()
    kill_via = _collect(d, ("via_dangling",))          # one-layer vias (pour-completed)
    kill_trk = _collect(d, ("track_dangling",))        # stubs the graph missed (via-coincident end)
    hole_pos = _collect(d, ("holes_co_located", "hole_to_hole"))
    board = pcbnew.LoadBoard(BOARD)
    tracks = list(board.GetTracks())            # FIRST -- before any footprint touch
    items = []                                  # cache geometry while proxies are valid
    for t in tracks:
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            items.append({"o": t, "via": True, "x": MM(p.x), "y": MM(p.y), "dead": False})
        else:
            a, b = t.GetStart(), t.GetEnd()
            items.append({"o": t, "via": False,
                          "a": _q(MM(a.x), MM(a.y)), "b": _q(MM(b.x), MM(b.y)), "dead": False})
    # pad centres (anchors). GetFootprints() degrades track proxies -- safe now
    # that geometry is cached; board.Remove(obj) still works on the pointer.
    anchors = set()
    for fp in board.GetFootprints():
        for p in fp.Pads():
            pp = p.GetPosition()
            anchors.add(_q(MM(pp.x), MM(pp.y)))

    vias = [it for it in items if it["via"]]

    # 1. remove DRC-flagged one-layer vias (their feeding stub then dangles and
    #    is swept below -- the signal already completed through its pour)
    n_kill = 0
    for (tx, ty) in kill_via:
        best = min((it for it in vias if not it["dead"]),
                   key=lambda it: (it["x"] - tx) ** 2 + (it["y"] - ty) ** 2, default=None)
        if best and (best["x"] - tx) ** 2 + (best["y"] - ty) ** 2 < 0.001:
            board.Remove(best["o"]); best["dead"] = True; n_kill += 1
    # 1b. explicit removal of DRC-flagged dangling stubs the graph fixpoint
    #     kept (their free end coincided with a via that has since been killed,
    #     or with a pad edge my centre-anchor set missed). unconnected==0 with
    #     pours filled proves the net is held elsewhere.
    for (tx, ty) in kill_trk:
        best = min((it for it in items if not it["via"] and not it["dead"]),
                   key=lambda it: min((it["a"][0] - tx) ** 2 + (it["a"][1] - ty) ** 2,
                                      (it["b"][0] - tx) ** 2 + (it["b"][1] - ty) ** 2),
                   default=None)
        if best:
            dd = min((best["a"][0] - tx) ** 2 + (best["a"][1] - ty) ** 2,
                     (best["b"][0] - tx) ** 2 + (best["b"][1] - ty) ** 2)
            if dd < 0.001:
                board.Remove(best["o"]); best["dead"] = True; n_kill += 1
    # 2. de-stack co-located / too-close via pairs: drop the one with FEWER
    #    coincident segment ends (the redundant healer drop)
    seg_ends = {}
    for it in items:
        if not it["via"]:
            seg_ends[it["a"]] = seg_ends.get(it["a"], 0) + 1
            seg_ends[it["b"]] = seg_ends.get(it["b"], 0) + 1
    for (tx, ty) in hole_pos:
        near = [it for it in vias if not it["dead"]
                and (it["x"] - tx) ** 2 + (it["y"] - ty) ** 2 < 0.36]
        if len(near) >= 2:
            near.sort(key=lambda it: seg_ends.get(_q(it["x"], it["y"]), 0))
            board.Remove(near[0]["o"]); near[0]["dead"] = True; n_kill += 1

    via_pts = {_q(it["x"], it["y"]) for it in vias if not it["dead"]}
    segs = [it for it in items if not it["via"] and not it["dead"]]
    vias = [it for it in vias if not it["dead"]]
    alive = {id(it): it for it in segs}
    removed_seg = 0
    changed = True
    while changed:
        changed = False
        endcount = {}
        for it in alive.values():
            endcount[it["a"]] = endcount.get(it["a"], 0) + 1
            endcount[it["b"]] = endcount.get(it["b"], 0) + 1
        for k in list(alive):
            it = alive[k]
            free = False
            for e in (it["a"], it["b"]):
                if e not in anchors and e not in via_pts and endcount.get(e, 0) <= 1:
                    free = True
                    break
            if free:
                board.Remove(it["o"])
                del alive[k]
                removed_seg += 1
                changed = True

    # orphan vias: no surviving segment endpoint coincides with the via
    live_ends = set()
    for it in alive.values():
        live_ends.add(it["a"]); live_ends.add(it["b"])
    removed_via = 0
    for it in vias:
        if _q(it["x"], it["y"]) not in live_ends:
            board.Remove(it["o"])
            removed_via += 1

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    # POST-STRIP GATE: the strip must not have disconnected anything.
    rn1 = _ratsnest(BOARD)
    if rn1 != 0:
        raise SystemExit(f"finalize ABORT: strip raised ratsnest to {rn1} -- a removed "
                         "stub was load-bearing; board NOT trustworthy (restore + investigate)")
    print(f"phase copper: killed {n_kill} flagged vias, stripped {removed_seg} "
          f"dangling segments, {removed_via} orphan vias (ratsnest still 0)")


def main():
    phase_silk()
    phase_copper()
    print("finalize: done")


if __name__ == "__main__":
    main()
