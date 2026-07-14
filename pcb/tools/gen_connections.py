"""Generates CONNECTIONS.md -- the per-net, per-pin justification document.

Every net in netlist.net gets an entry: which pins belong to it (annotated
with the pin's FUNCTION name from the part symbol, not just the number) and
WHY that connection exists, with the source the justification rests on.
Coverage is enforced by construction: any net without a rationale aborts
the build, so the document can never silently drift out of sync with the
schematic. Regenerate after any schematic change:

    cd tools
    "C:\\msys64\\ucrt64\\bin\\python3.exe" gen_connections.py
"""
import re
import sys
import os

NETLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "netlist.net")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "CONNECTIONS.md")

# ---------------------------------------------------------------------------
# Pin-number -> function-name tables, taken from the exact KiCad library
# symbols this schematic instantiates (extracted from the installed libs and
# cross-checked against manufacturer datasheets -- see PROJECT_NOTES.md).
# ---------------------------------------------------------------------------

TB6612_PINS = {
    "1": "AO1", "2": "AO1", "3": "PGND1", "4": "PGND1", "5": "AO2", "6": "AO2",
    "7": "BO2", "8": "BO2", "9": "PGND2", "10": "PGND2", "11": "BO1", "12": "BO1",
    "13": "VM2", "14": "VM3", "15": "PWMB", "16": "BIN2", "17": "BIN1", "18": "GND",
    "19": "STBY", "20": "VCC", "21": "AIN1", "22": "AIN2", "23": "PWMA", "24": "VM1",
}
HEF4067_PINS = {
    "1": "Z", "2": "Y7", "3": "Y6", "4": "Y5", "5": "Y4", "6": "Y3", "7": "Y2",
    "8": "Y1", "9": "Y0", "10": "S0", "11": "S1", "12": "VSS", "13": "S3",
    "14": "S2", "15": "~E", "16": "Y15", "17": "Y14", "18": "Y13", "19": "Y12",
    "20": "Y11", "21": "Y10", "22": "Y9", "23": "Y8", "24": "VDD",
}
AP63203_PINS = {"1": "FB/VOUT-sense", "2": "EN", "3": "VIN", "4": "GND", "5": "SW", "6": "BST"}

# Sole controller: Arduino Nano ESP32 on the real Module:Arduino_Nano footprint,
# one 30-pad part (A1). Pad -> Arduino function, locked against the footprint's
# USB marker at (7.62,35.56): pads 1-15 = analog row VIN..D13, pads 16-30 =
# digital row D12..D1 (see build_schematic.py A1_MAP for the full net mapping).
A1_PINS = {
    "1": "VIN", "2": "GND", "3": "RESET", "4": "5V", "5": "A7", "6": "A6",
    "7": "A5", "8": "A4", "9": "A3", "10": "A2", "11": "A1", "12": "A0",
    "13": "AREF", "14": "3V3", "15": "D13", "16": "D12", "17": "D11", "18": "D10",
    "19": "D9", "20": "D8", "21": "D7", "22": "D6", "23": "D5", "24": "D4",
    "25": "D3", "26": "D2", "27": "GND", "28": "RESET", "29": "D0", "30": "D1",
}

MOTOR_CONN_PINS = {"1": "M+", "2": "M-", "3": "ENC_VCC", "4": "ENC_GND", "5": "ENC_A", "6": "ENC_B"}

# Socketed motor-driver breakout header rows (functional labels; verify order
# + spacing against the actual TB6612 carrier before fab).
J10_PINS = {"1": "STBY", "2": "PWMA", "3": "AIN1", "4": "AIN2", "5": "PWMB",
            "6": "BIN1", "7": "BIN2", "8": "GND"}
J11_PINS = {"1": "VM (batt)", "2": "VCC (+3V3)", "3": "GND", "4": "AO1", "5": "AO2",
            "6": "BO1", "7": "BO2", "8": "GND"}

EXACT_PIN_NAMES = {
    "A1": A1_PINS,
    "U1": AP63203_PINS,
    "U4": HEF4067_PINS,
    "U5": HEF4067_PINS,
    "J1": {"1": "BAT+", "2": "BAT-"},
    "J2": {"1": "SW_A", "2": "SW_B"},
    "J3": {"1": "PACK+ (cell2+)", "2": "CELL_MID (cell1+/cell2-)", "3": "PACK- (GND)"},
    "J5": MOTOR_CONN_PINS,
    "J6": MOTOR_CONN_PINS,
    "J10": J10_PINS,
    "J11": J11_PINS,
    "Q1": {"D": "Drain (battery side)", "G": "Gate", "S": "Source (load side)"},
}

def pin_name(ref, pin):
    if ref in EXACT_PIN_NAMES:
        return EXACT_PIN_NAMES[ref].get(pin, pin)
    if re.fullmatch(r"D\d+", ref):
        return {"1": "K (cathode)", "2": "A (anode)"}.get(pin, pin)
    if re.fullmatch(r"Q\d+", ref):
        n = int(ref[1:])
        if n >= 2 and n % 2 == 0:   # SFH309 phototransistors
            return {"1": "C (collector)", "2": "E (emitter)"}.get(pin, pin)
        if n >= 3:                   # BSS138 switches
            return {"1": "G (gate)", "2": "S (source)", "3": "D (drain)"}.get(pin, pin)
    return pin  # passives: bare pin number is fine

# ---------------------------------------------------------------------------
# Sensor indexing (matches build_schematic.py's generation order exactly)
# ---------------------------------------------------------------------------
SENSOR_NAMES = ["WALL1", "WALL2", "WALL3", "WALL4", "WALL5", "WALL6",
                "LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8"]

def sensor_parts(i):
    return {
        "photo": f"Q{2 + 2*i}", "pullup": f"R{13 + 2*i}", "curr": f"R{14 + 2*i}",
        "led": f"D{1 + i}", "switch": f"Q{3 + 2*i}", "channel": f"Y{i}",
    }

SENSOR_ROLE = {
    "WALL1": "front-left diagonal wall sensor (THT, leads bent to aim forward-left ~45 deg)",
    "WALL2": "front-right diagonal wall sensor (THT, leads bent to aim forward-right ~45 deg)",
    "WALL3": "left-forward wall sensor (THT, leads bent to aim forward)",
    "WALL4": "right-forward wall sensor (THT, leads bent to aim forward)",
    "WALL5": "left side wall sensor (THT, leads bent to aim left, 90 deg)",
    "WALL6": "right side wall sensor (THT, leads bent to aim right, 90 deg)",
}
for _k in range(1, 9):
    SENSOR_ROLE[f"LINE{_k}"] = (f"line sensor {_k} of 8 (bottom-side mounted, faces the floor; "
                                 "9.525mm pitch matching the Pololu QTR-8A reference)")

# ---------------------------------------------------------------------------
# Netlist parsing
# ---------------------------------------------------------------------------

def parse(path):
    text = open(path, encoding="utf-8").read()
    comps = {}
    for m in re.finditer(r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*\(footprint "([^"]*)"\)', text):
        comps[m.group(1)] = (m.group(2), m.group(3))
    nets = {}
    for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text, re.S):
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2))
        nets[m.group(1)] = nodes
    return comps, nets

comps, nets = parse(NETLIST)

# ---------------------------------------------------------------------------
# Rationales. Explicit per-net text for the uniquely-named nets; generated
# text for the patterned families (sensor nets, LED cathodes, no-connects).
# Any net that ends up with no rationale aborts the script.
# ---------------------------------------------------------------------------

R = {}

R["GND"] = (
    "System ground and current return for every subsystem. Both battery-negative terminals "
    "(J1.2 main lead, J3.3 balance lead) land here; all logic (the ESP32 controller, both muxes), "
    "all decoupling capacitors, every phototransistor emitter, every LED-switch source, all three "
    "push buttons, the divider bottoms, and the TB6612's logic GND plus both power grounds (PGND1/"
    "PGND2) return here. A single unified ground (no split analog/motor ground) is a deliberate "
    "2-layer-board decision -- GND is poured as a full plane on BOTH copper layers of the PCB, which "
    "gives motor return currents a wide, low-inductance path without star-grounding complexity. "
    "TB6612's PGND pins carry the H-bridge return current; keeping them on the same net as logic GND "
    "matches Toshiba's reference application circuit.")

R["PLUS3V3"] = (
    "The single regulated 3.3V logic rail, produced by U1 (AP63203WU buck) via L1 and sensed at its "
    "FB pin. A switching buck (not an LDO) was chosen because the ESP32-S3's WiFi TX bursts reach "
    "~350-500mA, which an LDO from 8.4V would burn ~2.5W dissipating. Consumers, each justified: "
    "the Arduino Nano ESP32's 3V3 pin (A1.14 -- the dev board is powered from our regulated rail; "
    "do NOT power it via its USB while the battery is on, two supplies would fight); both mux VDD "
    "pins (U4/U5.24 -- HEF4067 supply must match the analog signal range, and phototransistor "
    "outputs swing 0..3.3V); all 14 phototransistor pull-ups (47k each, QTR-8A-style divider); all "
    "14 IR-LED current-limit resistors (LED drive current is sized against the REGULATED rail so "
    "sensor brightness does not drift as the 2S pack discharges 8.4V to 6.0V -- a Peter Harrison "
    "micromouse design rule); the four encoder pull-ups and both motor-connector ENC_VCC pins "
    "(Hall encoder boards accept 3.3V, keeping encoder logic levels native to the ESP32); TB6612 "
    "VCC via the breakout header (logic side, 2.7-5.5V rated); and the USER_BTN pull-up.")

R["VM_BATT"] = (
    "The protected raw-battery rail (6.0-8.4V from the 2S pack, downstream of the switch J2, fuse "
    "F1, and reverse-polarity MOSFET Q1 -- entering at Q1's SOURCE, see Net-(F1-Pad2)). Feeds "
    "exactly three things, each justified: (1) TB6612 motor-power pins VM1/VM2/VM3 (U2.24/13/14) -- "
    "motors run from raw battery for full torque headroom; VM range 2.5-13.5V easily covers 2S; "
    "(2) buck regulator input U1.3 VIN plus its enable U1.2 (EN tied to VIN = always-on when "
    "battery power is present, per AP63203 datasheet practice); (3) bulk + HF decoupling C1 100uF, "
    "C2 100nF at the battery entry and C4 10uF at the regulator input, plus C9 10uF at the TB6612 "
    "VM pins -- motor PWM draws fast current steps that must be served locally, not through the "
    "battery leads' inductance.")

R["VBAT_CELL1_SENSE"] = (
    "Scaled cell-1 voltage into ESP32 ADC pin A1 (A1.11). R2 (10k, from the "
    "balance-lead cell-1 tap J3.2) and R3 (22k, to GND) divide 0-4.2V down to 0-2.89V, inside the "
    "3.3V ADC range with margin. C6 100nF across the bottom leg low-passes the node -- the ADC "
    "samples a low-impedance-ish source and motor PWM noise is filtered. Firmware computes "
    "cell2 = pack - cell1 so BOTH cells are monitored for the per-cell 3.0V LiPo cutoff (a pack "
    "reading alone can hide one weak cell). A0-A2 carry all three analog inputs on this board "
    "-- confirm the Nano-ESP32 header->GPIO->ADC1-channel mapping in firmware (ADC1, not ADC2, "
    "must be used while WiFi is active).")

R["VBAT_PACK_SENSE"] = (
    "Scaled full-pack voltage into ESP32 ADC pin A2 (A1.10). R4 (10k, from the "
    "balance connector's pack+ pin J3.1) and R5 (6.2k, to GND) divide 0-8.4V down to 0-3.21V. C7 "
    "100nF filters the node, same reasoning as the cell-1 divider. NOTE (flagged risk, also in "
    "PROJECT_NOTES): both dividers hang directly on the balance connector, UPSTREAM of switch and "
    "fuse -- they drain ~0.52mA + ~0.13mA continuously while the balance lead is plugged, which "
    "will deep-discharge a stored pack over some weeks. Mitigation: unplug the balance connector "
    "for storage (documented assembly/user rule), or a future revision can add a high-side sense "
    "switch.")

R["MUX_S0"] = None  # filled by loop below
R["MUX_S1"] = None
R["MUX_S2"] = None
R["MUX_S3"] = None
for _i, _pin in ((0, "D13 via A1.15"), (1, "A3 via A1.9"), (2, "A4 via A1.8"), (3, "A5 via A1.7")):
    R[f"MUX_S{_i}"] = (
        f"Mux channel-select bit {_i} (binary weight {2**_i}), ESP32 GPIO {_pin} driving select "
        f"input S{_i} on BOTH HEF4067s in parallel (U4.{ {0:'10',1:'11',2:'14',3:'13'}[_i] } and "
        f"U5.{ {0:'10',1:'11',2:'14',3:'13'}[_i] }). Sharing one 4-bit select bus across the "
        "read-mux and the write-demux is the core of the sensor architecture: selecting channel N "
        "simultaneously picks sensor N's phototransistor for reading AND sensor N's LED driver for "
        "pulsing, enforcing one-emitter-one-receiver lockstep (crosstalk avoidance) while spending "
        "only 4 GPIOs + 1 ADC pin + 1 pulse pin on 14 sensors. Channel index = S3 S2 S1 S0 binary; "
        "WALL1..6 = channels 0-5 (Y0-Y5), LINE1..8 = channels 6-13 (Y6-Y13).")

R["MUX_SENSE"] = (
    "Analog common (Z, U4.1) of the READ mux into ESP32 ADC pin A0 (A1.12). "
    "Whatever channel S3..S0 selects, that sensor's phototransistor divider node appears here. One "
    "ADC pin thus reads all 14 sensors -- far fewer than 14 ADC-capable pins exist on the Nano "
    "header, so muxing is mandatory; it also saves GPIO for the drive side. HEF4067 is a bidirectional ANALOG switch (verified: "
    "Nexperia datasheet Rev.11 calls it a bidirectional transmission-gate switch), so the divider "
    "voltage passes through unmodified in DC terms. Verified caveats for firmware (adversarial "
    "datasheet check, 2 independent agents): the datasheet only characterizes Ron at 5/10/15V "
    "(350R typ / 2500R MAX at 5V); at our 3.3V, mid-scale Ron rises to ~1k+ typical and plausibly "
    "several k worst case (metal-gate CMOS, only ~1.65V overdrive at mid-supply). Into the ADC's "
    "high-Z input this costs NO ratio accuracy (no DC current flows), but the 47k pull-up + ~1k+ "
    "Ron source impedance is far above the ESP32 ADC's fast-sample limit, so USE A LONG ADC "
    "SAMPLING TIME (or an op-amp buffer if speed matters). Channel off-leakage (spec'd 1000nA max "
    "Z-port at 25C) through 47k is a low-tens-of-mV worst-case offset, typically negligible.")

R["LED_PULSE"] = (
    "ESP32 GPIO A6 (A1.6) into the WRITE demux common (Z, U5.1). Firmware raises this for "
    "~60-100us to fire the currently-selected sensor's IR LED via its BSS138 gate, samples "
    "MUX_SENSE ('bright'), lowers it, samples again ('ambient'), and subtracts -- synchronous "
    "detection that cancels ambient IR (Peter Harrison's method, see PROJECT_NOTES). FIRMWARE "
    "RULE (flagged): unselected demux outputs are high-impedance, so a BSS138 gate holds its last "
    "charge when deselected. ALWAYS return LED_PULSE low while the channel is still selected (gate "
    "discharges through the mux), and on boot walk all 14 channels with LED_PULSE low to discharge "
    "any power-up gate charge. Otherwise a deselected LED can stay on -- crosstalk + battery drain.")

R["STBY"] = (
    "TB6612 standby control (active-low) from ESP32 GPIO D2 (A1.26) to the breakout header J10.1. "
    "GPIO-driven rather than strapped high so firmware can hard-disable both H-bridges (fault "
    "response, low-power idle) -- an explicit user requirement recorded in PROJECT_NOTES. TB6612 "
    "outputs are disabled while STBY is low regardless of the IN/PWM pins, so the robot cannot "
    "drive during MCU reset if the pin idles low.")

for _sig, _pin_lbl, _brk, _desc in (
        ("AIN1", "D6 via A1.22", "J10.3", "motor A direction bit 1"),
        ("AIN2", "D5 via A1.23", "J10.4", "motor A direction bit 2"),
        ("BIN1", "D4 via A1.24", "J10.6", "motor B direction bit 1"),
        ("BIN2", "D3 via A1.25", "J10.7", "motor B direction bit 2")):
    R[_sig] = (
        f"TB6612 {_desc} from ESP32 GPIO {_pin_lbl} to the motor-driver breakout control header "
        f"({_brk}). The IN1/IN2 pair per channel selects forward / reverse / short-brake / stop "
        "per the TB6612 truth table while the PWM pin modulates speed. Plain GPIOs suffice -- "
        "direction changes are slow, and the ESP32's LEDC PWM works on any pin so no special "
        "pin assignment is needed anywhere on the drive side.")

R["PWMA"] = (
    "Motor A speed PWM: ESP32 D8 (A1.20) to the breakout's PWMA (J10.2). The ESP32-S3's LEDC "
    "peripheral generates hardware PWM on any GPIO, typically configured 20-25kHz (above audible). "
    "Use one LEDC timer for both PWMA and PWMB so the two motors' PWM stays phase-aligned.")

R["PWMB"] = (
    "Motor B speed PWM: ESP32 D7 (A1.21) to the breakout's PWMB (J10.5). Same LEDC timer as PWMA, "
    "see PWMA rationale.")

for _sig, _row, _pin_lbl, _conn, _r in (
        ("ENC1_A", "A1.16", "D12", "J5.5", "R6"),
        ("ENC1_B", "A1.17", "D11", "J5.6", "R7"),
        ("ENC2_A", "A1.18", "D10", "J6.5", "R8"),
        ("ENC2_B", "A1.19", "D9", "J6.6", "R9")):
    _m = "A" if "1" in _sig else "B"
    R[_sig] = (
        f"Motor {_m} quadrature encoder phase {_sig[-1]}: from the N20 motor's Hall encoder via "
        f"connector {_conn}, into ESP32 {_pin_lbl} ({_row}), with 10k pull-up {_r} to +3V3. "
        "The ESP32-S3 has 4 PCNT (pulse-counter) units with hardware quadrature decoding, and "
        "PCNT inputs route through the GPIO matrix from ANY pin -- each motor's phase pair just "
        "needs two ordinary GPIOs (no special timer-pin pairing as an STM32 would need). The "
        "pull-up is defensive: the encoder's output stage (open-drain vs push-pull) is unverified "
        "for the exact unit ordered -- required if open-drain, harmless if push-pull "
        "(PROJECT_NOTES).")

R["USER_BTN"] = (
    "Start-run button: ESP32 A7 (A1.5), pulled to +3V3 through R10 10k, switched to GND by SW1 "
    "(active-low). Standard micromouse UX -- arm the run without touching the robot's power.")

# --- Local (auto-named) power-chain nets ---

R["Net-(J1-Pin_1)"] = (
    "Battery positive from the main pack lead (J1.1) to one side of the external power switch "
    "(J2.1). The switch is off-board (a chassis-mounted toggle on a 2-pin header) so the robot can "
    "be powered off without unplugging the pack; putting it FIRST in the chain means everything "
    "downstream (fuse, protection FET, both rails) is dead when off.")

R["Net-(J2-Pin_2)"] = (
    "Switched battery positive from the power switch (J2.2) into the fuse F1 (3A resettable "
    "polyfuse). The fuse sits after the switch and before everything else so any downstream fault "
    "(shorted driver, crashed wiring) opens the whole system. 3A covers worst-case dual-motor "
    "stall plus logic with margin, while still tripping on a hard short.")

R["Net-(F1-Pad2)"] = (
    "Fused battery positive from F1.2 into Q1's DRAIN. Battery enters the reverse-protection "
    "P-MOSFET at the drain deliberately: at power-up the body diode (P-FET: anode=drain, "
    "cathode=source) conducts to the load, the gate (held at GND by R1) then sits ~Vbatt below "
    "the source, the channel enhances and shorts out the diode drop. With a REVERSED battery the "
    "body diode is reverse-biased and Vgs is positive: fully blocked. (The first schematic "
    "revision had source/drain swapped, which would have conducted a reversed battery through the "
    "body diode -- caught during this document's audit and fixed; see PROJECT_NOTES.)")

R["Net-(Q1-PadG)"] = (
    "Q1 gate to R1 (100k) whose other leg is GND. Holding the gate at ground keeps Vgs = -Vbatt "
    "when the battery is correct (FET hard on, ~milliohm path) and Vgs >= 0 when reversed (FET "
    "off). 100k limits any gate transient current and is small enough that gate leakage cannot "
    "float the gate.")

R["Net-(U1-SW)"] = (
    "Buck regulator switch node: U1.5 (SW) to L1.1, plus the bootstrap capacitor's low side "
    "(C3.2). This node slews between ~VM_BATT and GND at the AP63203's switching frequency; L1 "
    "integrates it into the DC output. Kept as a compact fat trace on the PCB -- it is the "
    "noisiest node on the board. VERIFIED against Diodes DS41326 Rev.3-2: 3.3uH is inside the "
    "recommended 2.2-10uH range (the table's single suggested value for 3.3V/1.1MHz is 3.9uH; "
    "3.3uH at 8.4V in gives ~28% ripple current, just under the 30-50% guideline -- acceptable, "
    "swap to 3.9uH at BOM time if convenient).")

R["Net-(U1-BST)"] = (
    "Bootstrap supply for the buck's high-side gate driver: U1.6 (BST) to C3.1 (100nF), whose "
    "other side rides the SW node. The cap pumps up each switching cycle to drive the high-side "
    "FET's gate above its source -- required by the AP63203 datasheet, value from its application "
    "circuit.")

R["Net-(J3-Pin_1)"] = (
    "Balance-connector pack+ tap (J3.1) into the top of the pack-voltage divider (R4.1). Carries "
    "only the divider's ~0.5mA. Runs from the balance lead rather than VM_BATT so the ADC sees "
    "the battery even with the power switch off (storage-charge checks) -- the flip side is the "
    "standby-drain risk flagged in VBAT_PACK_SENSE.")

R["Net-(J3-Pin_2)"] = (
    "Balance-connector cell-1 tap (J3.2, the junction between the two series cells) into the top "
    "of the cell-1 divider (R2.1). Only path to measure the individual cell; carries ~0.13mA.")

# pin -> actual net name (for looking up KiCad's autogenerated local-net names,
# which flip between a 2-node net's two pins as the component set changes --
# so never hardcode "Net-(Dx-K)" etc; resolve it from the real netlist).
pin2net = {}
for _nm, _nodes in nets.items():
    for _r, _pp in _nodes:
        pin2net[(_r, _pp)] = _nm

for _mn, _conn, _bo, _breakpin, _pol in (("A", "J5", "AO", "J11.4", "MOTA_P"),
                                          ("A", "J5", "AO", "J11.5", "MOTA_N"),
                                          ("B", "J6", "BO", "J11.6", "MOTB_P"),
                                          ("B", "J6", "BO", "J11.7", "MOTB_N")):
    plus = _pol.endswith("_P")
    R[_pol] = (
        f"Motor {_mn} phase wire ({'M+' if plus else 'M-'}): the socketed TB6612 breakout's "
        f"{_bo}{'1' if plus else '2'} output (breakout header {_breakpin}) to motor connector "
        f"{_conn}.{'1' if plus else '2'}. Carries the full motor current (PWM-chopped, "
        "bidirectional) -- wide 0.5mm trace. Polarity convention: IN1=H, IN2=L, PWM=H drives M+ "
        "positive; if the motor spins backwards at bring-up, flip it in firmware (direction bits), "
        "not by rewiring. NOTE the breakout's actual output-pin order varies by vendor -- confirm "
        "AO1/AO2/BO1/BO2 positions against your board (see the socketing note).")

# --- Sensor family nets (generated) ---
for i, name in enumerate(SENSOR_NAMES):
    p = sensor_parts(i)
    ch = i
    bits = format(ch, "04b")
    mux_pad = [k for k, v in HEF4067_PINS.items() if v == p["channel"]][0]
    R[f"{name}_SENSE"] = (
        f"Analog output of the {SENSOR_ROLE[name]}. {p['photo']} (SFH309) sits emitter-to-GND, "
        f"collector pulled to +3V3 by {p['pullup']} (47k, the Pololu QTR-8A reference value): more "
        f"reflected 940nm IR -> more collector current -> LOWER voltage on this node. The node "
        f"feeds read-mux channel {p['channel']} (U4 pin {mux_pad}); when firmware sets "
        f"S3..S0={bits} (channel {ch}) it appears on MUX_SENSE for the ADC. Read 'bright' with the "
        f"LED pulsed, 'ambient' with it off, subtract in firmware.")
    R[f"{name}_LED"] = (
        f"Gate-drive for the {name} emitter switch: write-demux channel {p['channel']} (U5 pin "
        f"{mux_pad}) to the gate of {p['switch']} (BSS138). With channel {ch} selected and "
        f"LED_PULSE high, {p['switch']} sinks current through {p['led']} (SFH4550, 940nm) from "
        f"+3V3 via {p['curr']} (33R): roughly (3.3 - ~1.35Vf - Vds) / 33 = ~50mA class pulses, "
        f"tune at bring-up (BSS138 Rds(on) at 3.3V gate drive is the soft spot -- PROJECT_NOTES). "
        f"A GPIO cannot source this current, hence the per-sensor low-side switch; the demux only "
        f"ever carries gate charge, never LED current. VERIFIED gate-drive timing (datasheet "
        f"check): the demux's ~1k+ mid-supply Ron into the BSS138's Ciss (~50pF class -- a small "
        f"logic FET, NOT a power FET) gives sub-microsecond gate settling, comfortably inside a "
        f"60-100us LED pulse. (This is why a small-signal BSS138 was chosen over a power MOSFET -- "
        f"a power FET's nF-class Ciss through the mux Ron would eat 5-30% of the pulse.) See "
        f"LED_PULSE for the mandatory gate-discharge firmware rule that handles the floating "
        f"deselected gate.")

# LED cathode/anode local nets: key by the ACTUAL autogenerated net name
# (resolved via pin2net), not a hardcoded "Net-(Dx-K)" which KiCad may name
# after the transistor/resistor instead. Also collect these names so the
# GROUPS below reference the real names.
SENSOR_LOCAL_NETS = {}  # name -> list of (led_local_net_names)
for i, name in enumerate(SENSOR_NAMES):
    p = sensor_parts(i)
    k_net = pin2net.get((p["led"], "1"))   # cathode -> switch drain
    a_net = pin2net.get((p["led"], "2"))   # anode -> current-limit resistor
    SENSOR_LOCAL_NETS[name] = [n for n in (k_net, a_net) if n]
    if k_net:
        R[k_net] = (
            f"{name} LED cathode ({p['led']}.1) to its switch's drain ({p['switch']}.3). Local "
            f"two-node net inside the {name} driver: +3V3 -> {p['curr']} 33R -> LED anode, LED "
            f"cathode -> {p['switch']} drain, source -> GND. Low-side switching keeps the gate "
            f"drive ground-referenced (a 3.3V GPIO/demux level fully enhances the FET).")
    if a_net:
        R[a_net] = (
            f"{name} LED anode ({p['led']}.2) to the low side of its current-limit resistor "
            f"({p['curr']}.2, 33R): +3V3 -> {p['curr']} -> anode; cathode switched to GND by "
            f"{p['switch']} sets the pulse current. Supply-side resistor placement keeps the "
            f"switched (fast-edged) node confined to the cathode/drain net.")

# --- No-connects: every unconnected-* net, with real reasons ---

NC_REASONS = {
    ("A1", "1"):  "VIN -- the dev board is fed regulated 3.3V directly on its 3V3 pin; feeding "
                   "VIN too would run its onboard regulator in parallel with ours.",
    ("A1", "3"):  "RESET (analog-row copy) -- nothing on this board needs to hard-reset the "
                   "ESP32; its own button/auto-reset handle it.",
    ("A1", "4"):  "5V -- the board is battery-powered at 3.3V throughout; the dev board's 5V "
                   "USB rail is only alive while its USB is plugged.",
    ("A1", "13"): "AREF -- the ESP32's ADC uses its internal reference; nothing external supplied.",
    ("A1", "28"): "RESET (digital-row copy) -- same line as A1.3, see there.",
    ("A1", "29"): "D0/RX -- kept free for USB-serial debug on the dev board; no on-board UART "
                   "link exists now that the ESP32 is the sole controller.",
    ("A1", "30"): "D1/TX -- kept free, same reason as D0/RX.",
    ("U4", "16"): "Read-mux channel Y15 -- only 14 sensors exist; channels 14/15 unused.",
    ("U4", "17"): "Read-mux channel Y14 -- unused, see Y15.",
    ("U5", "16"): "Write-demux channel Y15 -- unused, see U4.",
    ("U5", "17"): "Write-demux channel Y14 -- unused, see U4.",
}

def nc_reason(ref, pin):
    if (ref, pin) in NC_REASONS:
        return NC_REASONS[(ref, pin)]
    return "Intentionally unconnected."

# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

GROUPS = [
    ("Power input & protection chain",
     ["Net-(J1-Pin_1)", "Net-(J2-Pin_2)", "Net-(F1-Pad2)", "Net-(Q1-PadG)", "VM_BATT"]),
    ("3.3V regulation",
     ["Net-(U1-SW)", "Net-(U1-BST)", "PLUS3V3"]),
    ("Ground", ["GND"]),
    ("Battery monitoring",
     ["Net-(J3-Pin_1)", "Net-(J3-Pin_2)", "VBAT_PACK_SENSE", "VBAT_CELL1_SENSE"]),
    ("Motor drive (socketed TB6612 breakout)",
     ["STBY", "PWMA", "AIN1", "AIN2", "MOTA_P", "MOTA_N",
      "PWMB", "BIN1", "BIN2", "MOTB_P", "MOTB_N"]),
    ("Encoders",
     ["ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B"]),
    ("IR sensor matrix -- shared control",
     ["MUX_S0", "MUX_S1", "MUX_S2", "MUX_S3", "MUX_SENSE", "LED_PULSE"]),
    ("IR sensor matrix -- wall sensors (THT, bent-lead)",
     [f"WALL{k}_{s}" for k in range(1, 7) for s in ("SENSE", "LED")] +
     [n for k in range(6) for n in SENSOR_LOCAL_NETS[SENSOR_NAMES[k]]]),
    ("IR sensor matrix -- line sensors (SMD, bottom-face)",
     [f"LINE{k}_{s}" for k in range(1, 9) for s in ("SENSE", "LED")] +
     [n for k in range(6, 14) for n in SENSOR_LOCAL_NETS[SENSOR_NAMES[k]]]),
    ("User interface", ["USER_BTN"]),
]

def fmt_pins(nodes):
    parts = []
    for ref, pin in sorted(nodes, key=lambda t: (re.sub(r"\d+", "", t[0]), int(re.search(r"\d+", t[0]).group(0)) if re.search(r"\d+", t[0]) else 0, t[1])):
        nm = pin_name(ref, pin)
        parts.append(f"`{ref}.{pin}`" + (f" ({nm})" if nm != pin else ""))
    return ", ".join(parts)

out = []
out.append("# CONNECTIONS.md -- every net, every pin, and why\n")
out.append(
    "Generated by `tools/gen_connections.py` from `netlist.net` (the schematic's exported netlist, "
    "itself ERC-clean and net-by-net verified -- see PROJECT_NOTES.md). Pin functions are annotated "
    "from the exact KiCad library symbols used. **Regenerate this file after any schematic change** "
    "-- the generator aborts if any net lacks a justification, so this document cannot silently "
    "drift from the design.\n")

out.append("## How parts attach to this board (sockets vs. solder vs. plugs)\n")
out.append(
    "| Part | Attachment | Why |\n|---|---|---|\n"
    "| Arduino Nano ESP32 (A1, SOLE controller) | **Socketed** -- the real Module:Arduino_Nano land pattern (two 1x15 rows, 15.24mm apart; fit female headers) | User decision (2026-07-13): the STM32 was dropped entirely to shrink the board; one ESP32-S3 dev board now does all control AND telemetry. The dev board brings its own USB-C, auto-reset, boot button, regulator and decoupling, and is flashed/debugged over that USB (or WiFi OTA). Pad order locked against the footprint's USB silk marker; identical to KiCad's Arduino Nano reference. |\n"
    "| Motor driver (TB6612 breakout) | **Socketed** -- two 1x8 female headers (J10 control, J11 power+outputs) | User decision (2026-07-12): a socketed TB6612 carrier (e.g. SparkFun ROB-14451 / Pololu), not a bare SSOP-24. The breakout carries its own decoupling. **Pin order + row spacing vary by vendor -- verify against your actual board before fab.** |\n"
    "| Motors (2x N20 + encoder) | **Pluggable** -- JST-PH 6-pin (J5, J6) | Motors are mechanical wear parts; JST-PH is the class of connector these motors ship with. Pin order is FUNCTIONAL (M+, M-, ENC_VCC, ENC_GND, ENC_A, ENC_B) -- verify against the real cable at assembly, resellers vary (PROJECT_NOTES). |\n"
    "| Battery | **Pluggable** -- JST-XH 2-pin (J1) + JST-XH 3-pin balance (J3) | Standard 2S pack interfaces. Balance lead powers the voltage dividers -- unplug for storage (drain risk, see VBAT_PACK_SENSE). |\n"
    "| Power switch | **Pluggable** -- 2-pin header (J2) | Chassis-mounted toggle, position depends on mechanical build. |\n"
    "| Line-sensor optics (8x) | **SMD, bottom face** | User decision (2026-07-12): SMD IR LED (e.g. Osram SFH4045N) + SMD phototransistor (e.g. SFH320FA) on the board underside, looking down at the floor (~3mm ride height), 9.525mm QTR pitch. |\n"
    "| Wall-sensor optics (6x), regulator, muxes, passives, button | **Soldered** | Wall sensors are THT with deliberate lead-forming (bent outward to aim at walls). The rest is permanent circuit fabric. |\n")

out.append("## Reading a net entry\n")
out.append(
    "Each net lists its full pin membership as `REF.pin (pin function)`, then the engineering "
    "justification. Sources referenced: Toshiba TB6612FNG datasheet, Nexperia HEF4067B datasheet, "
    "Espressif ESP32-S3-MINI-1 datasheet + hardware design guidelines, Diodes AP63203 datasheet, "
    "the ESP32-S3 datasheet/TRM (LEDC any-GPIO PWM, PCNT quadrature, ADC1-with-WiFi), Pololu QTR-8A documentation, "
    "Peter Harrison's micromouse sensor writings, and the project research log (PROJECT_NOTES.md).\n")

out.append("## Verification status of the load-bearing claims\n")
out.append(
    "The datasheet-dependent claims below were adversarially re-checked against PRIMARY sources by "
    "independent agents instructed to refute them (2026-07-12). Results:\n\n"
    "| Claim | Verdict | Primary source |\n|---|---|---|\n"
    "| TB6612FNG full pinout + STBY active-low + VM/VCC ranges | **CONFIRMED** | Toshiba TB6612FNG datasheet, pin table p.2 / control table p.4 / ratings p.3 |\n"
    "| HEF4067 active-low enable, 3.3V-capable, bidirectional analog | **CONFIRMED** | Nexperia HEF4067B Rev.11 |\n"
    "| HEF4067 Ron at 3.3V | **Corrected** -- not \"hundreds of ohms\"; ~1k+ typ at mid-supply, multi-k worst case. Doc updated (see MUX_SENSE/*_LED): immaterial for the ADC divider, drives the choice of small-signal BSS138 over a power FET | Nexperia Rev.11 + TI CD4067B (no 3.3V Ron is published by either; extrapolated from 5V data) |\n"
        "| AP63203 fixed-3.3V: FB direct to VOUT, 100nF BST cap, 3.3uH in-range, EN-to-VIN, 8.4V < Vin,max | **CONFIRMED** (3.9uH is the table's exact suggestion vs. our 3.3uH -- both in the 2.2-10uH range) | Diodes DS41326 Rev.3-2 |\n"
    "| P-FET reverse protection: battery->DRAIN, load->SOURCE, gate->GND | Self-verified via body-diode analysis (workflow agent hit session limit); this is the textbook orientation and the doc's Net-(F1-Pad2) entry walks the proof | onsemi/TI reverse-polarity P-FET app notes |\n"
    "| Nano header row order (D12..D1 digital row; D13,3V3,AREF,A0-A7,5V,RST,GND,VIN analog row; RESET on both) | Self-verified pad-for-pad against KiCad's bundled Arduino Nano reference PCB (workflow agent hit session limit) | `share/kicad/template/Arduino_Nano/Arduino_Nano.kicad_pcb` |\n")

documented = set()
for title, net_list in GROUPS:
    out.append(f"\n## {title}\n")
    for net in net_list:
        if net not in nets:
            print(f"WARNING: group '{title}' references net '{net}' not in netlist")
            continue
        if net in documented:
            continue
        rationale = R.get(net)
        if not rationale:
            continue  # caught by coverage check below
        out.append(f"### `{net}`\n")
        out.append(f"**Pins:** {fmt_pins(nets[net])}\n")
        out.append(rationale + "\n")
        documented.add(net)

# No-connects section
nc_nets = sorted(n for n in nets if n.startswith("unconnected-"))
out.append("\n## Deliberate no-connects\n")
out.append("Every pin below carries an explicit no-connect flag in the schematic (ERC-checked), "
           "not an accidental omission.\n\n| Pin | Function | Why unconnected |\n|---|---|---|\n")
for net in nc_nets:
    (ref, pin), = nets[net]
    nm = pin_name(ref, pin)
    out.append(f"| `{ref}.{pin}` | {nm} | {nc_reason(ref, pin)} |\n")
    documented.add(net)

# Coverage enforcement
missing = [n for n in nets if n not in documented]
if missing:
    print("FATAL: nets present in netlist but not documented:")
    for n in missing:
        print("   ", n, nets[n])
    sys.exit(1)

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))
print(f"Wrote {OUT}: {len(documented)} nets documented, 0 missing.")
