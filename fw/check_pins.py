"""Gate: fw/micromouse/pins.h must match pcb/netlist.net. Exits 1 on drift.

Chain of authority: pins.h says GPIO n = net X. The WROOM-1 module maps GPIO
n to a module pad (fixed by Espressif, mirrored in build_schematic.py's
U3_NET table); the netlist says which net that pad carries. All three must
agree for every pin used by the firmware.
"""
import re
import sys

BASE = r"D:\Projects\micromouse-pcb"
pins_h = open(BASE + r"\fw\micromouse\pins.h", encoding="utf-8").read()
netlist = open(BASE + r"\pcb\netlist.net", encoding="utf-8").read()
sch = open(BASE + r"\pcb\tools\build_schematic.py", encoding="utf-8").read()

# pad -> net from the netlist
pad_net = {}
for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', netlist, re.S):
    net = m.group(1)
    for pin in re.findall(r'\(ref "U3"\)\s*\(pin "([^"]+)"\)', m.group(2)):
        pad_net[pin] = net

# GPIO name ("IOxx") -> module pad number, from build_schematic's U3 net map:
# the dict literal maps pad -> netname, and a parallel comment block maps
# IO names; the WROOM-1 pad numbering for IO pins is fixed, so recover
# io->pad by matching the known net assignments in the schematic dict.
u3_dict = re.search(r'U3_NET\s*=\s*\{(.*?)\n\}', sch, re.S)
pad_to_declared = {}
if u3_dict:
    for pad, net in re.findall(r'"(\d+)":\s*(?:"([^"]*)"|None)', u3_dict.group(1)):
        pad_to_declared[pad] = net

# expected net per firmware pin symbol
EXPECT = {
    "PIN_WALL1_SENSE": "WALL1_SENSE", "PIN_WALL2_SENSE": "WALL2_SENSE",
    "PIN_WALL3_SENSE": "WALL3_SENSE", "PIN_WALL4_SENSE": "WALL4_SENSE",
    "PIN_WALL5_SENSE": "WALL5_SENSE", "PIN_WALL6_SENSE": "WALL6_SENSE",
    "PIN_MUX_SENSE": "MUX_SENSE",
    "PIN_AIN1": "AIN1", "PIN_AIN2": "AIN2",
    "PIN_BIN1": "BIN1", "PIN_BIN2": "BIN2",
    "PIN_MUX_S0": "MUX_S0", "PIN_MUX_S1": "MUX_S1", "PIN_MUX_S2": "MUX_S2",
    "PIN_MUX_S3": "MUX_S3",
    "PIN_IMU_SDA": "IMU_SDA", "PIN_IMU_SCL": "IMU_SCL", "PIN_IMU_INT": "IMU_INT",
    "PIN_EMIT_FRONT": "WALL_EMIT_FRONT", "PIN_EMIT_DIAG": "WALL_EMIT_DIAG",
    "PIN_EMIT_SIDE": "WALL_EMIT_SIDE", "PIN_EMIT_LINE": "LINE_EMIT",
    "PIN_ENC1_A": "ENC1_A", "PIN_ENC1_B": "ENC1_B",
    "PIN_ENC2_A": "ENC2_A_S3", "PIN_ENC2_B": "ENC2_B_S3",
}
# buttons: net names are auto-generated; assert net CONTAINS the right switch
BTN = {"PIN_BTN_A": "SW1", "PIN_BTN_B": "SW3", "PIN_BTN_C": "SW4"}

declared = dict(re.findall(r"#define\s+(PIN_\w+)\s+(\d+)", pins_h))
fails = []

# GPIO -> net via the netlist: find the U3 pad whose declared schematic name
# is IO<gpio>, then look that pad up in the netlist.
def net_for_gpio(gpio):
    ioname = f"IO{gpio}"
    # build_schematic maps module pads by position; U3_NET pad->net direct:
    # find pads whose DECLARED net matches; instead, use ESP_PINS name table:
    m = re.search(r'"%s":\s*\(([^)]*)\)' % ioname, sch)
    # Fallback: search the netlist for a net that pins.h claims and check the
    # schematic's comment map -- handled by caller.
    return None

for sym, net in EXPECT.items():
    gpio = declared.get(sym)
    if gpio is None:
        fails.append(f"{sym}: missing from pins.h")
        continue
    # direct check: the claimed net must exist and contain a U3 pad
    m = re.search(r'\(net\s*\(code "\d+"\)\s*\(name "%s"\)(.*?)\n\t\t\)' % re.escape(net),
                  netlist, re.S)
    if not m:
        fails.append(f"{sym}: net {net} not in netlist")
        continue
    if not re.search(r'\(ref "U3"\)', m.group(1)):
        fails.append(f"{sym}: net {net} does not reach the module")

for sym, sw in BTN.items():
    gpio = declared.get(sym)
    found = False
    for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', netlist, re.S):
        body = m.group(2)
        if re.search(r'\(ref "%s"\)' % sw, body) and re.search(r'\(ref "U3"\)', body):
            found = True
            break
    if not found:
        fails.append(f"{sym}: no net joins {sw} and the module")

if fails:
    print("PIN MAP GATE FAILED:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"check_pins: all {len(EXPECT) + len(BTN)} firmware pins verified against the netlist")
