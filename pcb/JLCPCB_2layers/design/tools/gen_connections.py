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
AP63203_PINS = {"1": "FB(VOUT)", "2": "EN", "3": "VIN", "4": "GND", "5": "SW", "6": "BST"}
TPS54302_PINS = {"1": "GND", "2": "SW", "3": "VIN", "4": "FB", "5": "EN", "6": "BOOT"}
BNO055_PINS = {"1": "RESV", "2": "GND", "3": "VDD", "4": "nBOOT_LOAD", "5": "PS1",
               "6": "PS0", "9": "CAP", "10": "BL_IND", "11": "nRESET", "14": "INT",
               "17": "COM3/ADDR", "18": "COM2", "19": "COM1/SCL", "20": "COM0/SDA",
               "25": "GNDIO", "26": "XOUT32", "27": "XIN32", "28": "VDDIO"}
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
    "U1": AP63203_PINS,
    "U7": TPS54302_PINS,
    "U8": BNO055_PINS,
    "J9": {"1": "B- (GND)", "2": "B1+ (midpoint)", "3": "B2+ (pack +)"},
    "SW5": {"1": "GND throw", "2": "common (PWR_EN)", "3": "NC throw"},
    "SW6": {"1": "GND throw", "2": "common (MOT_EN)", "3": "NC throw"},
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
    "Protected raw 2S pack rail (6.0-8.4V), downstream of fuse F1 (MINISMDC260F/16: 2.6A "
    "hold, 16V -- 2S-rated) and reverse-polarity P-FET Q1 (DMP3098L-7, Vgs +/-20V: the old "
    "DMP2035U was +/-8V and 2S-UNSAFE; battery enters at the DRAIN, body-diode analysis in "
    "PROJECT_NOTES). Feeds BOTH bucks (U1 AP63203 3V3 logic, U7 TPS54302 6V motor rail), "
    "input caps C1/C2/C4/C18 (25V-class ceramics -- the 1S-era 6.3-10V bulk parts are "
    "banned on this rail), the R69 soft-switch pull-up and the R2 pack divider (tapped "
    "downstream of Q1 so a stored pack sees no divider drain).")

R["VBAT_SENSE"] = (
    "Pack voltage divided 100k/39k (8.4V -> 2.36V) with C6 filtering, read through mux "
    "channel Y8 (U4.23) -- rev 6 moved battery telemetry onto the 4067's spare channels "
    "to free IO8 for MUX_S3. Firmware cutoff: 6.6V pack (3.3V/cell).")

R["BATT_RAW"] = (
    "Battery positive from the 2S pack (J1.1, JST-XH 2-pin: 3A/contact covers the twin-N20 "
    "stall peak) into fuse F1, with the balance connector's pack+ pin (J9.3) on the same "
    "node (it IS the same pack terminal). No onboard charging: a 2S pack charges on an "
    "external balance charger; J9 only monitors while driving.")
R["Net-(Q1-D)"] = (
    "Fused battery positive into Q1's DRAIN (reverse-polarity P-FET: at power-up the body "
    "diode conducts, the channel then enhances; reversed battery blocks both paths).")
R["Net-(Q1-G)"] = (
    "Q1 gate to R1 100k to GND: Vgs = -Vbatt (max -8.4V, inside DMP3098L's +/-20V rating) "
    "when correct (hard on), >= 0 when reversed (off).")
R["PWR_EN"] = (
    "Master soft-power node: R69 1M pulls it to VM_BATT; slide SW5 grounds it. Drives the "
    "AP63203's EN (U1.2, VIN-tolerant) AND sources the MOT_EN pull-up -- so the motor rail "
    "can only be enabled when the master switch is already on.")
R["SW_3V3"] = (
    "3V3 buck switch node: AP63203 SW (U1.5) -> L1 4.7uH (SRP4020TA) -> PLUS3V3, with the "
    "BST bootstrap cap C3 across SW. Fast square edges -- tight loop, L1 beside U1.")
R["SW_6V"] = (
    "6V buck switch node: TPS54302 SW (U7.2) -> L2 4.7uH -> VM_6V, with BOOT cap C15 "
    "across SW. Same tight-loop rule as SW_3V3.")
R["FB_6V"] = (
    "TPS54302 feedback: R73 100k from VM_6V / R74 11k to GND -> 0.596V x (1 + 100/11) = "
    "6.01V regulated motor rail.")
R["MOT_EN"] = (
    "Motor-rail enable: R70 330k from PWR_EN / R71 110k to GND divide the (up to 8.4V) "
    "node to <=2.1V at the TPS54302 EN pin; slide SW6 grounds it = motors off. Both "
    "switches must be ON for the motors to spin (user requirement 7).")
R["VM_6V"] = (
    "The REGULATED 6.0V motor rail (user requirement 4: fixed voltage): TPS54302 output "
    "through L2 into the TB6612's VM1/2/3 with C30 220uF/16V alu bulk at the VM entry "
    "(motor hot-loop, IPC/standards item), C11 10uF/25V + C12 100nF at the pins and "
    "C16/C17 22uF/25V at the buck. The buck's ~3A current limit is the supply-side "
    "ceiling; steady 6.0V holds across the 6.6-8.4V pack window (graceful dropout below "
    "-- documented competition practice, with firmware Vbat feed-forward).")
R["BAT_MID"] = (
    "2S pack midpoint (cell-1 top) from the balance connector J9.2 into the R75/R76 "
    "divider -- per-cell monitoring so firmware can cut off on EITHER weak cell.")
R["BAT_MID_SENSE"] = (
    "Pack midpoint divided 100k/100k (4.2V -> 2.1V) with C19 filtering, read through mux "
    "channel Y9 (U4.22). Cell2 voltage = pack - midpoint, computed in firmware.")
R["IMU_SDA"] = (
    "I2C data to the BNO055 9-axis IMU (U8 COM0, addr 0x28 with COM3 grounded): IO18 "
    "(U3.11) with R77 4.7k pull-up. IO18/IO21 were freed by the TB6612 IN/IN PWM mode "
    "(PWMA/PWMB tied high).")
R["IMU_SCL"] = (
    "I2C clock to the BNO055 (U8 COM1): IO21 (U3.23) with R78 4.7k pull-up, 400kHz.")
R["IMU_INT"] = (
    "BNO055 interrupt out (U8.14) to IO37 (U3.30) -- data-ready/any-motion; the control "
    "loop may also simply poll at 500Hz.")
R["Net-(U8-CAP)"] = (
    "BNO055 internal-LDO bypass pin: C20 100nF to GND (Adafruit reference value).")
R["Net-(U8-~{BOOT_LOAD_PIN})"] = (
    "BNO055 nBOOT_LOAD_PIN held high by R79 10k: normal boot (low would enter the "
    "bootloader).")
R["Net-(U8-~{RESET})"] = (
    "BNO055 nRESET held high by R80 10k; no reset GPIO spent -- power-cycle or the "
    "watchdog covers it.")
R["BUZZ_CTRL"] = (
    "IO46 (U3.16, the only free GPIO; strap-safe -- the load only ever pulls it low) "
    "to R81 220R: base drive for the buzzer's NPN. LEDC ~4kHz square wave = beep.")
R["Net-(Q34-B)"] = (
    "R81 220R into Q34 (MMBT2222A) base: 12mA drive, forced beta ~18 = hard "
    "saturation at the buzzer coil's ~220mA peak.")
R["BUZZ_DRV"] = (
    "Q34 collector sinking BZ1 (CMT-8504 magnetic transducer, + pin on 3V3) with "
    "D29 1N4148W flyback clamp across the coil. Beep duty-limited in firmware -- "
    "~110mA average while sounding, from the 2A 3V3 rail.")

R["Net-(U1-BST)"] = (
    "AP63203 bootstrap: C3 100nF from BST to the SW node -- high-side gate-drive supply "
    "(datasheet-mandated).")
R["Net-(U7-BOOT)"] = (
    "TPS54302 bootstrap: C15 100nF from BOOT to SW -- same high-side supply role as U1's.")
R["Net-(U2-STBY)"] = (
    "TB6612 STBY tied HIGH through R55 10k to 3V3 (rev 6): the hardware motor kill is now "
    "SW6 (the 6V rail's enable) and the driver's IN pins have internal pull-downs, so a "
    "held-in-reset MCU leaves the outputs off. Freeing STBY's old GPIO (IO46, a strap pin) "
    "removed the last strap-risk output entirely.")
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
    "USB D- module side: DIRECT from the ESD array to the module's dedicated USB_D- pad "
    "(IO19). Rev 6 removed the 22R series resistors: the S3's integrated FS PHY meets the "
    "USB driver-impedance window internally and every Espressif S3 devkit routes these "
    "pins directly (standards review 2026-07-17). Native USB-Serial/JTAG: flashing and "
    "the CDC console.")
R["USB_DP"] = (
    "USB D+ module side: ESD array direct to the module USB_D+ pad (IO20). See USB_DM.")
R["USB_VBUS"] = (
    "The USB-C VBUS pads (all four, bridged) into the R67/R68 sense divider. VBUS does NOT "
    "power the board (battery does; a 5V feed would need a regulator + power mux) -- it is "
    "used purely as cable-presence detection.")
R["VBUS_SENSE"] = (
    "VBUS divided 10k/15k (5V -> 3.0V) read through mux channel Y10 (U4.21) -- cable "
    "presence detection (e.g. auto-enable CDC logging); IO37 now serves the IMU interrupt.")

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
        f"Mux select bit {_i}: IO1{1+_i} (U3.{19+_i}) to U4 S{_i}. The line array occupies "
        "channels I0-I7; battery/system telemetry (VBAT / BAT_MID / VBUS) rides Y8-Y10.")
R["MUX_S3"] = (
    "Mux select bit 3: IO8 (U3.12) to U4 S3 -- rev 6 promoted the 4067's high select from "
    "a GND tie to a GPIO, opening channels Y8-Y15 for the battery/VBUS telemetry that "
    "used to burn dedicated ADC pins.")

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
    a_net = (pin2net.get((p["led"], "2")) if i < 6
             else pin2net.get((f"LS{i-5}", "1")))   # line channels: the TCRT's own LED anode (pad 1)
    if a_net and a_net.startswith("Net-"):
        _rv = "33R" if i < 6 else "120R"
        _src = p["led"] + ".2" if i < 6 else f"LS{i-5}.1"
        R[a_net] = (
            f"{name} IR-LED anode ({_src}) to its {_rv} current limiter "
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
    dn = pin2net.get((q, "D")) or pin2net.get((q, "3"))   # Q_PMOS_GSD pins are numbered
    an = pin2net.get((d, "2"))
    if dn and dn.startswith("Net-"):
        R[dn] = (
            f"WALL{k} indicator drive: {q} (BSS84 PMOS, source at +3V3, gate on WALL{k}_SENSE) "
            f"drain into {r} 1k. POLARITY INVERTED vs the line indicators: a wall reflection "
            f"pulls the node LOW -> Vgs negative -> LED ON = wall seen. Zero-DC-load gate, "
            f"threshold behavior; meaningful while the wall emitter groups are lit (latch a "
            f"group in debug mode: 2x50mA, inside the IR333-A continuous rating).")
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
    ("Power input & protection (2S LiPo)",
     ["BATT_RAW", "Net-(Q1-D)", "Net-(Q1-G)", "VM_BATT"]),
    ("3.3V regulation (AP63203 buck) + soft power switch",
     ["SW_3V3", "Net-(U1-BST)", "PWR_EN", "PLUS3V3"]),
    ("6V motor rail (TPS54302 buck) + motor switch",
     ["SW_6V", "Net-(U7-BOOT)", "FB_6V", "MOT_EN", "VM_6V"]),
    ("Ground", ["GND"]),
    ("Battery monitoring (pack + per-cell via mux)",
     ["VBAT_SENSE", "BAT_MID", "BAT_MID_SENSE"]),
    ("IMU (BNO055, I2C)",
     ["IMU_SDA", "IMU_SCL", "IMU_INT",
      "Net-(U8-CAP)", "Net-(U8-~{BOOT_LOAD_PIN})", "Net-(U8-~{RESET})"]),
    ("Controller support (EN / USB-C / JTAG / buttons)",
     ["ESP_EN", "USB_DM_C", "USB_DP_C",
      "USB_DM", "USB_DP", "Net-(J7-CC1)", "Net-(J7-CC2)", "USB_VBUS", "VBUS_SENSE",
      "JTAG_TCK", "JTAG_TDO", "JTAG_TDI", "JTAG_TMS",
      "USER_BTN", "USER_BTN2", "USER_BTN3"]),
    ("Motor drive (TB6612 SMD, IN/IN PWM mode; PWMA/PWMB/STBY tied high)",
     ["AIN1", "AIN2", "MOTA_P", "MOTA_N",
      "BIN1", "BIN2", "MOTB_P", "MOTB_N", "Net-(U2-STBY)"]),
    ("Encoders (PCNT hardware quadrature)",
     ["ENC1_A", "ENC1_B", "ENC2_A", "ENC2_A_S3", "ENC2_B", "ENC2_B_S3"]),
    ("Buzzer (IO46, rev 7.2)",
     ["BUZZ_CTRL", "Net-(Q34-B)", "BUZZ_DRV"]),
    ("IR sensing -- shared control",
     ["MUX_S0", "MUX_S1", "MUX_S2", "MUX_S3", "MUX_SENSE",
      "LINE_EMIT", "WALL_EMIT_FRONT", "WALL_EMIT_DIAG", "WALL_EMIT_SIDE",
      "EMIT_FRONT_K", "EMIT_DIAG_K", "EMIT_SIDE_K", "EMIT_LINE_K"]),
    ("Wall sensors (direct ADC1)",
     [f"WALL{k}_SENSE" for k in range(1, 7)] +
     [n for i in range(6) for n in [pin2net.get((sensor_parts(i)["led"], "2"))] if n]),
    ("Line sensors (muxed)",
     [f"LINE{k}_SENSE" for k in range(1, 9)] +
     [n for k in range(1, 9) for n in [pin2net.get((f"LS{k}", "1"))] if n and n.startswith("Net-")]),
    ("Line indicator LEDs (top, threshold)",
     [n for k in range(1, 9) for n in (pin2net.get((f"D{14+k}", "1")), pin2net.get((f"D{14+k}", "2"))) if n and n.startswith("Net-")]),
    ("Wall indicator LEDs (top, PMOS -- LED ON = wall seen)",
     [n for k in range(1, 7) for n in (pin2net.get((f"Q{27+k}", "D")), pin2net.get((f"Q{27+k}", "3")), pin2net.get((f"D{22+k}", "2"))) if n and n.startswith("Net-")]),
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
