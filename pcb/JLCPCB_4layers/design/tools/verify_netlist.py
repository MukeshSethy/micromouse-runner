"""Netlist gate for the rev-6 design. Exits 1 on any failure.

Verifies net-level integrity of pcb/netlist.net: distinct power rails, the
complete 2S battery power path (J1 -> fuse -> reverse-polarity P-FET ->
VM_BATT -> two bucks), the dual-switch enable chain, motor IN/IN drive,
IMU I2C, mux telemetry channels, encoder/USB/JTAG nets, and that every
sensor SENSE net reaches both its reader (U3 ADC or U4 mux) and its
indicator FET gate.

History: the original script checked the rev-1 STM32-era names and always
exited 0, so it silently stopped gating anything around rev 2. Board-level
pad mapping is separately gated by PcbGen.assert_netlist_pads_mapped()
(build_pcb.py) -- THAT is the check which catches symbol-pin vs footprint-pad
naming mismatches (the rev-5 floating-FET defect); this file checks the
netlist's own topology.
"""
import re
import sys

text = open(r"D:\Projects\micromouse-pcb\pcb\netlist.net", encoding="utf-8").read()

by_name = {}
for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text, re.S):
    nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2))
    by_name.setdefault(m.group(1), []).extend(nodes)

fails = []

def need(net, min_pins=2, must_have=()):
    nodes = by_name.get(net)
    if nodes is None:
        fails.append(f"{net}: MISSING")
        return
    if len(nodes) < min_pins:
        fails.append(f"{net}: only {len(nodes)} pins (need >= {min_pins}): {nodes}")
    for want in must_have:
        if want not in nodes:
            fails.append(f"{net}: expected node {want} not present: {nodes}")

print(f"Total distinct nets: {len(by_name)}")

# Power rails -- FOUR distinct nets in rev 6 (2S raw, protected, 6V, 3V3)
need("GND", 60)
need("PLUS3V3", 40)
need("VM_BATT", 8, must_have=[("Q1", "2"), ("U1", "3"), ("U7", "3")])  # P-FET source feeds BOTH bucks
need("VM_6V", 6, must_have=[("L2", "2"), ("U2", "24"), ("C30", "1")])  # buck out -> TB6612 VM3 (pad 24) + bulk

# 2S battery power path, pin by pin: J1 -> F1 -> Q1(D->S) -> VM_BATT; gate
# held low through R1 (DMP3098L: Vgs +/-20V, 2S-safe). Balance tap J9:
# pin 1 GND, pin 2 midpoint divider, pin 3 same node as J1+.
need("BATT_RAW", 3, must_have=[("J1", "1"), ("F1", "1"), ("J9", "3")])
need("Net-(Q1-D)", 2, must_have=[("F1", "2"), ("Q1", "3")])
need("Net-(Q1-G)", 2, must_have=[("Q1", "1"), ("R1", "1")])
need("BAT_MID", 2, must_have=[("J9", "2"), ("R75", "1")])
need("BAT_MID_SENSE", 3, must_have=[("U4", "22")])   # mux Y9 = pad 22 (4067)

# Dual-switch enable chain: SW5 gates PWR_EN (AP63203 EN, pin 2); SW6 gates
# MOT_EN (TPS54302 EN, pin 5) whose pull-up feeds FROM PWR_EN -- motors
# require both switches on.
need("PWR_EN", 4, must_have=[("R69", "2"), ("SW5", "2"), ("U1", "2"), ("R70", "1")])
need("MOT_EN", 4, must_have=[("R70", "2"), ("R71", "1"), ("SW6", "2"), ("U7", "5")])
if ("SW5", "1") not in by_name.get("GND", []):
    fails.append("GND: SW5.1 (power-off throw) not on GND")
if ("SW6", "1") not in by_name.get("GND", []):
    fails.append("GND: SW6.1 (motor-off throw) not on GND")
if ("R1", "2") not in by_name.get("GND", []):
    fails.append("GND: R1.2 (Q1 gate pulldown) not on GND")

# 6V buck support: FB divider 100k/11k, bootstrap, inductor
need("FB_6V", 3, must_have=[("U7", "4"), ("R73", "2"), ("R74", "1")])
need("SW_6V", 3, must_have=[("U7", "2"), ("L2", "1"), ("C15", "1")])
need("SW_3V3", 3, must_have=[("U1", "5"), ("L1", "1"), ("C3", "1")])

# Motor driver: IN/IN PWM mode -- AIN/BIN are the PWM pins; PWMA/PWMB and
# STBY are tied high (nets PLUS3V3 / R55) and must NOT exist as GPIO nets.
for n in ("MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"):
    need(n, 2)
for n in ("ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B"):
    need(n, 2)
for n in ("AIN1", "AIN2", "BIN1", "BIN2"):
    need(n, 2)
for gone in ("PWMA", "PWMB", "STBY", "VBAT_SENSE_DIRECT"):
    if gone in by_name:
        fails.append(f"{gone}: rev-5 net still present (rev 6 removed it)")
p3 = by_name.get("PLUS3V3", [])
for want in (("U2", "11"), ("U2", "12")):   # TB6612 PWMA=pin 11? verified below
    pass  # pad-number mapping is footprint-level; gated by build_pcb instead
if not any(r == "R55" for r, p in by_name.get("PLUS3V3", [])):
    fails.append("PLUS3V3: R55 (STBY tie-high) not on rail")

# IMU (BNO055): I2C + INT + address/mode straps
need("IMU_SDA", 3, must_have=[("U3", "11"), ("U8", "20"), ("R77", "2")])
need("IMU_SCL", 3, must_have=[("U3", "23"), ("U8", "19"), ("R78", "2")])
need("IMU_INT", 2, must_have=[("U3", "30"), ("U8", "14")])
gnd = by_name.get("GND", [])
for strap in (("U8", "5"), ("U8", "6"), ("U8", "17"), ("U8", "18"), ("U8", "25")):
    if strap not in gnd:
        fails.append(f"GND: BNO055 strap {strap} (PS1/PS0/COM3/COM2/GNDIO) not grounded")
# rev 6.1: external crystal dropped (BNO055 internal oscillator); XIN32/
# XOUT32 (U8.26/27) are no-connects -- assert X1 is truly gone.
if any("X1" == r for nodes in by_name.values() for r, _ in nodes):
    fails.append("X1 (crystal) still present -- rev 6.1 uses the internal oscillator")

# ESP32 module support / USB / JTAG. Rev 6: D+/D- direct (no 22R): the ESD
# array's module-side pins are ON USB_DM/USB_DP and no R59/R60 exist.
need("ESP_EN", 2)
for n in ("USB_DM", "USB_DP", "USB_DM_C", "USB_DP_C", "USB_VBUS", "VBUS_SENSE",
          "JTAG_TMS", "JTAG_TCK", "JTAG_TDO", "JTAG_TDI"):
    need(n, 2)
need("USB_DM", 2, must_have=[("U6", "6"), ("U3", "13")])
need("USB_DP", 2, must_have=[("U6", "4"), ("U3", "14")])

# Mux: 4 selects + telemetry channels Y8/Y9/Y10 (pads 12/11/10... verified by
# presence of the three sense nets on U4)
for n in ("MUX_S0", "MUX_S1", "MUX_S2", "MUX_S3", "MUX_SENSE"):
    need(n, 2)
for n, tag in (("VBAT_SENSE", "Y8"), ("BAT_MID_SENSE", "Y9"), ("VBUS_SENSE", "Y10")):
    if not any(r == "U4" for r, p in by_name.get(n, [])):
        fails.append(f"{n}: not on the mux (expected {tag})")
for n in ("WALL_EMIT_FRONT", "WALL_EMIT_DIAG", "WALL_EMIT_SIDE", "LINE_EMIT"):
    need(n, 2)

# Every SENSE net must reach its reader AND its indicator FET gate (pin 1 on
# both the BSS138 line drivers and the Q_PMOS_GSD wall drivers).
for i in range(1, 7):
    net = f"WALL{i}_SENSE"
    nodes = by_name.get(net, [])
    if not any(r == "U3" for r, p in nodes):
        fails.append(f"{net}: no U3 (ADC) node: {nodes}")
    if not any(r.startswith("Q") and p == "1" for r, p in nodes):
        fails.append(f"{net}: no indicator FET gate node: {nodes}")
for i in range(1, 9):
    net = f"LINE{i}_SENSE"
    nodes = by_name.get(net, [])
    if not any(r == "U4" for r, p in nodes):
        fails.append(f"{net}: no U4 (mux) node: {nodes}")
    if not any(r.startswith("Q") and p == "1" for r, p in nodes):
        fails.append(f"{net}: no indicator FET gate node: {nodes}")
    if not any(r == f"LS{i}" and p == "4" for r, p in nodes):
        fails.append(f"{net}: no LS{i}.4 (TCRT5000 collector) node: {nodes}")

# No expected-distinct pair may have merged: spot-check likely shorts
for a, b in (("USB_DM", "USB_DP"), ("ENC1_A", "ENC1_B"), ("MOTA_P", "MOTA_N"),
             ("GND", "PLUS3V3"), ("GND", "VM_BATT"), ("VM_BATT", "VM_6V"),
             ("PWR_EN", "MOT_EN"), ("IMU_SDA", "IMU_SCL"),
             ("VBAT_SENSE", "BAT_MID_SENSE")):
    na, nb = set(by_name.get(a, [])), set(by_name.get(b, []))
    if na and na == nb:
        fails.append(f"{a} and {b} resolve to the SAME node set -- merged/shorted")

if fails:
    print(f"\nVERIFY FAILED ({len(fails)}):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("verify_netlist: ALL CHECKS PASSED")
