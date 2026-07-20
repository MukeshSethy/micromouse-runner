"""THT board CLOSER -- autonomous route -> verify -> heal -> re-verify, with a
STUCK detector, ending in one definitive verdict. Run this ONE job; on its
completion read the final VERDICT line. No passive waiting, no per-round
babysitting.

Stages (each bounded, each prints progress with flush):
  1. route_tht.py          (fast-fail bounded, incremental save)
  2. verify_board.py       (ratsnest + DRC)  -> if PASS, done
  3. heal_all.py           ONLY if ratsnest>0, with a watchdog: if the board
                           file mtime doesn't advance for STUCK_S seconds the
                           heal is killed (heal_all sat 18min saving nothing)
  4. verify_board.py again -> final verdict

Prints a machine-readable final line: FINAL: PASS|FAIL rn=.. err=.. warn=..
"""
import os, sys, time, subprocess, threading

BASE = r"D:\Projects\micromouse-pcb\tht-assembly\pcb"
TOOLS = os.path.join(BASE, "tools")
BOARD = os.path.join(BASE, "micromouse-tht.kicad_pcb")
KPY = r"C:\Program Files\KiCad\10.0\bin\python.exe"
PY = r"C:\msys64\ucrt64\bin\python3.exe"
STUCK_S = 180          # kill a stage that saves nothing for this long
LOG = open(os.path.join(r"D:\tmp", "close_tht.log"), "w", buffering=1)


def say(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    LOG.write(line + "\n"); LOG.flush()


def run_stage(name, cmd, watchdog=False):
    """Run a stage; if watchdog, kill it when BOARD mtime stalls for STUCK_S."""
    say(f"STAGE {name}: start")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, bufsize=1)
    killed = {"v": False}
    if watchdog:
        def guard():
            last = os.path.getmtime(BOARD) if os.path.exists(BOARD) else 0
            stall = 0
            while p.poll() is None:
                time.sleep(15)
                now = os.path.getmtime(BOARD) if os.path.exists(BOARD) else 0
                if now > last:
                    last = now; stall = 0
                else:
                    stall += 15
                    if stall >= STUCK_S:
                        say(f"STAGE {name}: STUCK ({STUCK_S}s no save) -> kill")
                        killed["v"] = True
                        p.kill(); return
        threading.Thread(target=guard, daemon=True).start()
    for ln in p.stdout:
        ln = ln.rstrip()
        if ln and not any(s in ln for s in ("memory leak", "duplicate image")):
            say(f"  {name}| {ln}")
    p.wait()
    say(f"STAGE {name}: exit {p.returncode}{' (killed-stuck)' if killed['v'] else ''}")
    return p.returncode, killed["v"]


def verify():
    p = subprocess.run([KPY, os.path.join(TOOLS, "verify_board.py")],
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    verdict = [l for l in out.splitlines() if l.startswith("VERDICT")]
    say(f"VERIFY: {verdict[0] if verdict else out.strip()[-120:]}")
    # parse ratsnest
    rn = None
    for l in out.splitlines():
        if "ratsnest" in l.lower() and l.strip().startswith("ratsnest"):
            try: rn = int(l.split(":")[1].strip())
            except Exception: pass
    return p.returncode == 0, (rn if rn is not None else -1), (verdict[0] if verdict else "")


def main():
    t0 = time.time()
    # 1. route
    run_stage("route", [KPY, "-u", os.path.join(TOOLS, "route_tht.py")])
    ok, rn, v = verify()
    if ok:
        say(f"FINAL: PASS after route ({time.time()-t0:.0f}s) | {v}")
        return
    # 3. heal only if there's a ratsnest to close
    if rn != 0:
        run_stage("heal", [KPY, os.path.join(TOOLS, "heal_all.py")], watchdog=True)
        ok, rn, v = verify()
    say(f"FINAL: {'PASS' if ok else 'FAIL'} after {time.time()-t0:.0f}s | {v}")


if __name__ == "__main__":
    main()
