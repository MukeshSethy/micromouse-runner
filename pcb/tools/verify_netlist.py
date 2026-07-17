"""Netlist gate for the rev-5 design. Exits 1 on any failure.

Verifies net-level integrity of pcb/netlist.net: distinct power rails, the
complete battery power path (J2 -> fuse -> reverse-polarity P-FET -> VM_BATT),
motor/encoder/USB/JTAG nets, and that every sensor SENSE net reaches both its
reader (U3 ADC or U4 mux) and its indicator FET gate.

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

# Power rails -- three distinct nets with realistic fanout
need("GND", 60)
need("PLUS3V3", 40)
need("VM_BATT", 10, must_have=[("Q1", "2")])   # P-FET source feeds the rail

# Battery power path, pin by pin: J1 -> F1 -> Q1(D->S) -> VM_BATT; gate held
# low through R1. This exact chain was broken in shipped rev 5 (floating Q1).
need("Net-(J1-Pin_1)", 2, must_have=[("J1", "1"), ("F1", "1")])
need("Net-(Q1-D)", 2, must_have=[("F1", "2"), ("Q1", "3")])
need("Net-(Q1-G)", 2, must_have=[("Q1", "1"), ("R1", "1")])
# Soft power switch (rev 5.3): R69 pull-up + SW5-to-GND on the regulator EN
need("PWR_EN", 3, must_have=[("R69", "2"), ("SW5", "2"), ("U1", "6")])
if ("SW5", "1") not in by_name.get("GND", []):
    fails.append("GND: SW5.1 (power-off throw) not on GND")
if ("R1", "2") not in by_name.get("GND", []):
    fails.append("GND: R1.2 (Q1 gate pulldown) not on GND")

# Motor driver / encoders
for n in ("MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"):
    need(n, 2)
for n in ("ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B"):
    need(n, 2)
for n in ("PWMA", "PWMB", "AIN1", "AIN2", "BIN1", "BIN2", "STBY"):
    need(n, 2)

# ESP32 module support / USB / JTAG
need("ESP_EN", 2)
for n in ("USB_DM", "USB_DP", "USB_DM_C", "USB_DP_C", "USB_VBUS", "VBUS_SENSE",
          "JTAG_TMS", "JTAG_TCK", "JTAG_TDO", "JTAG_TDI"):
    need(n, 2)

# Mux + emitter rails
for n in ("MUX_S0", "MUX_S1", "MUX_S2", "MUX_SENSE"):
    need(n, 2)
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

# No expected-distinct pair may have merged: spot-check a few likely shorts
for a, b in (("USB_DM", "USB_DP"), ("ENC1_A", "ENC1_B"), ("MOTA_P", "MOTA_N"),
             ("GND", "PLUS3V3"), ("GND", "VM_BATT")):
    na, nb = set(by_name.get(a, [])), set(by_name.get(b, []))
    if na and na == nb:
        fails.append(f"{a} and {b} resolve to the SAME node set -- merged/shorted")

if fails:
    print(f"\nVERIFY FAILED ({len(fails)}):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("verify_netlist: ALL CHECKS PASSED")
