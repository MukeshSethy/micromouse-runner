"""Micro-route the residual unrouted SIGNAL-net connections that Freerouting
left open, using the in-house A* (retry_edge) which is free to change layers
via stitching vias -- i.e. the "multiple via paths" fallback the user asked
for. GND is a poured plane and is NOT handled here (see heal_all/gnd_iso).

Crash-isolated: one net's edges, save, os._exit(0). Re-run in a loop until the
DRC unconnected list is empty. Endpoints come straight from the kicad-cli DRC
'unconnected_items' report, whose positions are the ratsnest anchors (pad
centres / junctions) -- exactly what retry_edge's layers_at() expects.
"""
import os, re, sys, json, subprocess
import pcbnew
import heal_all

CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
BOARD = heal_all.BOARD
DRC = os.path.join(os.environ.get("TEMP", r"D:\tmp"), "heal_signal_drc.json")


def unrouted_edges():
    """The board MUST be filled+saved first (kicad-cli DRC does not fill zones,
    so an unfilled pour reports every GND pad as unconnected). With the pour
    filled+saved, the unconnected list is the TRUE residual. The net name is
    embedded in each item's description as '... [NET] ...', not a JSON field."""
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "--output", DRC, BOARD],
                   capture_output=True)
    d = json.load(open(DRC))
    edges = []
    for u in d.get("unconnected_items", []):
        its = u.get("items", [])
        if len(its) < 2:
            continue
        nets = re.findall(r"\[([^\]]+)\]",
                          " ".join(x.get("description", "") for x in its))
        net = nets[0] if nets else ""
        # GND is a poured plane -- bridged with stitch vias (gnd_iso), not here.
        if net == "GND" or not net:
            continue
        pa = (round(its[0]["pos"]["x"], 3), round(its[0]["pos"]["y"], 3))
        pb = (round(its[1]["pos"]["x"], 3), round(its[1]["pos"]["y"], 3))
        edges.append((net, pa, pb))
    return edges


def main():
    edges = unrouted_edges()
    print(f"unrouted signal edges (excl GND): {len(edges)}")
    for (net, pa, pb) in edges:
        print(f"  {net}: {pa} <-> {pb}")
    if not edges:
        print("nothing to heal")
        return
    g = heal_all.load()
    # Route every residual edge in ONE process. Incrementally adding tracks/vias
    # is the normal router mutation pattern (thousands per run) -- it is BULK
    # Remove()/re-Fill() that triggers the SWIG heap corruption, not add_track.
    # Vias are allowed on every retry (multiple via paths). Widen the search
    # and drop clearance grid so tight escapes are found.
    routed, failed = [], []
    for (net, pa, pb) in edges:
        ok = g.retry_edge(net, pa, pb, width_mm=0.25, clearance_mm=0.18,
                          grid_mm=0.1, max_expansions=300000)
        (routed if ok else failed).append((net, pa, pb))
        print(f"  retry_edge {net} {pa}->{pb}: {'ROUTED' if ok else 'FAILED'}")
        sys.stdout.flush()
    pcbnew.SaveBoard(BOARD, g.board)
    print(f"saved -- routed {len(routed)}, failed {len(failed)}")
    for (net, pa, pb) in failed:
        print(f"  STILL OPEN: {net} {pa} <-> {pb}")
    sys.stdout.flush()
    os._exit(0 if not failed else 3)


if __name__ == "__main__":
    main()
