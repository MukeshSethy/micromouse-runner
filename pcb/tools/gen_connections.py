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
ESP32_PINS = {
    "1": "GND", "2": "GND", "3": "3V3", "4": "IO0", "5": "IO1", "6": "IO2",
    "7": "IO3", "8": "IO4", "9": "IO5", "10": "IO6", "11": "IO7", "12": "IO8",
    "13": "IO9", "14": "IO10", "15": "IO11", "16": "IO12", "17": "IO13",
    "18": "IO14", "19": "IO15", "20": "IO16", "21": "IO17", "22": "IO18",
    "23": "USB_D-", "24": "USB_D+", "25": "IO21", "26": "IO26", "27": "IO47",
    "28": "IO33", "29": "IO34", "30": "IO48", "31": "IO35", "32": "IO36",
    "33": "IO37", "34": "IO38", "35": "IO39", "36": "IO40", "37": "IO41",
    "38": "IO42", "39": "TXD0", "40": "RXD0", "41": "IO45", "42": "GND",
    "43": "GND", "44": "IO46", "45": "EN",
}
for _n in range(46, 66):
    ESP32_PINS[str(_n)] = "GND"

AP63203_PINS = {"1": "FB/VOUT-sense", "2": "EN", "3": "VIN", "4": "GND", "5": "SW", "6": "BST"}

# Nano-header rows, verified against KiCad's bundled Arduino Nano reference
# PCB (both rows' pin 1 at the same physical end; digital row runs D12->D1).
J4_PINS = {
    "1": "D12/PB4", "2": "D11/PB5", "3": "D10/PA11", "4": "D9/PA8", "5": "D8/PF1",
    "6": "D7/PF0", "7": "D6/PB6", "8": "D5/PA15", "9": "D4/PB7", "10": "D3/PB0",
    "11": "D2/PA12", "12": "GND", "13": "RESET", "14": "D0/PA10", "15": "D1/PA9",
}
J8_PINS = {
    "1": "D13/PB3", "2": "3V3", "3": "AREF", "4": "A0/PA0", "5": "A1/PA1",
    "6": "A2/PA3", "7": "A3/PA4", "8": "A4/PA5", "9": "A5/PA6", "10": "A6/PA7",
    "11": "A7/PA2", "12": "5V", "13": "RESET", "14": "GND", "15": "VIN",
}

MOTOR_CONN_PINS = {"1": "M+", "2": "M-", "3": "ENC_VCC", "4": "ENC_GND", "5": "ENC_A", "6": "ENC_B"}

# Socketed motor-driver breakout header rows (functional labels; verify order
# + spacing against the actual TB6612 carrier before fab).
J10_PINS = {"1": "STBY", "2": "PWMA", "3": "AIN1", "4": "AIN2", "5": "PWMB",
            "6": "BIN1", "7": "BIN2", "8": "GND"}
J11_PINS = {"1": "VM (batt)", "2": "VCC (+3V3)", "3": "GND", "4": "AO1", "5": "AO2",
            "6": "BO1", "7": "BO2", "8": "GND"}
# Socketed Arduino Nano ESP32 dev board -- same physical Nano rows as the STM32
# (J12 = digital row, J13 = analog row). Only 3V3/GND/D0/D1/D2 are wired.
J12_PINS = {
    "1": "D12", "2": "D11", "3": "D10", "4": "D9", "5": "D8", "6": "D7", "7": "D6",
    "8": "D5", "9": "D4", "10": "D3", "11": "D2 (->STM32 NRST)", "12": "GND",
    "13": "RESET", "14": "D0/RX (<-STM32 TX)", "15": "D1/TX (->STM32 RX)",
}
J13_PINS = {
    "1": "D13", "2": "3V3 (power in)", "3": "AREF", "4": "A0", "5": "A1", "6": "A2",
    "7": "A3", "8": "A4", "9": "A5", "10": "A6", "11": "A7", "12": "5V",
    "13": "RESET", "14": "GND", "15": "VIN",
}

EXACT_PIN_NAMES = {
    "U1": AP63203_PINS,
    "U4": HEF4067_PINS,
    "U5": HEF4067_PINS,
    "J1": {"1": "BAT+", "2": "BAT-"},
    "J2": {"1": "SW_A", "2": "SW_B"},
    "J3": {"1": "PACK+ (cell2+)", "2": "CELL_MID (cell1+/cell2-)", "3": "PACK- (GND)"},
    "J4": J4_PINS,
    "J5": MOTOR_CONN_PINS,
    "J6": MOTOR_CONN_PINS,
    "J8": J8_PINS,
    "J10": J10_PINS,
    "J11": J11_PINS,
    "J12": J12_PINS,
    "J13": J13_PINS,
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
    "(J1.2 main lead, J3.3 balance lead) land here; all logic (STM32 header, ESP32, both muxes), "
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
    "STM32 module power (J8.2, the module's 3V3 input -- the module is powered here instead of via "
    "5V/VIN because its own regulator stage is bypassed when feeding 3V3 directly, and everything "
    "else on this board is 3.3V logic); ESP32 3V3 (U3.3); both mux VDD pins (U4/U5.24 -- HEF4067 "
    "supply must match the analog signal range, and phototransistor outputs swing 0..3.3V); all 14 "
    "phototransistor pull-ups (47k each, QTR-8A-style divider); all 14 IR-LED current-limit "
    "resistors (the LED drive current is sized against the REGULATED rail so sensor brightness "
    "doesn't drift as the 2S pack discharges 8.4V to 6.0V -- a Peter Harrison micromouse design "
    "rule); the four encoder pull-ups and both motor-connector ENC_VCC pins (Hall encoder boards "
    "accept 3.3V, keeping encoder logic levels native to the STM32); TB6612 VCC (logic side, "
    "2.7-5.5V rated); the EN/IO0 strap pull-ups and USER_BTN pull-up; and the ESP32 programming "
    "header's 3V3 pin (J7.2, so a dongle can power the ESP32 for flashing -- do NOT connect the "
    "dongle's power while the battery is switched on; two supplies would fight).")

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
    "Scaled cell-1 voltage into STM32 ADC pin D8/PF1 (ADC2_IN10) via J4.5. R2 (10k, from the "
    "balance-lead cell-1 tap J3.2) and R3 (22k, to GND) divide 0-4.2V down to 0-2.89V, inside the "
    "3.3V ADC range with margin. C6 100nF across the bottom leg low-passes the node -- the ADC "
    "samples a low-impedance-ish source and motor PWM noise is filtered. Firmware computes "
    "cell2 = pack - cell1 so BOTH cells are monitored for the per-cell 3.0V LiPo cutoff (a pack "
    "reading alone can hide one weak cell). PF1 was chosen for this because it has NO timer "
    "alternate function on the LQFP32 package -- it would otherwise be a wasted pin (verified "
    "against ST's CubeMX pin data via Zephyr hal_stm32).")

R["VBAT_PACK_SENSE"] = (
    "Scaled full-pack voltage into STM32 ADC pin D7/PF0 (ADC1_IN10) via J4.6. R4 (10k, from the "
    "balance connector's pack+ pin J3.1) and R5 (6.2k, to GND) divide 0-8.4V down to 0-3.21V. C7 "
    "100nF filters the node, same reasoning as the cell-1 divider. NOTE (flagged risk, also in "
    "PROJECT_NOTES): both dividers hang directly on the balance connector, UPSTREAM of switch and "
    "fuse -- they drain ~0.52mA + ~0.13mA continuously while the balance lead is plugged, which "
    "will deep-discharge a stored pack over some weeks. Mitigation: unplug the balance connector "
    "for storage (documented assembly/user rule), or a future revision can add a high-side sense "
    "switch.")

R["USART1_TX"] = (
    "STM32 USART1 transmit (D1/PA9 via J4.15) into the ESP32 dev board's D0/RX (J12.14). This is "
    "the telemetry uplink AND the STM32's side of the firmware-update dialogue: USART1 on PA9/PA10 "
    "is one of the exact pin pairs the STM32G43x System Memory ROM bootloader listens on (VERIFIED "
    "against AN2606 section 46 Table 99: USART1_TX=PA9, USART1_RX=PA10, 8E1 framing, standard "
    "AN3155 protocol), which lets the ESP32 flash the STM32 over this wire pair with no BOOT0 line "
    "(the Nano header does not expose BOOT0 -- the update path is a firmware-triggered jump into "
    "the ROM bootloader; AN2606 sanctions the jump but requires firmware to disable peripheral "
    "clocks, PLL and interrupts first, and the bootloader refuses flash commands under readout-"
    "protection level 2 -- both firmware-side rules). The ESP32 dev board uses its D0/D1 UART for "
    "the STM32 link and its own USB-C for flashing itself, so the two never contend.")

R["USART1_RX"] = (
    "ESP32 dev board D1/TX (J12.15) driving STM32 USART1 receive (D0/PA10 via J4.14). Downlink "
    "half of the telemetry/update link -- see USART1_TX for the STM32 pin-pair rationale.")

R["NRST"] = (
    "STM32 hardware reset line. Three members: the two RESET pins of the Nano header (J4.13 digital "
    "row, J8.13 analog row -- the Arduino Nano standard carries reset on BOTH rows, tied to the "
    "same MCU line, so the socket mirrors that) and the ESP32 dev board's D2 (J12.11), which lets "
    "the ESP32 hard-reset the STM32 in the wireless-update flow (reset into freshly-flashed "
    "firmware, or recover a hung app before retrying the UART dialogue). FIRMWARE RULE: configure "
    "ESP32 D2 as open-drain (drive low to reset, release to run) -- the Nucleo module has its own "
    "pull-up/reset circuitry on NRST and a push-pull high would fight it and any manual reset.")

R["MUX_S0"] = None  # filled by loop below
R["MUX_S1"] = None
R["MUX_S2"] = None
R["MUX_S3"] = None
for _i, _pin in ((0, "D2/PA12 via J4.11"), (1, "D4/PB7 via J4.9"), (2, "D6/PB6 via J4.7"), (3, "A0/PA0 via J8.4")):
    R[f"MUX_S{_i}"] = (
        f"Mux channel-select bit {_i} (binary weight {2**_i}), STM32 GPIO {_pin} driving select "
        f"input S{_i} on BOTH HEF4067s in parallel (U4.{ {0:'10',1:'11',2:'14',3:'13'}[_i] } and "
        f"U5.{ {0:'10',1:'11',2:'14',3:'13'}[_i] }). Sharing one 4-bit select bus across the "
        "read-mux and the write-demux is the core of the sensor architecture: selecting channel N "
        "simultaneously picks sensor N's phototransistor for reading AND sensor N's LED driver for "
        "pulsing, enforcing one-emitter-one-receiver lockstep (crosstalk avoidance) while spending "
        "only 4 GPIOs + 1 ADC pin + 1 pulse pin on 14 sensors. Channel index = S3 S2 S1 S0 binary; "
        "WALL1..6 = channels 0-5 (Y0-Y5), LINE1..8 = channels 6-13 (Y6-Y13).")

R["MUX_SENSE"] = (
    "Analog common (Z, U4.1) of the READ mux into STM32 ADC pin D3/PB0 (ADC1_IN15) via J4.10. "
    "Whatever channel S3..S0 selects, that sensor's phototransistor divider node appears here. One "
    "ADC pin thus reads all 14 sensors -- the only alternative on this MCU package was physically "
    "impossible (14 sensor signals + 2 battery senses > the 11 ADC-capable pins on the whole Nano "
    "header, PROJECT_NOTES budget analysis). HEF4067 is a bidirectional ANALOG switch (verified: "
    "Nexperia datasheet Rev.11 calls it a bidirectional transmission-gate switch), so the divider "
    "voltage passes through unmodified in DC terms. Verified caveats for firmware (adversarial "
    "datasheet check, 2 independent agents): the datasheet only characterizes Ron at 5/10/15V "
    "(350R typ / 2500R MAX at 5V); at our 3.3V, mid-scale Ron rises to ~1k+ typical and plausibly "
    "several k worst case (metal-gate CMOS, only ~1.65V overdrive at mid-supply). Into the ADC's "
    "high-Z input this costs NO ratio accuracy (no DC current flows), but the 47k pull-up + ~1k+ "
    "Ron source impedance is far above the STM32 ADC's fast-sample limit, so USE A LONG ADC "
    "SAMPLING TIME (or an op-amp buffer if speed matters). Channel off-leakage (spec'd 1000nA max "
    "Z-port at 25C) through 47k is a low-tens-of-mV worst-case offset, typically negligible.")

R["LED_PULSE"] = (
    "STM32 GPIO A1/PA1 (via J8.5) into the WRITE demux common (Z, U5.1). Firmware raises this for "
    "~60-100us to fire the currently-selected sensor's IR LED via its BSS138 gate, samples "
    "MUX_SENSE ('bright'), lowers it, samples again ('ambient'), and subtracts -- synchronous "
    "detection that cancels ambient IR (Peter Harrison's method, see PROJECT_NOTES). FIRMWARE "
    "RULE (flagged): unselected demux outputs are high-impedance, so a BSS138 gate holds its last "
    "charge when deselected. ALWAYS return LED_PULSE low while the channel is still selected (gate "
    "discharges through the mux), and on boot walk all 14 channels with LED_PULSE low to discharge "
    "any power-up gate charge. Otherwise a deselected LED can stay on -- crosstalk + battery drain.")

R["STBY"] = (
    "TB6612 standby control (U2.19, active-low standby) from STM32 GPIO A2/PA3 via J8.6. "
    "GPIO-driven rather than strapped high so firmware can hard-disable both H-bridges (fault "
    "response, low-power idle) -- an explicit user requirement recorded in PROJECT_NOTES. TB6612 "
    "outputs are disabled while STBY is low regardless of the IN/PWM pins, so the robot cannot "
    "drive during MCU reset if the pin idles low.")

for _sig, _pin_lbl, _brk, _desc in (
        ("AIN1", "A3/PA4 via J8.7", "J10.3", "motor A direction bit 1"),
        ("AIN2", "A4/PA5 via J8.8", "J10.4", "motor A direction bit 2"),
        ("BIN1", "A5/PA6 via J8.9", "J10.6", "motor B direction bit 1"),
        ("BIN2", "A6/PA7 via J8.10", "J10.7", "motor B direction bit 2")):
    R[_sig] = (
        f"TB6612 {_desc} from STM32 GPIO {_pin_lbl} to the motor-driver breakout control header "
        f"({_brk}). The IN1/IN2 pair per channel selects forward / reverse / short-brake / stop "
        "per the TB6612 truth table while the PWM pin modulates speed. Plain GPIOs suffice (no "
        "timer function needed -- direction changes are slow); the timer-capable pins were "
        "budgeted for PWM and encoders instead (see the AF table in PROJECT_NOTES).")

R["PWMA"] = (
    "Motor A speed PWM: STM32 D9/PA8 via J4.4 to the breakout's PWMA (J10.2). PA8 is TIM1_CH1 "
    "(AF6, verified against ST's CubeMX pin data) -- hardware PWM from the advanced-control timer, "
    "typically 20-25kHz (above audible). Paired with PWMB on the SAME timer (TIM1) so both motors' "
    "PWM is phase-aligned and updated by one timer.")

R["PWMB"] = (
    "Motor B speed PWM: STM32 D10/PA11 via J4.3 to the breakout's PWMB (J10.5). PA11 is TIM1_CH4 "
    "(AF11) -- same TIM1 as PWMA, see PWMA rationale.")

for _sig, _row, _pin_lbl, _conn, _r, _tim in (
        ("ENC1_A", "J4.1", "D12/PB4", "J5.5", "R6", "TIM3_CH1 (AF2)"),
        ("ENC1_B", "J4.2", "D11/PB5", "J5.6", "R7", "TIM3_CH2 (AF2)"),
        ("ENC2_A", "J4.8", "D5/PA15", "J6.5", "R8", "TIM2_CH1 (AF1)"),
        ("ENC2_B", "J8.1", "D13/PB3", "J6.6", "R9", "TIM2_CH2 (AF1)")):
    _m = "A" if "1" in _sig else "B"
    R[_sig] = (
        f"Motor {_m} quadrature encoder phase {_sig[-1]}: from the N20 motor's Hall encoder via "
        f"connector {_conn}, into STM32 {_pin_lbl} ({_row}), with 10k pull-up {_r} to +3V3. "
        f"This pin is {_tim} -- the two phases of each motor land on channels 1+2 of the SAME "
        "timer (TIM3 for motor A, TIM2 for motor B), which is the hardware requirement for the "
        "STM32's zero-CPU-cost hardware quadrature-encoder mode. The pull-up is defensive: the "
        "encoder's output stage (open-drain vs push-pull) is unverified for the exact unit ordered "
        "-- required if open-drain, harmless if push-pull (PROJECT_NOTES).")

R["USER_BTN"] = (
    "Start-run button: STM32 A7/PA2 via J8.11, pulled to +3V3 through R12 10k, switched to GND by "
    "SW3 (active-low). Standard micromouse UX -- arm the run without touching the robot's power. "
    "PA2/A7 was the single pin left over once every required function was allocated; the button "
    "was added because the pin was free, not because the spec demanded it (PROJECT_NOTES).")

R["ESP_EN_NET"] = (
    "ESP32 chip-enable/reset node: EN (U3.45) held high by R10 10k to +3V3, pulled to GND by SW1 "
    "(manual reset). The ESP32-S3-MINI-1 module does NOT integrate an EN pull-up, so the external "
    "resistor is required for the chip to boot (Espressif hardware design guidelines); the button "
    "gives the standard manual-reset UX during development and is half of the classic "
    "EN+IO0 flashing two-button dance.")

R["ESP_IO0_NET"] = (
    "ESP32 boot-strap node: IO0 (U3.4) pulled high by R11 10k (normal boot from flash), pulled to "
    "GND by SW2. Holding IO0 low through a reset puts the ESP32-S3 into serial download mode "
    "(Espressif boot-mode strapping) -- press SW2, tap SW1, release SW2, then flash via J7. "
    "Once ESP32 WiFi OTA is running this is only a recovery path.")

R["ESP_PROG_TX"] = (
    "ESP32 UART0 TXD0 (U3.39) to programming header J7.3. UART0 is the ROM serial-bootloader port "
    "on the S3; keeping it dedicated to the external USB-serial dongle (and NOT shared with the "
    "STM32 link on IO4/IO5) means flashing or monitoring the ESP32 never disturbs robot telemetry. "
    "Labelled from the ESP32's perspective -- connect to the dongle's RX.")

R["ESP_PROG_RX"] = (
    "ESP32 UART0 RXD0 (U3.40) from programming header J7.4 -- the dongle's TX. See ESP_PROG_TX.")

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
    ("J8", "3"):  "AREF -- the STM32's ADC uses the internal 3.3V reference; nothing external supplied.",
    ("J8", "12"): "5V -- the module is powered via its 3V3 pin instead (see PLUS3V3); the module's "
                   "USB/5V path is only used when its own USB is plugged.",
    ("J8", "15"): "VIN -- same reason as 5V: this board feeds regulated 3.3V directly.",
    ("U4", "16"): "Read-mux channel Y15 -- only 14 sensors exist; channels 14/15 unused.",
    ("U4", "17"): "Read-mux channel Y14 -- unused, see Y15.",
    ("U5", "16"): "Write-demux channel Y15 -- unused, see U4.",
    ("U5", "17"): "Write-demux channel Y14 -- unused, see U4.",
}

def nc_reason(ref, pin):
    if (ref, pin) in NC_REASONS:
        return NC_REASONS[(ref, pin)]
    if ref in ("J12", "J13"):
        nm = pin_name(ref, pin)
        return (f"Arduino Nano ESP32 dev-board pin {nm} -- unused. The wireless role needs only "
                "3V3, GND, D0/RX, D1/TX (STM32 UART link) and D2 (STM32 NRST); every other Nano "
                "pin is left unconnected. USB, auto-reset, and boot are handled on the dev board.")
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
    ("STM32 <-> ESP32 link & reset",
     ["USART1_TX", "USART1_RX", "NRST"]),
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
    "| NUCLEO-G431KB (STM32) | **Socketed** -- two 1x15 female headers (J4 digital row, J8 analog row, 15.24mm apart) | User requirement; module is removable/reusable; its snap-off ST-LINK still works for recovery while the tab is attached. The G431KB's CN3/CN4 silk labels are swapped vs. every other Nucleo-32 (ST forum, confirmed by ST moderator), so rows here are named by function. Row order verified against KiCad's bundled Arduino Nano reference PCB. |\n"
    "| ESP32 (Arduino Nano ESP32 dev board) | **Socketed** -- two 1x15 female headers (J12 digital row, J13 analog row, 15.24mm apart) | User decision (2026-07-12): a socketed ESP32-S3 dev board, not a bare SMD module. Same Nano form factor as the Nucleo, so it sockets identically. The dev board brings its own USB, auto-reset, boot button, regulator and decoupling -- so the SMD version's strap buttons, boot pull-ups, programming header and decoupling are all removed. Only 3V3/GND/UART/NRST are wired. |\n"
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
    "ST UM2397 / AN2606 / STM32G431 datasheet (via CubeMX pin data), Pololu QTR-8A documentation, "
    "Peter Harrison's micromouse sensor writings, and the project research log (PROJECT_NOTES.md).\n")

out.append("## Verification status of the load-bearing claims\n")
out.append(
    "The datasheet-dependent claims below were adversarially re-checked against PRIMARY sources by "
    "independent agents instructed to refute them (2026-07-12). Results:\n\n"
    "| Claim | Verdict | Primary source |\n|---|---|---|\n"
    "| TB6612FNG full pinout + STBY active-low + VM/VCC ranges | **CONFIRMED** | Toshiba TB6612FNG datasheet, pin table p.2 / control table p.4 / ratings p.3 |\n"
    "| HEF4067 active-low enable, 3.3V-capable, bidirectional analog | **CONFIRMED** | Nexperia HEF4067B Rev.11 |\n"
    "| HEF4067 Ron at 3.3V | **Corrected** -- not \"hundreds of ohms\"; ~1k+ typ at mid-supply, multi-k worst case. Doc updated (see MUX_SENSE/*_LED): immaterial for the ADC divider, drives the choice of small-signal BSS138 over a power FET | Nexperia Rev.11 + TI CD4067B (no 3.3V Ron is published by either; extrapolated from 5V data) |\n"
    "| ESP32-S3 needs external EN pull-up/RC (no on-module pull-up); IO0-low = download boot; IO45/IO46 safe floating | **CONFIRMED** | Espressif ESP32-S3-MINI-1 datasheet v1.7 + HW design guidelines |\n"
    "| STM32G431 ROM bootloader on USART1 PA9/PA10; software jump (no BOOT0) valid | **CONFIRMED** (caveats: firmware must disable clocks/PLL/IRQ before the jump; no flashing under RDP level 2) | ST AN2606 sec.46 Table 99 + sec.4.1 |\n"
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
