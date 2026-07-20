"""THT board CHECK ROUTINE -- one command, one definitive verdict. Fills the
zones, reports the pcbnew ratsnest (the connectivity truth headless), runs
kicad-cli DRC at default (error+warning) severity + schematic parity, and
prints a single VERDICT line. Exit 0 = PASS, 1 = FAIL. No passive waiting:
run it, read the verdict, act.

  python verify_board.py            # full check
  python verify_board.py --quiet    # verdict line only
"""
import sys, os, json, subprocess, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

BASE = r"D:\Projects\micromouse-pcb\tht-assembly\pcb"
BOARD = os.path.join(BASE, "micromouse-tht.kicad_pcb")
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
DRC = os.path.join(os.environ.get("TEMP", r"D:\tmp"), "verify_board_drc.json")
QUIET = "--quiet" in sys.argv


def ratsnest():
    # retry the degraded-SWIG load
    for _ in range(6):
        b = pcbnew.LoadBoard(BOARD)
        try:
            _ = [fp.GetReference() for fp in b.GetFootprints()]
        except TypeError:
            continue
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        b.BuildConnectivity()
        rn = b.GetConnectivity().GetUnconnectedCount(True)
        pcbnew.SaveBoard(BOARD, b)
        return rn
    return -1


def drc():
    subprocess.run([CLI, "pcb", "drc", "--schematic-parity", "--severity-error",
                    "--severity-warning", "--format", "json", "--output", DRC, BOARD],
                   capture_output=True)
    d = json.load(open(DRC))
    v = d.get("violations", [])
    errs = collections.Counter(x["type"] for x in v if x["severity"] == "error")
    warns = collections.Counter(x["type"] for x in v if x["severity"] == "warning")
    unc = len(d.get("unconnected_items", []))
    par = len(d.get("schematic_parity", []))
    return errs, warns, unc, par


def main():
    rn = ratsnest()
    errs, warns, unc, par = drc()
    ne, nw = sum(errs.values()), sum(warns.values())
    if not QUIET:
        print(f"ratsnest (pcbnew truth) : {rn}")
        print(f"DRC errors              : {ne}  {dict(errs)}")
        print(f"DRC warnings            : {nw}  {dict(warns)}")
        print(f"kicad-cli unconnected   : {unc}")
        print(f"schematic parity        : {par}")
    ok = (rn == 0 and ne == 0 and nw == 0 and par == 0)
    print(f"VERDICT: {'PASS' if ok else 'FAIL'} "
          f"(ratsnest {rn}, {ne} err, {nw} warn, {par} parity)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
