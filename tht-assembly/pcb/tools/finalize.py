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

BOARD = r"D:\Projects\micromouse-pcb\tht-assembly\pcb\micromouse-tht.kicad_pcb"
DRC = r"D:\Projects\micromouse-pcb\tht-assembly\pcb_drc.json"
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
MM = pcbnew.ToMM


def _q(x, y):
    return (round(x, 3), round(y, 3))


# ---- selective-refdes clear-spot scanner (rev 7.2) ----------------------------
def _place_refdes_clear(board, fps):
    """Place each kept reference text at the first candidate spot around its
    footprint that is >=0.25mm from every pad's bbox (mask openings), >=0.3mm
    from every other silk text placed so far, inside the outline, and off the
    two wheel notches. Text 0.8mm/0.15 stroke -- small, readable, dense-safe."""
    import math
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            pads.append((MM(bb.GetLeft()), MM(bb.GetTop()),
                         MM(bb.GetRight()), MM(bb.GetBottom()),
                         pad.IsOnLayer(pcbnew.F_Cu), pad.IsOnLayer(pcbnew.B_Cu)))
    taken = []           # placed text bboxes (both faces; face flag included)
    # seed with every PRE-EXISTING board-level silk text (BATT/PWR/MOT labels,
    # angle numbers, A/B/C letters, polarity marks, ONE PACK ONLY): the rev-7.2
    # first pass ignored them and 8 refdes landed on top of labels.
    for dw in board.GetDrawings():
        if dw.GetClass() != "PCB_TEXT":
            continue
        lay = dw.GetLayer()
        if lay not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        tb = dw.GetBoundingBox()
        taken.append((MM(tb.GetLeft()), MM(tb.GetTop()),
                      MM(tb.GetRight()), MM(tb.GetBottom()),
                      lay == pcbnew.B_SilkS))
    placed = 0
    for fp in sorted(fps, key=lambda f: f.GetReference()):
        r = fp.Reference()
        r.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
        r.SetTextThickness(pcbnew.FromMM(0.15))
        r.SetTextAngleDegrees(0)
        back = fp.IsFlipped()
        n = len(fp.GetReference())
        tw, th = 0.65 * n * 0.8 + 0.3, 1.1     # crude text extent
        fbb = fp.GetBoundingBox(False)
        fx1, fy1, fx2, fy2 = MM(fbb.GetLeft()), MM(fbb.GetTop()), MM(fbb.GetRight()), MM(fbb.GetBottom())
        cx, cy = (fx1 + fx2) / 2, (fy1 + fy2) / 2
        cands = []
        for d in (0.9, 1.3, 1.8, 2.4, 3.0):
            cands += [(cx, fy1 - d), (cx, fy2 + d), (fx1 - d, cy), (fx2 + d, cy),
                      (fx1 - d, fy1 - d), (fx2 + d, fy1 - d),
                      (fx1 - d, fy2 + d), (fx2 + d, fy2 + d)]
        ok_pos = None
        for (tx, ty) in cands:
            bx1, by1, bx2, by2 = tx - tw / 2, ty - th / 2, tx + tw / 2, ty + th / 2
            if bx1 < 1.0 or bx2 > 99.0 or by1 < 1.0 or by2 > 119.0:
                continue
            # wheel/antenna notches (board_geom): keep clear
            from board_geom import WHEEL_NOTCHES
            bad = False
            for (nx1, ny1, nx2, ny2) in WHEEL_NOTCHES:
                if bx2 > nx1 - 0.3 and bx1 < nx2 + 0.3 and by2 > ny1 - 0.3 and by1 < ny2 + 0.3:
                    bad = True
            if bad:
                continue
            for (px1, py1, px2, py2, onF, onB) in pads:
                if (onB if back else onF):
                    if bx2 > px1 - 0.25 and bx1 < px2 + 0.25 and by2 > py1 - 0.25 and by1 < py2 + 0.25:
                        bad = True
                        break
            if bad:
                continue
            for (ox1, oy1, ox2, oy2, oback) in taken:
                if oback == back and bx2 > ox1 - 0.3 and bx1 < ox2 + 0.3 and by2 > oy1 - 0.3 and by1 < oy2 + 0.3:
                    bad = True
                    break
            if not bad:
                ok_pos = (tx, ty, (bx1, by1, bx2, by2, back))
                break
        if ok_pos:
            r.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(round(ok_pos[0], 3)),
                                          pcbnew.FromMM(round(ok_pos[1], 3))))
            taken.append(ok_pos[2])
            placed += 1
        else:
            # no clear spot -> demote to fab rather than risk a warning
            r.SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
            print(f"  refdes {fp.GetReference()}: no clear silk spot, left on fab")
    return placed


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
    # Rev 7.2 (user: "component namings clearly visible for debugging"):
    # debug-critical refs KEEP their reference on physical silk, relocated to a
    # scanned clear spot beside the part. Everything else still moves to fab
    # (179 refs collide on silk at this density -- the assembly PDFs are the
    # full map).
    KEEP_REFDES = ({f"U{i}" for i in range(1, 9)} | {f"J{i}" for i in range(1, 11)}
                   | {f"SW{i}" for i in range(1, 7)} | {"F1", "Q1", "BZ1"})
    kept = []
    for fp in board.GetFootprints():
        fab = pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab
        ref = fp.GetReference()
        for txt in (fp.Reference(), fp.Value()):
            if txt.GetLayer() in SILK:
                if txt is fp.Reference() and ref in KEEP_REFDES:
                    kept.append(fp)
                    continue
                txt.SetLayer(fab)
                moved += 1
        for gi in fp.GraphicalItems():
            if gi.GetLayer() in SILK:
                gi.SetLayer(pcbnew.B_Fab if gi.GetLayer() == pcbnew.B_SilkS else pcbnew.F_Fab)
                moved += 1
    # a KEEP ref whose reference already sits on fab (earlier finalize runs)
    # comes back to silk first
    for fp in board.GetFootprints():
        if fp.GetReference() in KEEP_REFDES and fp not in kept:
            r = fp.Reference()
            if r.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab):
                r.SetLayer(pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS)
                kept.append(fp)
    placed = _place_refdes_clear(board, kept)
    print(f"phase silk: selective refdes kept for {len(kept)} parts, {placed} scanned clear")
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
    ANGLE_POS = [(26.2, 12.0), (73.8, 12.0), (10.7, 27.52), (89.3, 27.52),  # rev 7 front spots
                 (18.15, 37.16), (88.2, 36.6)]
    LETTER_POS = {"A": (74.25, 111.9), "B": (84.25, 111.9), "C": (94.25, 111.9)}  # ABOVE buttons, clear band  # BELOW buttons (visible)
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
    # rev 6.2 FIX: --severity-warning HIDES errors on KiCad 10.0.4
    # (included_severities:["warning"] only). Run at DEFAULT severity so the
    # report carries error-severity items too; callers filter by need.
    subprocess.run([CLI, "pcb", "drc", "--format",
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
    # subprocess isolation: in-process LoadBoard after phase_silk intermittently
    # returns a degraded SwigPyObject (no .Zones) -- a fresh interpreter never does
    code = ("import pcbnew;b=pcbnew.LoadBoard(r'%s');"
            "pcbnew.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();"
            "print('RN=%%d'%%b.GetConnectivity().GetUnconnectedCount(True))" % path)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    for ln in r.stdout.splitlines():
        if ln.startswith("RN="):
            return int(ln[3:])
    raise SystemExit(f"finalize ABORT: ratsnest subprocess failed: {r.stderr[-400:]}")


def phase_copper():
    # SAFETY GATE (rev 6.1): the strip is only sound on a FULLY-routed board.
    # kicad-cli's "unconnected" is unreliable headless, so gate on the pcbnew
    # RATSNEST. A non-zero ratsnest here means routing is incomplete and the
    # strip would cascade through partial routes (this exact bug over-stripped
    # a board from 7 to 51 unconnected once) -- refuse to strip.
    #
    # rev 6.2 rewrite: the old free-end graph fixpoint treated T-junctions
    # (a track ending on the MIDDLE of another track) as free ends and once
    # stripped 56 load-bearing connections. Now the strip is DRC-list-driven
    # and iterative: remove ONLY items KiCad itself flags as dangling (its
    # detection is zone- and T-junction-aware), re-run DRC, repeat until no
    # flags remain. Every round gates connectivity IN MEMORY before saving.
    rn0 = _ratsnest(BOARD)
    if rn0 != 0:
        raise SystemExit(f"finalize ABORT: ratsnest = {rn0} (routing incomplete); "
                         "route to zero before finalizing")
    total_v = total_t = total_destk = 0
    # positions proven load-bearing (skip re-matching); persisted because each
    # round runs in its own process (a second LoadBoard in-process degrades)
    PROT = os.path.join(os.environ.get("TEMP", r"D:\tmp"), "finalize_protected.json")
    protected = set()
    if os.path.exists(PROT):
        protected = {tuple(p) for p in json.load(open(PROT))}
    first = len(sys.argv) > 2 and sys.argv[2] == "first"
    for rnd in range(1):
        d = run_drc()
        kill_via = _collect(d, ("via_dangling",))
        kill_trk = _collect(d, ("track_dangling",))
        hole_pos = _collect(d, ("holes_co_located", "hole_to_hole")) if first else []
        kill_via = [p for p in kill_via if _q(*p) not in protected]
        kill_trk = [p for p in kill_trk if _q(*p) not in protected]
        if not kill_via and not kill_trk and not hole_pos:
            print(f"phase copper: converged after {rnd} rounds "
                  f"({total_v} vias, {total_t} stubs, {total_destk} de-stacked, "
                  f"{len(protected)} pour-bridges kept)")
            return
        board = pcbnew.LoadBoard(BOARD)
        tracks = list(board.GetTracks())        # cache FIRST (SWIG)
        items = []
        for t in tracks:
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                items.append({"o": t, "via": True, "x": MM(p.x), "y": MM(p.y),
                              "net": t.GetNetname(), "dead": False, "src": None})
            else:
                a, b = t.GetStart(), t.GetEnd()
                items.append({"o": t, "via": False, "net": t.GetNetname(),
                              "a": _q(MM(a.x), MM(a.y)), "b": _q(MM(b.x), MM(b.y)),
                              "dead": False, "src": None})
        vias = [it for it in items if it["via"]]
        n_v = n_t = n_d = 0
        for (tx, ty) in kill_via:
            best = min((it for it in vias if not it["dead"]),
                       key=lambda it: (it["x"] - tx) ** 2 + (it["y"] - ty) ** 2, default=None)
            if best and (best["x"] - tx) ** 2 + (best["y"] - ty) ** 2 < 0.01:
                board.Remove(best["o"]); best["dead"] = True
                best["src"] = _q(tx, ty); n_v += 1
        for (tx, ty) in kill_trk:
            best = min((it for it in items if not it["via"] and not it["dead"]),
                       key=lambda it: min((it["a"][0] - tx) ** 2 + (it["a"][1] - ty) ** 2,
                                          (it["b"][0] - tx) ** 2 + (it["b"][1] - ty) ** 2),
                       default=None)
            if best:
                dd = min((best["a"][0] - tx) ** 2 + (best["a"][1] - ty) ** 2,
                         (best["b"][0] - tx) ** 2 + (best["b"][1] - ty) ** 2)
                if dd < 0.01:
                    board.Remove(best["o"]); best["dead"] = True
                    best["src"] = _q(tx, ty); n_t += 1
        # de-stack co-located via pairs (round 0 only): drop the one with
        # fewer coincident segment ends (the redundant healer drop)
        if hole_pos:
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
                    board.Remove(near[0]["o"]); near[0]["dead"] = True; n_d += 1
        if n_v + n_t + n_d == 0:
            print(f"phase copper: {len(kill_via)+len(kill_trk)} flags but no matchable "
                  "items (positions stale?) -- stopping")
            return
        # gate BEFORE saving. KiCad's dangling test ignores ZONES, so a
        # pad->stub->pour bridge gets flagged although removing it cuts the
        # pad off. Detect: after the bulk removal, find broken nets and
        # RE-ADD every removed item on them; iterate until ratsnest is 0.
        readded = 0
        for _fix in range(6):
            pcbnew.ZONE_FILLER(board).Fill(board.Zones())
            board.BuildConnectivity()
            rn1 = board.GetConnectivity().GetUnconnectedCount(True)
            if rn1 == 0:
                break
            conn = board.GetConnectivity()
            broken = set()
            byname = {}
            for code, ni in board.GetNetsByNetcode().items():
                if ni.GetNetname():
                    byname[ni.GetNetname()] = code
            removed_nets = {it["net"] for it in items if it["dead"]}
            for nm in removed_nets:
                code = byname.get(nm)
                if code is None:
                    continue
                pads = [p for fp in board.GetFootprints() for p in fp.Pads()
                        if p.GetNetCode() == code]
                if len(pads) < 2:
                    continue
                reach = {(x.GetPosition().x, x.GetPosition().y)
                         for x in conn.GetConnectedItems(pads[0]) if x.GetClass() == "PAD"}
                reach.add((pads[0].GetPosition().x, pads[0].GetPosition().y))
                if any((p.GetPosition().x, p.GetPosition().y) not in reach for p in pads[1:]):
                    broken.add(nm)
            if not broken:
                raise SystemExit(f"finalize ABORT round {rnd}: ratsnest {rn1} but no "
                                 "broken net matches a removed item; disk untouched")
            for it in items:
                if it["dead"] and it["net"] in broken:
                    board.Add(it["o"]); it["dead"] = False; readded += 1
                    if it["src"]:
                        protected.add(it["src"])
                    if it["via"]:
                        n_v -= 1
                    else:
                        n_t -= 1
        else:
            raise SystemExit(f"finalize ABORT round {rnd}: could not restore ratsnest 0 "
                             "by re-adding; board on disk left untouched")
        pcbnew.SaveBoard(BOARD, board)
        json.dump(sorted(protected), open(PROT, "w"))
        if readded:
            print(f"  round: re-added {readded} load-bearing pour-bridge items")
        total_v += n_v; total_t += n_t; total_destk += n_d
        print(f"  round done: -{n_v} vias, -{n_t} stubs, -{n_d} de-stacked (ratsnest 0)")


def main():
    # every phase AND every copper round in its OWN interpreter: a second
    # LoadBoard in-process after a LoadBoard+SaveBoard cycle returns a
    # degraded SwigPyObject (no methods)
    if len(sys.argv) > 1:
        {"silk": phase_silk, "copper": phase_copper}[sys.argv[1]]()
        return
    me = os.path.abspath(__file__)

    def run_phase(args):
        r = subprocess.run([sys.executable, me] + args, capture_output=True, text=True)
        out = r.stdout + r.stderr
        for ln in out.splitlines():
            low = ln.lower()
            if "memory leak" in low or "duplicate image" in low or not ln.strip():
                continue
            print(ln)
        if r.returncode != 0:
            raise SystemExit(f"finalize: phase {args[0]} failed (rc {r.returncode})")
        return out

    prot = os.path.join(os.environ.get("TEMP", r"D:\tmp"), "finalize_protected.json")
    if os.path.exists(prot):
        os.remove(prot)
    run_phase(["silk"])
    for i in range(10):
        out = run_phase(["copper", "first"] if i == 0 else ["copper"])
        if "converged" in out:
            break
    else:
        raise SystemExit("finalize: copper did not converge in 10 rounds")
    print("finalize: done")


if __name__ == "__main__":
    main()
