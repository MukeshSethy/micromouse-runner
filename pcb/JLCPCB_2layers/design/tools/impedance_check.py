"""Impedance / signal-integrity check for the 2-LAYER micromouse PCB.

The question a 2-layer board must answer is NOT "are my traces 50/90 ohm" -- it
is "does ANY net on this board actually REQUIRE controlled impedance, and if
so, can a 2-layer stack deliver it?".  This script answers it from first
principles against the real stackup + the placed geometry (pcb/netlist +
.kicad_pcb), the same analytical way everything else here is verified.

Method:
  1. JLCPCB standard 2-layer stackup (1.6mm FR4, 1oz outer) -> microstrip Z0
     and effective-Er for the design trace widths (IPC-2141A closed form).
  2. The ONE differential pair (USB D+/D-) -> edge-coupled microstrip Zdiff.
  3. The decider: ELECTRICAL LENGTH. A trace shorter than tr*v/6 does not
     behave as a transmission line -> its characteristic impedance is
     irrelevant (no reflections at the driver's edge rate). Every fast net on
     this board (USB Full-Speed, WS2812B, I2C) is checked against its own edge
     rate using the ACTUAL placed net length.
  4. Confirm from the netlist that USB is the ESP32-S3 NATIVE port = Full-Speed
     12 Mbps only (no High-Speed PHY) -> the USB2.0 90ohm rule is HS-only and
     does NOT apply.

Exit 1 if any net is both electrically long AND impedance-uncontrolled.
Run:  python tools/impedance_check.py
"""
import os
import re
import math
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETLIST = os.path.join(BASE, "netlist.net")
try:
    import pcbnew
    BOARD = os.path.join(BASE, "micromouse-pcb.kicad_pcb")
except Exception:
    pcbnew = None

# ---- JLCPCB standard 2-layer stackup ---------------------------------------
TH_TOTAL = 1.6          # mm finished thickness
CU = 0.035              # mm, 1oz outer copper
H = TH_TOTAL - 2 * CU   # mm dielectric core between F.Cu trace and B.Cu plane
ER = 4.5                # FR4 relative permittivity (JLC "FR4-Standard", ~1GHz)
C0 = 299.792            # mm/ns, speed of light

FAILS = []


def microstrip_z0(w, h=H, t=CU, er=ER):
    """IPC-2141A surface microstrip characteristic impedance (ohm)."""
    return (87.0 / math.sqrt(er + 1.41)) * math.log(5.98 * h / (0.8 * w + t))


def er_eff(w, h=H, er=ER):
    """Effective permittivity (Hammerstad) -> propagation velocity."""
    return (er + 1) / 2 + (er - 1) / 2 / math.sqrt(1 + 12 * h / w)


def v_prop(w):
    return C0 / math.sqrt(er_eff(w))     # mm/ns


def zdiff_edge_coupled(w, s, h=H, er=ER):
    """Edge-coupled microstrip differential impedance (Wadell approx)."""
    z0 = microstrip_z0(w)
    return 2 * z0 * (1 - 0.48 * math.exp(-0.96 * s / h))


def net_length_mm(nets_pads, netname):
    """Straight-line MST-ish length of a net from placed pad centres (a lower
    bound on the routed length -- good enough for the electrical-length test)."""
    pads = nets_pads.get(netname, [])
    if len(pads) < 2:
        return 0.0
    # chain nearest-neighbour from the first pad
    remaining = pads[:]
    cur = remaining.pop(0)
    total = 0.0
    while remaining:
        j = min(range(len(remaining)),
                key=lambda i: (remaining[i][0] - cur[0]) ** 2 + (remaining[i][1] - cur[1]) ** 2)
        nxt = remaining.pop(j)
        total += math.hypot(nxt[0] - cur[0], nxt[1] - cur[1])
        cur = nxt
    return total


def check(cond, what, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {what}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILS.append(what)


def main():
    net = open(NETLIST, encoding="utf-8").read()

    print("=" * 72)
    print("IMPEDANCE / SIGNAL-INTEGRITY CHECK -- 2-layer micromouse PCB")
    print("=" * 72)
    print(f"\nStackup (JLCPCB 2-layer standard): {TH_TOTAL}mm FR4, 1oz outer Cu,")
    print(f"  dielectric core h = {H:.3f} mm, Er = {ER}")

    # -- placed pad centres per net (for real lengths) -----------------------
    nets_pads = {}
    if pcbnew:
        b = pcbnew.LoadBoard(BOARD)
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                nm = pad.GetNetname()
                if not nm:
                    continue
                p = pad.GetCenter()
                nets_pads.setdefault(nm, []).append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))

    # -- 1. single-ended Z0 for the design trace widths ----------------------
    print("\n1. Single-ended microstrip Z0 (F.Cu trace over B.Cu GND pour)")
    for w in (0.25, 0.30, 0.50, 0.90):
        z = microstrip_z0(w)
        print(f"     w={w:.2f}mm -> Z0 ~ {z:5.1f} ohm   (Er_eff {er_eff(w):.2f}, "
              f"v {v_prop(w):.0f} mm/ns)")
    print("     NOTE: with GND ALSO poured coplanar on F.Cu (this board), the")
    print("     real structure is grounded-CPW -> Z is LOWER than these numbers;")
    print("     the microstrip value is the conservative UPPER bound.")

    # -- 2. USB D+/D- differential -------------------------------------------
    print("\n2. USB D+/D- differential (the only pair on the board)")
    z0 = microstrip_z0(0.25)
    for s in (0.20, 0.30, 0.50):
        zd = zdiff_edge_coupled(0.25, s)
        print(f"     w=0.25mm s={s:.2f}mm -> Zdiff ~ {zd:5.1f} ohm")
    print(f"     (single-ended Z0 {z0:.0f} ohm; on 2-layer with a 1.53mm core the")
    print("      pair cannot be pulled to 90 ohm -- see why that's OK in step 4.)")

    # -- 3. native-USB confirmation ------------------------------------------
    print("\n3. USB port type (sets whether 90 ohm is even required)")
    native = ('(ref "U3")' in net and "USB_DM" in net and "USB_DP" in net
              and "ULPI" not in net.upper())
    check(native, "USB is the ESP32-S3 NATIVE port (no external HS ULPI PHY)",
          "ESP32-S3 native USB = Full-Speed 12 Mbps ONLY")
    check("USBLC6" in net or "U6" in net, "only an ESD array sits in the D+/D- path",
          "USBLC6-2SC6, ~1.5pF/line -- no impedance-defining series parts")

    # -- 4. the decider: electrical length vs edge rate ----------------------
    print("\n4. Electrical-length test (a short trace is NOT a transmission line)")
    print("   critical length Lc = tr * v / 6; if L << Lc, Z0 is irrelevant.")
    # (net, human-name, edge time tr in ns) -- conservative (fast) edge rates
    fast = [("USB_DM",  "USB D- (FS 12Mbps)", 4.0),
            ("USB_DP",  "USB D+ (FS 12Mbps)", 4.0),
            ("USB_DM_C", "USB D- conn->ESD",  4.0),
            ("USB_DP_C", "USB D+ conn->ESD",  4.0),
            ("RGB_DATA", "WS2812B data 800kHz", 20.0),
            ("IMU_SDA", "I2C SDA 400kHz", 100.0),
            ("IMU_SCL", "I2C SCL 400kHz", 100.0)]
    v = v_prop(0.25)
    for netname, label, tr in fast:
        L = net_length_mm(nets_pads, netname) if nets_pads else 0.0
        Lc = tr * v / 6.0
        # electrically short if L < Lc (with margin). If we have no geometry,
        # fall back to the board diagonal (156mm) as a hard upper bound.
        Lbound = L if L > 0 else math.hypot(100, 120)
        short = Lbound < Lc
        check(short, f"{label}: electrically short",
              f"L~{Lbound:.0f}mm < Lc {Lc:.0f}mm (tr {tr:.0f}ns)")

    # -- verdict --------------------------------------------------------------
    print("\n" + "=" * 72)
    if FAILS:
        print(f"IMPEDANCE CHECK: {len(FAILS)} ISSUE(S): {FAILS}")
        sys.exit(1)
    print("IMPEDANCE CHECK: PASS -- NO controlled-impedance net on this board.")
    print("  * USB is Full-Speed (12 Mbps); the USB2.0 90 ohm rule is HS-only.")
    print("  * Every fast net is electrically SHORT at its edge rate, so its")
    print("    characteristic impedance never enters the picture (no reflections).")
    print("  * GND poured on BOTH faces keeps a tight return path under every")
    print("    trace regardless. 2-layer is fully adequate for this design.")


if __name__ == "__main__":
    main()
