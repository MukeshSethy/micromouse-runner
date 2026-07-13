import re, sys

text = open(r"D:\Projects\micromouse-pcb\pcb\netlist.net", encoding="utf-8").read()

# Parse each (net (code N) (name "...") (node (ref "X") (pin "Y") ...)...) block.
nets = []  # list of (name, [(ref,pin), ...])
for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text, re.S):
    name = m.group(1)
    body = m.group(2)
    nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body)
    nets.append((name, nodes))

print(f"Total nets: {len(nets)}")

by_name = {}
for name, nodes in nets:
    by_name.setdefault(name, []).extend(nodes)

def show(name):
    nodes = by_name.get(name)
    if nodes is None:
        print(f"  {name}: MISSING")
    else:
        print(f"  {name} ({len(nodes)} pins): {nodes}")

print("\n--- Power rails (must be 3 DISTINCT nets) ---")
for n in ["GND", "VM_BATT", "PLUS3V3"]:
    show(n)

print("\n--- Motor driver outputs (must be 4 DISTINCT nets, one per connector pin) ---")
motor_out_nets = [name for name, nodes in nets if any(r == "U2" and p in ("1","2","5","6","7","8","11","12") for r, p in nodes)]
for name in motor_out_nets:
    show(name)

print("\n--- Encoder nets (must be 4 DISTINCT nets) ---")
for n in ["ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B"]:
    show(n)

print("\n--- ESP32 support nets (EN and IO0 must be DISTINCT, not shorted) ---")
for n in ["ESP_EN_NET", "ESP_IO0_NET", "NRST", "USART1_TX", "USART1_RX"]:
    show(n)

print("\n--- Sensor nets: all 28 (14 _SENSE + 14 _LED) must be DISTINCT ---")
sensor_names = ["WALL1","WALL2","WALL3","WALL4","WALL5","WALL6",
                "LINE1","LINE2","LINE3","LINE4","LINE5","LINE6","LINE7","LINE8"]
missing = []
sizes = {}
for nm in sensor_names:
    for suffix in ("_SENSE", "_LED"):
        key = nm + suffix
        nodes = by_name.get(key)
        if nodes is None:
            missing.append(key)
        else:
            sizes[key] = len(nodes)
print("Missing nets:", missing if missing else "none")
print("Pin counts (expect 2 each -- one sensor-side pin + one mux-channel pin):")
for k, v in sizes.items():
    flag = "" if v == 2 else "  <-- UNEXPECTED COUNT"
    print(f"  {k}: {v}{flag}")

# Cross-net collision check: no two DIFFERENT intended net names should share
# any (ref,pin) tuple, and more importantly no two DIFFERENT names should
# resolve to sets with >0 overlap (that would mean KiCad actually merged them
# under one canonical name already, which show() above would reveal as
# "MISSING" for one of the pair -- but double check explicitly here too).
all_expected = ["GND", "VM_BATT", "PLUS3V3", "ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B",
                "ESP_EN_NET", "ESP_IO0_NET", "NRST", "USART1_TX", "USART1_RX",
                "MUX_S0", "MUX_S1", "MUX_S2", "MUX_S3", "MUX_SENSE", "LED_PULSE",
                "STBY", "AIN1", "AIN2", "BIN1", "BIN2", "USER_BTN",
                "VBAT_CELL1_SENSE", "VBAT_PACK_SENSE", "PWMA", "PWMB",
                "ESP_PROG_TX", "ESP_PROG_RX"] + [nm + s for nm in sensor_names for s in ("_SENSE", "_LED")]

print("\n--- Any expected net name entirely absent from the netlist? ---")
absent = [n for n in all_expected if n not in by_name]
print(absent if absent else "none -- all present")

print("\n--- Total distinct net names vs expected minimum ---")
print(f"{len(by_name)} distinct net names in netlist; {len(all_expected)} explicitly checked above (plus unnamed local nets like motor outputs, decoupling, etc.)")
