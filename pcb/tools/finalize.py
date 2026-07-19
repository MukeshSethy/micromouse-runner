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
    ANGLE_POS = [(26.2, 12.0), (73.8, 12.0), (10.7, 27.52), (89.3, 27.52),  # rev 7 front spots
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
