"""NEGATIVE tests: prove the firmware gates and simulations actually FAIL
when given faulty inputs (a gate that cannot fail proves nothing).

Each case injects one deliberate fault into a TEMP COPY (repo untouched)
and asserts the corresponding gate DETECTS it (non-zero exit):

  N1  wrong GPIO in pins.h        -> check_pins.py 3-way gate must fail
  N2  CC pulldown removed from a  -> sim_flash.py stage 1 must fail
      netlist copy                   (host would never enumerate the board)
  N3  inverted steering in the    -> sim_linefollow scenarios must fail
      control core                   (classic sign bug)
  N4  estimator deadband removed  -> sim_hw S2 must fail (the real bug this
      (re-inject the fixed bug)      sim originally caught)

Run:  python fw/test_negative.py     (exit 1 if any fault goes UNDETECTED)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

FW = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(FW)
PY = sys.executable
FAILED = []


def report(name, detected, detail):
    print(f"[{'DETECTED' if detected else 'MISSED!!'}] {name} -- {detail}")
    if not detected:
        FAILED.append(name)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


def main():
    tmp = tempfile.mkdtemp(prefix="fw_neg_")
    print("NEGATIVE-TEST HARNESS (fault-injection on temp copies)")
    print("=" * 64)

    # ---- N1: wrong GPIO in pins.h ----------------------------------------
    src = open(os.path.join(FW, "micromouse", "pins.h"), encoding="utf-8").read()
    bad = re.sub(r"(#define\s+PIN_WALL1_SENSE\s+)\d+",
                 r"\g<1>7", src, count=1)   # 7 is MUX_SENSE's GPIO
    assert re.search(r"#define\s+PIN_WALL1_SENSE\s+7\b", bad), "N1 injection failed"
    negdir = os.path.join(tmp, "n1", "micromouse")
    os.makedirs(negdir)
    open(os.path.join(negdir, "pins.h"), "w", encoding="utf-8").write(bad)
    # run check_pins against the faulty pins.h via a patched copy
    chk = open(os.path.join(FW, "check_pins.py"), encoding="utf-8").read()
    chk = chk.replace(r'BASE + r"\fw\micromouse\pins.h"',
                      repr(os.path.join(negdir, "pins.h")))
    assert "pins.h')" in chk or 'pins.h")' in chk.replace("\\\\", "/"), \
        "check_pins patch failed to apply"
    chk_p = os.path.join(tmp, "n1", "check_pins_neg.py")
    open(chk_p, "w", encoding="utf-8").write(chk)
    rc, out = run([PY, chk_p])
    report("N1 wrong GPIO in pins.h", rc != 0 and "NOT on net" in out,
           "PIN_WALL1_SENSE moved to GPIO 7 (MUX_SENSE's pin)")

    # ---- N2: CC pulldown removed from the netlist -------------------------
    nl = open(os.path.join(ROOT, "pcb", "netlist.net"), encoding="utf-8").read()
    # remove R12's node from the CC1 net block (host would not enumerate)
    i = nl.find('(name "Net-(J7-CC1)")')
    j = nl.find('(net', i + 10)
    block = nl[i:j]
    block_bad = re.sub(r'\(node\s*\(ref "R12"\).*?\)\s*\)', "", block, flags=re.S)
    nl_bad = nl[:i] + block_bad + nl[j:]
    nl_p = os.path.join(tmp, "netlist_noCC.net")
    open(nl_p, "w", encoding="utf-8").write(nl_bad)
    rc, out = run([PY, os.path.join(FW, "sim_flash.py"), nl_p])
    report("N2 CC1 pulldown removed", rc != 0 and "5.1k-class pulldown" in out,
           "R12 deleted from Net-(J7-CC1) -> enumeration impossible")

    # ---- N3: inverted steering in the control core ------------------------
    cc = open(os.path.join(FW, "micromouse", "control_core.c"), encoding="utf-8").read()
    # rename the parameter, then shadow it with an inverted local inside the body
    cc_bad = re.sub(r"void drive_mix\(float base, float steer",
                    "void drive_mix(float base, float steer_orig", cc, count=1)
    cc_bad = re.sub(r"(void drive_mix\([^)]*\)\s*\{)",
                    r"\1\n    float steer = -steer_orig;  /* FAULT: inverted sign */",
                    cc_bad, count=1)
    assert "steer_orig" in cc_bad and "FAULT" in cc_bad, "N3 injection failed"
    n3 = os.path.join(tmp, "n3")
    os.makedirs(n3)
    open(os.path.join(n3, "control_core.c"), "w", encoding="utf-8").write(cc_bad)
    shutil.copy(os.path.join(FW, "micromouse", "control_core.h"), n3)
    exe = os.path.join(n3, "sim_lf.exe")
    rc, out = run(["gcc", "-O2", "-I", n3, "-o", exe,
                   os.path.join(FW, "sim", "sim_linefollow.c"),
                   os.path.join(n3, "control_core.c"), "-lm"])
    if rc != 0:
        report("N3 inverted steering", False, "fault build failed: " + out[:120])
    else:
        rc, out = run([exe])
        report("N3 inverted steering", rc != 0,
               "drive_mix steer sign flipped -> robot must lose the line")

    # ---- N4: estimator deadband removed (re-inject the fixed bug) ---------
    cc_bad = cc.replace("if (v < 0.15f) v = 0;",
                        "/* FAULT: deadband removed */")
    n4 = os.path.join(tmp, "n4")
    os.makedirs(n4)
    open(os.path.join(n4, "control_core.c"), "w", encoding="utf-8").write(cc_bad)
    shutil.copy(os.path.join(FW, "micromouse", "control_core.h"), n4)
    exe = os.path.join(n4, "sim_hw.exe")
    rc, out = run(["gcc", "-I", n4, "-o", exe,
                   os.path.join(FW, "sim", "sim_hw.c"),
                   os.path.join(n4, "control_core.c"), "-lm"])
    if rc != 0:
        report("N4 deadband removed", False, "fault build failed: " + out[:120])
    else:
        rc, out = run([exe])
        report("N4 deadband removed", rc != 0 and "estimator" in out,
               "idle-floor bias re-injected -> S2 must fail (the bug sim_hw caught)")

    shutil.rmtree(tmp, ignore_errors=True)
    print("=" * 64)
    if FAILED:
        print(f"NEGATIVE TESTS: {len(FAILED)} fault(s) went UNDETECTED: {FAILED}")
        sys.exit(1)
    print("NEGATIVE TESTS: all 4 injected faults DETECTED -- the gates are live.")


if __name__ == "__main__":
    main()
