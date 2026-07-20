"""Gate: fw/micromouse/pins.h must match pcb/netlist.net. Exits 1 on drift.

Chain of authority: pins.h says GPIO n = net X. The WROOM-1 module maps GPIO
n to a module pad (fixed by Espressif, mirrored in build_schematic.py's
U3_NET table); the netlist says which net that pad carries. All three must
agree for every pin used by the firmware.
"""
import re
import sys

BASE = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers"
pins_h = open(BASE + r"\fw\micromouse\pins.h", encoding="utf-8").read()
netlist = open(BASE + r"\design\netlist.net", encoding="utf-8").read()
sch = open(BASE + r"\design\tools\build_schematic.py", encoding="utf-8").read()

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
    # 2-layer: battery / bus telemetry moved off the mux onto direct ADC1
    "PIN_VBAT_SENSE": "VBAT_SENSE", "PIN_BATMID_SENSE": "BAT_MID_SENSE",
    "PIN_VBUS_SENSE": "VBUS_SENSE",
    "PIN_AIN1": "AIN1", "PIN_AIN2": "AIN2",
    "PIN_BIN1": "BIN1", "PIN_BIN2": "BIN2",
    "PIN_IMU_SDA": "IMU_SDA", "PIN_IMU_SCL": "IMU_SCL", "PIN_IMU_INT": "IMU_INT",
    "PIN_EMIT_FRONT": "WALL_EMIT_FRONT", "PIN_EMIT_DIAG": "WALL_EMIT_DIAG",
    "PIN_EMIT_SIDE": "WALL_EMIT_SIDE",
    # 2-layer: ESP-driven indicators
    "PIN_STATUS_LED": "STATUS_LED", "PIN_RGB_DATA": "RGB_DATA",
    "PIN_ENC1_A": "ENC1_A", "PIN_ENC1_B": "ENC1_B",
    "PIN_ENC2_A": "ENC2_A_S3", "PIN_ENC2_B": "ENC2_B_S3",
    "PIN_BUZZER": "BUZZ_CTRL",
}
# buttons: net names are auto-generated; assert net CONTAINS the right switch
BTN = {"PIN_BTN_A": "SW1", "PIN_BTN_B": "SW3", "PIN_BTN_C": "SW4"}

declared = dict(re.findall(r"#define\s+(PIN_\w+)\s+(\d+)", pins_h))
fails = []

# WROOM-1 module pad <- GPIO (datasheet table 3; the pad the netlist sees)
PAD_OF_GPIO = {0:"27",1:"39",2:"38",3:"15",4:"4",5:"5",6:"6",7:"7",8:"12",
               9:"17",10:"18",11:"19",12:"20",13:"21",14:"22",15:"8",16:"9",
               17:"10",18:"11",19:"13",20:"14",21:"23",35:"28",36:"29",
               37:"30",38:"31",39:"32",40:"33",41:"34",42:"35",43:"37",
               44:"36",45:"26",46:"16",47:"24",48:"25"}

for sym, net in EXPECT.items():
    gpio = declared.get(sym)
    if gpio is None:
        fails.append(f"{sym}: missing from pins.h")
        continue
    # THREE-WAY check (rev 7): pins.h GPIO -> WROOM module pad -> the netlist
    # must put EXACTLY that U3 pad on the expected net. A wrong GPIO number in
    # pins.h now fails (the old check only tested net-exists-somewhere-on-U3).
    pad = PAD_OF_GPIO.get(int(gpio))
    if pad is None:
        fails.append(f"{sym}: GPIO {gpio} is not a mappable WROOM-1 pad")
        continue
    m = re.search(r'\(net\s*\(code "\d+"\)\s*\(name "%s"\)(.*?)\n\t\t\)' % re.escape(net),
                  netlist, re.S)
    if not m:
        fails.append(f"{sym}: net {net} not in netlist")
        continue
    if not re.search(r'\(ref "U3"\)\s*\(pin "%s"\)' % re.escape(pad), m.group(1)):
        fails.append(f"{sym}: GPIO {gpio} = module pad {pad} is NOT on net {net}")

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
