"""Generates CONNECTIONS.md -- the per-net, per-pin justification document.

Every net in netlist.net gets an entry: which pins belong to it (annotated
with the pin's FUNCTION name) and WHY that connection exists. Coverage is
enforced by construction: any net without a rationale aborts the build.
Regenerate after any schematic change:

    "C:\\msys64\\ucrt64\\bin\\python3.exe" gen_connections.py
"""
import re
import sys
import os

NETLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "netlist.net")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "CONNECTIONS.md")

# ---------------------------------------------------------------------------
# Pin-number -> function-name tables (from the exact KiCad symbols used,
# cross-checked against manufacturer datasheets; see PROJECT_NOTES.md).
# ---------------------------------------------------------------------------

# ESP32-S3-WROOM-1 module (U3): pad -> module pin name. Pads 1/40/41 = GND.
U3_PINS = {
    "1": "GND", "2": "3V3", "3": "EN", "4": "IO4", "5": "IO5", "6": "IO6",
    "7": "IO7", "8": "IO15", "9": "IO16", "10": "IO17", "11": "IO18",
    "12": "IO8", "13": "USB_D-(IO19)", "14": "USB_D+(IO20)", "15": "IO3",
    "16": "IO46", "17": "IO9", "18": "IO10", "19": "IO11", "20": "IO12",
    "21": "IO13", "22": "IO14", "23": "IO21", "24": "IO47", "25": "IO48",
    "26": "IO45", "27": "IO0", "28": "IO35", "29": "IO36", "30": "IO37",
    "31": "IO38", "32": "IO39/MTCK", "33": "IO40/MTDO", "34": "IO41/MTDI",
    "35": "IO42/MTMS", "36": "RXD0(IO44)", "37": "TXD0(IO43)", "38": "IO2",
    "39": "IO1", "40": "GND", "41": "GND",
}
# CD74HC4067M (U4): same package/pin order as the old HEF4067BT.
U4_PINS = {
    "1": "COM/Z", "2": "I7", "3": "I6", "4": "I5", "5": "I4", "6": "I3",
    "7": "I2", "8": "I1", "9": "I0", "10": "S0", "11": "S1", "12": "GND",
    "13": "S3", "14": "S2", "15": "~E", "16": "I15", "17": "I14", "18": "I13",
    "19": "I12", "20": "I11", "21": "I10", "22": "I9", "23": "I8", "24": "VCC",
}
TPS63000_PINS = {"1": "VOUT", "2": "L2", "3": "PGND", "4": "L1", "5": "VIN",
                 "6": "EN", "7": "PS/SYNC", "8": "VINA", "9": "GND", "10": "FB",
                 "11": "PGND"}
USBLC6_PINS = {"1": "I/O1", "2": "GND", "3": "I/O2", "4": "I/O2'", "5": "VBUS", "6": "I/O1'"}
MOTOR_CONN_PINS = {"1": "M+", "2": "M-", "3": "ENC_VCC", "4": "ENC_GND", "5": "ENC_A", "6": "ENC_B"}
TB6612_PINS = {
    "1": "AO1", "2": "AO1", "3": "PGND1", "4": "PGND1", "5": "AO2", "6": "AO2",
    "7": "BO2", "8": "BO2", "9": "PGND2", "10": "PGND2", "11": "BO1", "12": "BO1",
    "13": "VM2", "14": "VM3", "15": "PWMB", "16": "BIN2", "17": "BIN1", "18": "GND",
    "19": "STBY", "20": "VCC", "21": "AIN1", "22": "AIN2", "23": "PWMA", "24": "VM1",
}
J8_PINS = {"1": "VDD33", "2": "TMS", "3": "TCK", "4": "TDO", "5": "TDI", "6": "GND"}

EXACT_PIN_NAMES = {
    "U1": TPS63000_PINS,
    "U3": U3_PINS,
    "U4": U4_PINS,
    "U6": USBLC6_PINS,
    "J1": {"1": "BAT+", "2": "BAT-"},
    "J2": {"1": "SW_A", "2": "SW_B"},
    "J5": MOTOR_CONN_PINS,
    "J6": MOTOR_CONN_PINS,
    "J8": J8_PINS,
    "U2": TB6612_PINS,
    "Q1": {"D": "Drain (battery side)", "G": "Gate", "S": "Source (load side)"},
}

def pin_name(ref, pin):
    if ref in EXACT_PIN_NAMES:
        return EXACT_PIN_NAMES[ref].get(pin, pin)
    if ref == "J7":
        return {"A5": "CC1", "B5": "CC2", "A6": "D+", "B6": "D+", "A7": "D-",
                "B7": "D-", "SH": "SHIELD"}.get(pin, pin)
    if re.fullmatch(r"D\d+", ref):
        return {"1": "K (cathode)", "2": "A (anode)"}.get(pin, pin)
    if re.fullmatch(r"Q\d+", ref):
        n = int(ref[1:])
        if 2 <= n <= 15:                 # phototransistors
            return {"1": "C (collector)", "2": "E (emitter)"}.get(pin, pin)
        if 16 <= n <= 27:                # BSS138 NMOS (groups + line indicators)
            return {"1": "G (gate)", "2": "S (source)", "3": "D (drain)"}.get(pin, pin)
        if 28 <= n <= 33:                # BSS84 PMOS (wall indicators)
            return {"D": "D (drain)", "G": "G (gate)", "S": "S (source)"}.get(pin, pin)
    return pin

# ---------------------------------------------------------------------------
# Sensor indexing (matches build_schematic.py rev 4 exactly)
# ---------------------------------------------------------------------------
SENSOR_NAMES = ["WALL1", "WALL2", "WALL3", "WALL4", "WALL5", "WALL6",
                "LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8"]

def sensor_parts(i):
    grp = ("FRONT" if i < 2 else "DIAG" if i < 4 else "SIDE" if i < 6 else "LINE")
    return {
        "photo": f"Q{2 + i}", "pullup": f"R{13 + 2*i}", "curr": f"R{14 + 2*i}",
        "led": f"D{1 + i}", "group": grp,
    }

SENSOR_ROLE = {
    "WALL1": "front-left wall sensor (THT, aimed nearly forward, toed slightly outward)",
    "WALL2": "front-right wall sensor (THT, aimed nearly forward, toed slightly outward)",
    "WALL3": "left 45-degree diagonal wall sensor (THT, on the chamfered corner)",
    "WALL4": "right 45-degree diagonal wall sensor (THT, on the chamfered corner)",
    "WALL5": "left side wall sensor (THT, ~90 degrees, toed slightly forward)",
    "WALL6": "right side wall sensor (THT, ~90 degrees, toed slightly forward)",
}
for _k in range(1, 9):
    SENSOR_ROLE[f"LINE{_k}"] = (f"line sensor {_k} of 8 (bottom-face SMD, faces the floor; "
                                 "9.525mm QTR pitch)")

# ESP32 pin for each wall sensor (ADC1 channel = GPIO number)
WALL_ADC = {1: "IO1", 2: "IO2", 3: "IO3", 4: "IO4", 5: "IO5", 6: "IO6"}

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
pin2net = {}
for _nm, _nodes in nets.items():
    for _r, _pp in _nodes:
        pin2net[(_r, _pp)] = _nm

# ---------------------------------------------------------------------------
# Rationales
# ---------------------------------------------------------------------------
R = {}

R["GND"] = (
    "System ground and current return for every subsystem: battery negative (J1.2), all "
    "decoupling, every phototransistor emitter, all group-switch sources, the indicator LED "
    "cathodes (wall side) and driver sources (line side), button lows, JTAG grounds, USB "
    "shield/ground, and the TB6612's logic + power grounds. Single unified ground poured on both outer "
    "copper faces (convert In1 to a plane in the GUI if desired).")

R["PLUS3V3"] = (
    "The single regulated 3.3V rail from U1 (TPS63001 buck-boost -- a 1S cell sags below a "
    "buck's dropout, hence buck-boost; 1.2A covers ESP32-S3 WiFi bursts). Consumers: the "
    "ESP32-S3-WROOM-1 (U3.2), mux VCC (U4.24), all 14 phototransistor pull-ups, all 14 IR-LED "
    "current limiters (regulated rail = constant sensor brightness across discharge -- Harrison "
    "rule), wall-indicator PMOS sources (Q28-33), line/wall indicator limiters, encoder supplies "
    "on both motor connectors, TB6612 VCC (U2.20), the USER_BTN and ESP_EN pull-ups, the JTAG "
    "header's VDD pin (J8.1) and the USB ESD array's clamp rail (U6.5).")

R["VM_BATT"] = (
    "Protected raw 1S cell rail (3.0-4.2V), downstream of switch J2, fuse F1, and reverse-"
    "polarity P-FET Q1 (battery enters at the DRAIN -- body-diode analysis in PROJECT_NOTES). "
    "Feeds: TB6612 motor power (U2 VM1/2/3, min 2.5V; C11 10uF + C12 100nF at the chip -- 3V-wound N20s, 6V wind "
    "runs ~60%), the TPS63001 input pins (VIN + EN tied high + VINA), input caps C1/C2/C4, and "
    "the battery divider R2 (tapped HERE, downstream of the switch, so a stored pack sees no "
    "divider drain -- fixes the rev<=3 balance-lead drain risk).")

R["VBAT_SENSE"] = (
    "Cell voltage divided 22k/33k (4.2V -> 2.52V) into ESP32 ADC1 (IO8, U3.12), C6 filtering "
    "PWM noise. Rescaled by the adversarial review: the S3's calibrated ADC range tops at "
    "~2.9V with worst error near the top, so full charge lands at 2.52V with headroom. "
    "Firmware low-battery cutoff at 3.0V.")

R["Net-(J1-Pin_1)"] = (
    "Battery positive from the 1S pack (J1.1, JST-PH) to the external power switch (J2.1). "
    "Switch first in the chain so everything downstream is dead when off.")
R["Net-(J2-Pin_2)"] = (
    "Switched battery positive from J2.2 into fuse F1 (2A resettable -- 1S currents; motors + "
    "logic worst case with margin, trips on a hard short).")
R["Net-(F1-Pad2)"] = (
    "Fused battery positive into Q1's DRAIN (reverse-polarity P-FET: at power-up the body "
    "diode conducts, the channel then enhances; reversed battery blocks both paths. Low-Vth "
    "part required at 1S -- DMP2035U class, fully enhanced by -2.5V).")
R["Net-(Q1-PadG)"] = (
    "Q1 gate to R1 100k to GND: Vgs = -Vbatt when correct (hard on), >= 0 when reversed (off).")
R["Net-(U1-L1)"] = (
    "Buck-boost switch node A: TPS63001 L1 pin to the 1.5uH inductor (datasheet value). Fast "
    "square edges -- keep the loop tight (L1 sits beside U1 on the board).")
R["Net-(U1-L2)"] = (
    "Buck-boost switch node B: the inductor's other end into the TPS63001 L2 pin. Same "
    "fast-edge caveat as L1.")

R["ESP_EN"] = (
    "ESP32 enable/reset: R11 10k pull-up + C9 1uF RC delay per Espressif hardware design "
    "guidelines, SW2 pulls it low for manual reset. Hold SW1 (IO0) while tapping SW2 = ROM "
    "download mode over the rear USB-C.")

R["USER_BTN"] = (
    "Start-run button SW1 on IO0 (U3.27) with R10 10k pull-up. IO0 is the BOOT strap -- the "
    "solid external pull-up keeps normal boot default, and holding SW1 through a reset enters "
    "download mode (deliberate dual use). Note: holding it during any watchdog/brownout reset "
    "also enters download mode until the next clean reset.")
R["USER_BTN2"] = (
    "Menu/select button SW3 on IO35 (U3.28), active-low, firmware enables the internal "
    "pull-up (no external resistor). On octal-PSRAM (-R8) modules IO35 does not exist -- "
    "buttons 2/3 are the sacrificial feature; use non-R8 (e.g. N16) modules.")
R["USER_BTN3"] = (
    "Third button SW4 on IO36 (U3.29) -- same arrangement and -R8 caveat as USER_BTN2.")

R["USB_DM_C"] = (
    "USB D- connector side: both B-row and A-row D- pads of the rear USB-C (J7) into the "
    "USBLC6 ESD array (U6 I/O1). The ESD array sits between the user-handled connector and "
    "the chip per the review (exposed connector on a robot).")
R["USB_DP_C"] = (
    "USB D+ connector side: J7's D+ pad pair into U6 I/O2. See USB_DM_C.")
R["USB_DM"] = (
    "USB D- module side: from the ESD array through R59 22R series (Espressif schematic "
    "checklist) into the module's dedicated USB_D- pad (IO19). Native USB-Serial/JTAG: "
    "flashing (even from blank flash, via IO0+EN buttons) and the CDC console -- UART0's "
    "pins were repurposed as encoder inputs.")
R["USB_DP"] = (
    "USB D+ module side: ESD array -> R60 22R -> module USB_D+ pad (IO20). See USB_DM.")
R["Net-(R59-Pad1)"] = (
    "Intermediate node between the ESD array's I/O1 output and R59's series resistance "
    "(the D- path's chip-side guard).")
R["Net-(R60-Pad1)"] = (
    "Intermediate node between the ESD array's I/O2 output and R60 (D+ path).")
R["USB_VBUS"] = (
    "The USB-C VBUS pads (all four, bridged) into the R67/R68 sense divider. VBUS does NOT "
    "power the board (battery does; a 5V feed would need a regulator + power mux) -- it is "
    "used purely as cable-presence detection.")
R["VBUS_SENSE"] = (
    "VBUS divided 10k/15k (5V -> 3.0V, a solid digital high) into IO37 (U3.30) -- firmware "
    "detects a plugged USB cable (e.g. auto-enable CDC logging). On -R8 modules IO37 does "
    "not exist; cable detect is the sacrificial feature there, same policy as buttons B/C.")
R["Net-(J7-CC1)"] = (
    "USB-C CC1 with R12 5.1k pull-down: advertises UFP (device) role so a host supplies "
    "VBUS/enumeration. VBUS itself is unconnected -- the board is battery-powered; flash "
    "with the battery on (documented).")
R["Net-(J7-CC2)"] = (
    "USB-C CC2 with R56 5.1k pull-down -- required on both CC pins so either cable "
    "orientation works.")

for _sig, _pin, _pad in (("JTAG_TCK", "IO39/MTCK", "U3.32"), ("JTAG_TDO", "IO40/MTDO", "U3.33"),
                          ("JTAG_TDI", "IO41/MTDI", "U3.34"), ("JTAG_TMS", "IO42/MTMS", "U3.35")):
    R[_sig] = (
        f"JTAG {_sig[-3:]}: {_pin} ({_pad}) to the debug header J8 (2.54mm 1x6: 3V3,TMS,TCK,"
        "TDO,TDI,GND -- a 1.27mm 2x5 was unroutable at the 0.3mm no-inter-pin clearance). "
        "IO39-42 are the S3's dedicated JTAG quad, kept exclusively for debugging.")

R["MUX_SENSE"] = (
    "Line-mux analog common (U4.1 COM) into ESP32 ADC1 IO7 (U3.7). One ADC pin reads all 8 "
    "line sensors. U4 is a CD74HC4067M -- the HC family is ~70R Ron and fast at 3.3V (the "
    "CD4000-family HEF4067 is only spec'd from 3V with kR-class Ron; swapped after the "
    "datasheet review). Budget ADC sampling time for the mux source impedance.")
for _i in range(3):
    R[f"MUX_S{_i}"] = (
        f"Line-mux select bit {_i}: IO1{1+_i} (U3.{19+_i}) to U4 S{_i}. Only 3 select bits: "
        "the line array uses channels I0-I7 and S3 is tied to GND. Walls no longer mux -- "
        "they read directly on ADC1 (user decision 2026-07-15).")

R["LINE_EMIT"] = (
    "Line emitter BANK gate: IO14 (U3.22) drives Q19 (BSS138) which sinks ALL 8 line LEDs "
    "(each with its own 120R from +3V3, ~15mA). One GPIO replaces the old write-demux. "
    "R61 100k holds the gate low through boot (IO14 floats until app init -- review fix). "
    "Line-follow mode latches this ON continuously (~120mA total), which is also what makes "
    "the top-side indicators live.")
for _sig, _grp, _pads in (("WALL_EMIT_FRONT", "front pair (WALL1+2)", "IO15/U3.8"),
                            ("WALL_EMIT_DIAG", "diagonal pair (WALL3+4)", "IO16/U3.9"),
                            ("WALL_EMIT_SIDE", "side pair (WALL5+6)", "IO17/U3.10")):
    _q = {"WALL_EMIT_FRONT": "Q16", "WALL_EMIT_DIAG": "Q17", "WALL_EMIT_SIDE": "Q18"}[_sig]
    _r = {"WALL_EMIT_FRONT": "R62", "WALL_EMIT_DIAG": "R63", "WALL_EMIT_SIDE": "R64"}[_sig]
    R[_sig] = (
        f"Wall emitter group gate for the {_grp}: {_pads} drives {_q} (BSS138) sinking both "
        f"LEDs of the pair (33R each, ~50mA pulses). UKMARS-practice grouping: mutually-"
        f"staring sensors are on different groups, and firing a pair while reading BOTH its "
        f"receivers in parallel on ADC1 halves scan time vs the old serial mux walk. "
        f"{_r} 100k holds the gate low through boot.")

for _k, _knet, _members in ((1, "EMIT_FRONT_K", "D1+D2"), (2, "EMIT_DIAG_K", "D3+D4"),
                              (3, "EMIT_SIDE_K", "D5+D6"), (4, "EMIT_LINE_K", "D7-D14")):
    _q = f"Q{15+_k}"
    R[_knet] = (
        f"Common cathode net of the {_knet[5:-2]} emitter group ({_members}) into {_q}'s "
        f"drain. Each LED keeps its own series resistor on the ANODE side, so this switched "
        f"node carries only the group's summed current and the per-LED currents stay "
        f"resistor-defined.")

R["PWMA"] = ("Motor A PWM: IO18 (U3.11) to U2.23. LEDC hardware PWM "
              "(any-GPIO via the matrix), 20-25kHz; share one LEDC timer with PWMB for "
              "phase-aligned motors.")
R["PWMB"] = ("Motor B PWM: IO21 (U3.23) to U2.15. Same LEDC timer as PWMA.")
R["AIN1"] = ("Motor A direction bit 1: IO9 (U3.17, an ADC-capable pin spent as GPIO) to U2.21.")
R["AIN2"] = ("Motor A direction bit 2: IO10 (U3.18) to U2.22.")
R["BIN1"] = ("Motor B direction bit 1: IO38 (U3.31) to U2.17.")
R["BIN2"] = (
    "Motor B direction bit 2: IO45 (U3.26) to U2.16. IO45 is the VDD_SPI STRAP -- safe only "
    "because this net idles low and carries R65 10k to GND (a high at reset would select "
    "1.8V flash supply and brick the boot). NEVER add a pull-up to this net.")
R["STBY"] = (
    "TB6612 standby (active low): IO46 (U3.16) to U2.19 with R66 10k pull-down. IO46 is a "
    "boot strap (must be low at reset when IO0 is held) -- the pull-down guarantees it AND "
    "holds the motor driver disabled from power-on until firmware acts. Same no-pull-up rule "
    "as BIN2.")

for _sig, _pin, _pad, _conn, _r in (("ENC1_A", "IO47", "U3.24", "J5.5", "R6"),
                                      ("ENC1_B", "IO48", "U3.25", "J5.6", "R7")):
    R[_sig] = (
        f"Motor A encoder phase {_sig[-1]}: from {_conn} into {_pin} ({_pad}), 10k pull-up "
        f"{_r} (defensive: encoder output stage unverified -- required if open-drain, "
        f"harmless if push-pull). Decoded by an S3 PCNT unit (hardware quadrature, any-pin "
        f"via the GPIO matrix).")
R["ENC2_A"] = (
    "Motor B encoder phase A: J6.5 with pull-up R8, then THROUGH R57 1k into the module "
    "(see ENC2_A_S3). The series guard exists because this pin pair is UART0.")
R["ENC2_B"] = (
    "Motor B encoder phase B: J6.6 with pull-up R9, through R58 1k (see ENC2_B_S3).")
R["ENC2_A_S3"] = (
    "Module side of the ENC2_A guard: R57 -> RXD0/IO44 (U3.36). IO44 is an input at reset "
    "(safe); the guard is for symmetry with IO43 and noise robustness. PCNT input is high-Z "
    "so 1k costs nothing at encoder frequencies.")
R["ENC2_B_S3"] = (
    "Module side of the ENC2_B guard: R58 -> TXD0/IO43 (U3.37). BLOCKER FIX from the "
    "adversarial review: IO43 is U0TXD, actively DRIVEN by the ROM at every boot while a "
    "push-pull encoder can drive the same node -- the 1k bounds the contention current. "
    "Firmware must set the console to USB-Serial-JTAG so UART0 never re-enables.")

# --- Sensor nets ---
for i, name in enumerate(SENSOR_NAMES):
    p = sensor_parts(i)
    if name.startswith("WALL"):
        k = int(name[4:])
        R[f"{name}_SENSE"] = (
            f"Analog node of the {SENSOR_ROLE[name]}: {p['photo']} collector, pulled to +3V3 "
            f"by {p['pullup']} 47k, read DIRECTLY on ESP32 ADC1 {WALL_ADC[k]} -- no mux (user "
            f"decision 2026-07-15; the bare S3 has 10 WiFi-safe ADC1 channels). More reflected "
            f"IR -> lower voltage. Also drives the gate of Q{27+k} (wall indicator PMOS -- "
            f"zero-DC-load gate). Fire the sensor's emitter GROUP and sample bright/ambient, "
            f"subtracting in firmware; both sensors of a fired pair sample in parallel.")
    else:
        k = int(name[4:])
        R[f"{name}_SENSE"] = (
            f"Analog node of the {SENSOR_ROLE[name]}: {p['photo']} collector + {p['pullup']} "
            f"47k pull-up, into line-mux channel I{k-1} (U4.{ {1:'9',2:'8',3:'7',4:'6',5:'5',6:'4',7:'3',8:'2'}[k] }); "
            f"selected by MUX_S0-2 it appears on MUX_SENSE (ADC1 IO7). Also drives the gate "
            f"of Q{19+k} (line indicator -- zero-DC-load).")
    a_net = pin2net.get((p["led"], "2"))
    if a_net and a_net.startswith("Net-"):
        _rv = "33R" if i < 6 else "120R"
        R[a_net] = (
            f"{name} IR-LED anode ({p['led']}.2) to its {_rv} current limiter "
            f"({p['curr']}.2) from +3V3. Cathode joins the {p['group']} group's switched "
            f"net -- per-LED current stays resistor-defined within the ganged group.")

# --- Indicator nets ---
for k in range(1, 9):   # line indicators: D15-22, Q20-27, R41-48
    d, q, r = f"D{14+k}", f"Q{19+k}", f"R{40+k}"
    kn = pin2net.get((d, "1"))
    an = pin2net.get((d, "2"))
    if kn and kn.startswith("Net-"):
        R[kn] = (
            f"LINE{k} indicator LED cathode ({d}.1) to {q}'s drain. {q}'s gate rides "
            f"LINE{k}_SENSE (zero DC load; if the channel reads pinned suspect this gate). "
            f"Threshold behavior around Vgs(th): LED ON = dark line under the sensor, WHILE "
            f"the line emitters are lit (the 120R latched-bank scheme).")
    if an and an.startswith("Net-"):
        R[an] = (
            f"LINE{k} indicator LED anode ({d}.2) to its 1k limiter ({r}.2) from +3V3 "
            f"(~1.4mA; high-efficiency AlInGaP super-red bin REQUIRED -- standard red washes "
            f"out in daylight at this current).")
for k in range(1, 7):   # wall indicators: D23-28, Q28-33, R49-54
    d, q, r = f"D{22+k}", f"Q{27+k}", f"R{48+k}"
    dn = pin2net.get((q, "D"))
    an = pin2net.get((d, "2"))
    if dn and dn.startswith("Net-"):
        R[dn] = (
            f"WALL{k} indicator drive: {q} (BSS84 PMOS, source at +3V3, gate on WALL{k}_SENSE) "
            f"drain into {r} 1k. POLARITY INVERTED vs the line indicators: a wall reflection "
            f"pulls the node LOW -> Vgs negative -> LED ON = wall seen. Zero-DC-load gate, "
            f"threshold behavior; meaningful while the wall emitter groups are lit (latch a "
            f"group in debug mode: 2x50mA, inside the SFH4550 continuous rating).")
    if an and an.startswith("Net-"):
        R[an] = (
            f"WALL{k} indicator LED anode ({d}.2) from {r} 1k (drive current ~1.4mA); "
            f"cathode to GND. Super-red high-efficiency bin, same as the line indicators.")

R["MOTA_P"] = ("Motor A M+ : U2 AO1 (doubled pins 1+2, micro-bridged) to J5.1. Full PWM-chopped motor current -- "
                "0.5mm trace. If the motor runs backwards, flip direction bits in firmware.")
R["MOTA_N"] = ("Motor A M- : U2 AO2 (pins 5+6) to J5.2. See MOTA_P.")
R["MOTB_P"] = ("Motor B M+ : U2 BO1 (pins 11+12) to J6.1. See MOTA_P.")
R["MOTB_N"] = ("Motor B M- : U2 BO2 (pins 7+8) to J6.2. See MOTA_P.")

# ---------------------------------------------------------------------------
# No-connects
# ---------------------------------------------------------------------------
NC_REASONS = {
    ("U3", "18"): "IO10 -- the one spare ADC1 channel, reserved for a future analog input.",
    ("U4", "16"): "Line-mux channel I15 -- only 8 line sensors; channels 8-15 unused.",
    ("U4", "17"): "I14 -- unused, see I15.",
    ("U4", "18"): "I13 -- unused.",
    ("U4", "19"): "I12 -- unused.",
    ("U4", "20"): "I11 -- unused.",
    ("U4", "21"): "I10 -- unused.",
    ("U4", "22"): "I9 -- unused.",
    ("U4", "23"): "I8 -- unused.",
    ("J7", "A8"): "SBU1 -- not used in USB 2.0.",
    ("J7", "B8"): "SBU2 -- not used in USB 2.0.",
}

def nc_reason(ref, pin):
    if (ref, pin) in NC_REASONS:
        return NC_REASONS[(ref, pin)]
    return "Intentionally unconnected."

# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------
GROUPS = [
    ("Power input & protection (1S LiPo)",
     ["Net-(J1-Pin_1)", "Net-(J2-Pin_2)", "Net-(F1-Pad2)", "Net-(Q1-PadG)", "VM_BATT"]),
    ("3.3V regulation (TPS63001 buck-boost)",
     ["Net-(U1-L1)", "Net-(U1-L2)", "PLUS3V3"]),
    ("Ground", ["GND"]),
    ("Battery monitoring", ["VBAT_SENSE"]),
    ("Controller support (EN / USB-C / JTAG / buttons)",
     ["ESP_EN", "USB_DM_C", "USB_DP_C", "Net-(R59-Pad1)", "Net-(R60-Pad1)",
      "USB_DM", "USB_DP", "Net-(J7-CC1)", "Net-(J7-CC2)", "USB_VBUS", "VBUS_SENSE",
      "JTAG_TCK", "JTAG_TDO", "JTAG_TDI", "JTAG_TMS",
      "USER_BTN", "USER_BTN2", "USER_BTN3"]),
    ("Motor drive (socketed TB6612 breakout)",
     ["STBY", "PWMA", "AIN1", "AIN2", "MOTA_P", "MOTA_N",
      "PWMB", "BIN1", "BIN2", "MOTB_P", "MOTB_N"]),
    ("Encoders (PCNT hardware quadrature)",
     ["ENC1_A", "ENC1_B", "ENC2_A", "ENC2_A_S3", "ENC2_B", "ENC2_B_S3"]),
    ("IR sensing -- shared control",
     ["MUX_S0", "MUX_S1", "MUX_S2", "MUX_SENSE",
      "LINE_EMIT", "WALL_EMIT_FRONT", "WALL_EMIT_DIAG", "WALL_EMIT_SIDE",
      "EMIT_FRONT_K", "EMIT_DIAG_K", "EMIT_SIDE_K", "EMIT_LINE_K"]),
    ("Wall sensors (direct ADC1)",
     [f"WALL{k}_SENSE" for k in range(1, 7)] +
     [n for i in range(6) for n in [pin2net.get((sensor_parts(i)["led"], "2"))] if n]),
    ("Line sensors (muxed)",
     [f"LINE{k}_SENSE" for k in range(1, 9)] +
     [n for i in range(6, 14) for n in [pin2net.get((sensor_parts(i)["led"], "2"))] if n]),
    ("Line indicator LEDs (top, threshold)",
     [n for k in range(1, 9) for n in (pin2net.get((f"D{14+k}", "1")), pin2net.get((f"D{14+k}", "2"))) if n and n.startswith("Net-")]),
    ("Wall indicator LEDs (top, PMOS -- LED ON = wall seen)",
     [n for k in range(1, 7) for n in (pin2net.get((f"Q{27+k}", "D")), pin2net.get((f"D{22+k}", "2"))) if n and n.startswith("Net-")]),
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
    "Generated by `tools/gen_connections.py` from `netlist.net` (ERC-clean). **Regenerate "
    "after any schematic change** -- the generator aborts if any net lacks a justification.\n")

out.append("## How parts attach (rev 4)\n")
out.append(
    "| Part | Attachment | Why |\n|---|---|---|\n"
    "| ESP32-S3-WROOM-1 (U3, SOLE controller) | **SMD, soldered** | User decision 2026-07-15: the only ESP32 in stock KiCad with exact footprint AND 3D model; dual-core 240MHz FreeRTOS; 10 WiFi-safe ADC1 channels let all 6 wall sensors read directly. Antenna overhangs the right board edge (Espressif: interior placement disallowed). Use non-R8 modules or lose IO35/36 (buttons 2/3). |\n"
    "| Motor driver (TB6612FNG) | **SMD, soldered** (U2, SSOP-24, stock 3D model) | Rev 5: bare chip saves the socket area + kills the vendor-pinout risk; C11/C12/C14 decouple at the chip. |\n"
    "| Motors (2x N20 + encoder) | **Pluggable** -- JST-PH 6-pin (J5/J6) | True-size mechanical footprints + 3D on the board (project n20 lib). Verify wire order at assembly. |\n"
    "| Battery | **Pluggable** -- JST-PH 2-pin (J1), 1S LiPo | 1S = no balance lead; buck-boost makes 3V3. |\n"
    "| USB-C (J7, REAR edge) | **SMD** GCT USB4105 | Flash + console via native USB; VBUS unused (battery powers the board). ESD array + 22R series per review. |\n"
    "| JTAG (J8) | 1.27mm 2x5 header | ESP-Prog pinout on the S3's dedicated JTAG quad IO39-42. |\n"
    "| Buttons | A=SW1 (start/BOOT), B=SW3, C=SW4, RST=SW2 -- lettered on the silkscreen | 3 user buttons + reset. |\n"
    "| Line optics (8x) | **SMD, bottom face** | Daylight-filtered receivers REQUIRED (optical feedback from the red indicators). |\n"
    "| Wall optics (6x), regulator, mux, passives | **Soldered** | Wall sensors THT with bent-lead aiming per Decimus practice. |\n")

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
            continue
        out.append(f"### `{net}`\n")
        out.append(f"**Pins:** {fmt_pins(nets[net])}\n")
        out.append(rationale + "\n")
        documented.add(net)

nc_nets = sorted(n for n in nets if n.startswith("unconnected-"))
out.append("\n## Deliberate no-connects\n")
out.append("| Pin | Function | Why unconnected |\n|---|---|---|\n")
for net in nc_nets:
    nodes = nets[net]   # stacked symbol pins (e.g. the 4 VBUS pads) share one NC net
    ref, pin = nodes[0]
    pins_str = ", ".join(f"`{r}.{p}`" for r, p in nodes)
    nm = pin_name(ref, pin)
    out.append(f"| {pins_str} | {nm} | {nc_reason(ref, pin)} |\n")
    documented.add(net)

missing = [n for n in nets if n not in documented]
if missing:
    print("FATAL: nets present in netlist but not documented:")
    for n in missing:
        print("   ", n, nets[n])
    sys.exit(1)

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))
print(f"Wrote {OUT}: {len(documented)} nets documented, 0 missing.")
