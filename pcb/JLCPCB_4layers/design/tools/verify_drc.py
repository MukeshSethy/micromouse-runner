"""Canonical DRC verifier -- the ONE way to check board cleanliness.

WHY THIS EXISTS (rev 6.2): `kicad-cli pcb drc --severity-warning` on KiCad
10.0.4 reports ONLY warning-severity items (included_severities == ["warning"])
-- it SILENTLY HIDES every error-severity violation. For many revs the project
gated on that command and reported "DRC 0/0/0" while the board carried 32
error-severity courtyard/placement violations. This script runs DRC at the
DEFAULT severity (error + warning) WITH schematic parity, and additionally
cross-checks the pcbnew ratsnest (kicad-cli's "unconnected" also under-reports
headless). It exits non-zero on ANY error, warning, unconnected item, parity
mismatch, or ratsnest > 0.

Usage:  python verify_drc.py            # full gate (errors AND warnings)
        python verify_drc.py --allow-warnings   # gate errors only (warnings listed)
"""
import sys, os, json, subprocess, collections

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
PCB = os.path.join(ROOT, "micromouse-pcb.kicad_pcb")
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
KPY = r"C:\Program Files\KiCad\10.0\bin\python.exe"
DRC = os.path.join(os.environ.get("TEMP", r"D:\tmp"), "verify_drc.json")
ALLOW_WARN = "--allow-warnings" in sys.argv


def run_drc():
    subprocess.run([CLI, "pcb", "drc", "--schematic-parity", "--format",
                    "json", "--output", DRC, PCB], capture_output=True)
    return json.load(open(DRC))


def ratsnest():
    """Truth for connectivity -- fill pours, build connectivity, count."""
    code = (
        "import pcbnew;b=pcbnew.LoadBoard(r'%s');"
        "pcbnew.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();"
        "print('RN=%%d'%%b.GetConnectivity().GetUnconnectedCount(True))" % PCB)
    r = subprocess.run([KPY, "-c", code], capture_output=True, text=True)
    for ln in r.stdout.splitlines():
        if ln.startswith("RN="):
            return int(ln[3:])
    return -1


def main():
    d = run_drc()
    errs = [v for v in d.get("violations", []) if v.get("severity") == "error"]
    warns = [v for v in d.get("violations", []) if v.get("severity") == "warning"]
    unc = d.get("unconnected_items", [])
    par = d.get("schematic_parity", [])
    rn = ratsnest()

    def hist(vs):
        return dict(collections.Counter(v["type"] for v in vs))

    print(f"DRC (severity error+warning, schematic-parity):")
    print(f"  errors      : {len(errs)}   {hist(errs) if errs else ''}")
    print(f"  warnings    : {len(warns)}  {hist(warns) if warns else ''}")
    print(f"  unconnected : {len(unc)}")
    print(f"  parity      : {len(par)}  {hist(par) if par else ''}")
    print(f"  ratsnest    : {rn}  (pcbnew truth; kicad-cli under-reports headless)")

    fail = []
    if errs:
        fail.append(f"{len(errs)} error-severity violations")
    if warns and not ALLOW_WARN:
        fail.append(f"{len(warns)} warning-severity violations")
    if unc:
        fail.append(f"{len(unc)} unconnected items")
    if par:
        fail.append(f"{len(par)} schematic-parity mismatches")
    if rn != 0:
        fail.append(f"ratsnest = {rn}")

    if fail:
        print("\nverify_drc: FAIL --", "; ".join(fail))
        # dump the offending items for triage
        for v in (errs + (warns if not ALLOW_WARN else []))[:60]:
            it = (v.get("items") or [{}])
            print(f"  {v['severity']:>7} {v['type']:<22} "
                  + " | ".join(x.get("description", "")[:44] for x in it))
        sys.exit(1)
    print("\nverify_drc: PASS -- 0 errors"
          + ("" if ALLOW_WARN else " / 0 warnings")
          + " / 0 unconnected / 0 parity / ratsnest 0")


if __name__ == "__main__":
    main()
