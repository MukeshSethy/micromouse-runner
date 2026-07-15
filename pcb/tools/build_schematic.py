import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_sch import SchGen, snap, pin_at

# Full schematic generator -- supersedes build_power_mcu.py (kept only as history;
# this is the single regeneratable source of truth going forward). Bumped paper to
# A1 (841x594mm landscape) -- A2 only had the top-left ~2/3 used by Power+MCU, and
# the user already flagged once that a cramped layout wasn't acceptable, so err on
# the side of more room for the four new sections rather than cramming into what's
# left of A2.
g = SchGen("micromouse-pcb", paper="A1")

# ---------------------------------------------------------------------------
# Generic component helpers (same pin-transform convention as build_power_mcu.py:
# pin_at(base, local_offset) = (base_x+lx, base_y-ly), KiCad negates local Y).
# ---------------------------------------------------------------------------

def R(ref, value, at, n1=None, n2=None, footprint="Resistor_SMD:R_0805_2012Metric"):
    base = snap(at)
    g.add_component("Device", "R", ref, value, base, {"1": n1 or "", "2": n2 or ""}, footprint=footprint)
    return pin_at(base, (0, 3.81)), pin_at(base, (0, -3.81))

def C(ref, value, at, n1=None, n2=None, footprint="Capacitor_SMD:C_0805_2012Metric"):
    base = snap(at)
    g.add_component("Device", "C", ref, value, base, {"1": n1 or "", "2": n2 or ""}, footprint=footprint)
    return pin_at(base, (0, 3.81)), pin_at(base, (0, -3.81))

def L(ref, value, at, footprint="Inductor_SMD:L_Bourns_SRP7028A_7.3x6.6mm"):
    base = snap(at)
    g.add_component("Device", "L", ref, value, base, {"1": "", "2": ""}, footprint=footprint)
    return pin_at(base, (0, 3.81)), pin_at(base, (0, -3.81))

def FUSE(ref, value, at, footprint="Fuse:Fuse_1206_3216Metric"):
    base = snap(at)
    g.add_component("Device", "Fuse", ref, value, base, {"1": "", "2": ""}, footprint=footprint)
    return pin_at(base, (0, 3.81)), pin_at(base, (0, -3.81))

def CONN2(ref, value, at, footprint="Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal"):
    base = snap(at)
    g.add_component("Connector_Generic", "Conn_01x02", ref, value, base, {"1": "", "2": ""}, footprint=footprint)
    return pin_at(base, (-5.08, 0)), pin_at(base, (-5.08, -2.54))

def CONN_COL(ref, value, at, n, footprint):
    # Generic single-row (1xN) connector, pins running top-to-bottom on the
    # left side. KiCad's Conn_01xNN places pin 1 at local (-5.08, top_y) with
    # top_y = 2.54*((N-1)//2) -- INTEGER floor, verified against the real
    # Conn_01x08 symbol (pin1 at +7.62, not the 8.89 a naive (N-1)/2 gives;
    # KiCad grid-snaps even-count connectors so they aren't centered on 0).
    base = snap(at)
    g.add_component("Connector_Generic", f"Conn_01x{n:02d}", ref, value, base,
                     {str(k): "" for k in range(1, n + 1)}, footprint=footprint)
    top_y = 2.54 * ((n - 1) // 2)
    return [pin_at(base, (-5.08, top_y - 2.54 * i)) for i in range(n)]

def CONN3(ref, value, at, footprint="Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical"):
    base = snap(at)
    g.add_component("Connector_Generic", "Conn_01x03", ref, value, base, {"1": "", "2": "", "3": ""}, footprint=footprint)
    return pin_at(base, (-5.08, 2.54)), pin_at(base, (-5.08, 0)), pin_at(base, (-5.08, -2.54))

def CONN4(ref, value, at, footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"):
    base = snap(at)
    g.add_component("Connector_Generic", "Conn_01x04", ref, value, base,
                     {"1": "", "2": "", "3": "", "4": ""}, footprint=footprint)
    return (pin_at(base, (-5.08, 2.54)), pin_at(base, (-5.08, 0)),
            pin_at(base, (-5.08, -2.54)), pin_at(base, (-5.08, -5.08)))

def CONN6(ref, value, at, footprint="Connector_JST:JST_PH_B6B-PH-K_1x06_P2.00mm_Vertical"):
    base = snap(at)
    g.add_component("Connector_Generic", "Conn_01x06", ref, value, base,
                     {str(n): "" for n in range(1, 7)}, footprint=footprint)
    return [pin_at(base, (-5.08, 5.08 - 2.54 * i)) for i in range(6)]

def QPMOS(ref, value, at, footprint="Package_TO_SOT_SMD:SOT-23"):
    base = snap(at)
    g.add_component("Device", "Q_PMOS", ref, value, base, {"D": "", "G": "", "S": ""}, footprint=footprint)
    return pin_at(base, (2.54, 5.08)), pin_at(base, (-5.08, 0)), pin_at(base, (2.54, -5.08))  # D, G, S

def LED_SFH4550(ref, at, footprint="LED_THT:LED_D5.0mm_IRGrey"):
    # SFH4550's own symbol uses `extends "LD271"`, which silently skips ERC
    # pin-connectivity checking (PROJECT_NOTES facts #2/#8: confirmed empirically
    # that AP63203WU-extends-AP63200WU produced zero pin_not_connected errors with
    # every pin floating). Instantiate the real LD271 base symbol directly instead
    # -- same physical pinout, footprint, and datasheet part -- with the actual
    # part name (SFH4550) recorded in Value.
    base = snap(at)
    g.add_component("LED", "LD271", ref, "SFH4550 (real part; LD271 base symbol used so ERC checks pins)",
                     base, {"1": "", "2": ""}, footprint=footprint,
                     datasheet="http://www.osram-os.com/Graphics/XPic3/00116140_0.pdf")
    return pin_at(base, (-5.08, 0)), pin_at(base, (2.54, 0))  # K (cathode), A (anode)

def SFH309(ref, at, footprint="LED_THT:LED_D3.0mm_Clear"):
    base = snap(at)
    g.add_component("Sensor_Optical", "SFH309", ref, "SFH309", base, {"1": "", "2": ""}, footprint=footprint,
                     datasheet="http://www.osram-os.com/Graphics/XPic2/00101811_0.pdf")
    return pin_at(base, (2.54, 5.08)), pin_at(base, (2.54, -5.08))  # C (collector), E (emitter)

def QN_BSS138(ref, at, footprint="Package_TO_SOT_SMD:SOT-23"):
    # Same extends-skips-ERC issue as SFH4550: BSS138 extends Q_NMOS_GSD.
    # Instantiate Q_NMOS_GSD directly, record BSS138 in Value.
    base = snap(at)
    g.add_component("Transistor_FET", "Q_NMOS_GSD", ref,
                     "BSS138 (real part; Q_NMOS_GSD base symbol used so ERC checks pins)",
                     base, {"1": "", "2": "", "3": ""}, footprint=footprint,
                     datasheet="https://www.onsemi.com/pub/Collateral/BSS138-D.PDF")
    return pin_at(base, (-5.08, 0)), pin_at(base, (2.54, -5.08)), pin_at(base, (2.54, 5.08))  # G, S, D

def SWPUSH(ref, at, footprint="Button_Switch_THT:SW_PUSH_6mm"):
    base = snap(at)
    g.add_component("Switch", "SW_Push", ref, "SW_Push", base, {"1": "", "2": ""}, footprint=footprint)
    return pin_at(base, (-5.08, 0)), pin_at(base, (5.08, 0))

HEF4067_PINS = {
    "Z": (-12.7, 12.7), "Y7": (12.7, 0), "Y6": (12.7, 2.54), "Y5": (12.7, 5.08),
    "Y4": (12.7, 7.62), "Y3": (12.7, 10.16), "Y2": (12.7, 12.7), "Y1": (12.7, 15.24),
    "Y0": (12.7, 17.78), "A0": (-12.7, 2.54), "A1": (-12.7, 0), "VSS": (0, -27.94),
    "A3": (-12.7, -5.08), "A2": (-12.7, -2.54), "E": (-12.7, -15.24), "Y15": (12.7, -20.32),
    "Y14": (12.7, -17.78), "Y13": (12.7, -15.24), "Y12": (12.7, -12.7), "Y11": (12.7, -10.16),
    "Y10": (12.7, -7.62), "Y9": (12.7, -5.08), "Y8": (12.7, -2.54), "VDD": (0, 25.4),
}

def HEF4067(ref, at, footprint="Package_SO:SOIC-24W_7.5x15.4mm_P1.27mm"):
    base = snap(at)
    g.add_component("Analog_Switch", "HEF4067BT", ref, "HEF4067BT", base,
                     {str(n): "" for n in range(1, 25)}, footprint=footprint,
                     datasheet="https://assets.nexperia.com/documents/data-sheet/HEF4067B.pdf")
    return {name: pin_at(base, off) for name, off in HEF4067_PINS.items()}

TB6612_PINS = {
    "AO1": (15.24, 10.16), "PGND1": (2.54, -25.4), "AO2": (15.24, 5.08),
    "BO2": (15.24, -7.62), "PGND2": (7.62, -25.4), "BO1": (15.24, -2.54),
    "VM2": (5.08, 25.4), "VM3": (7.62, 25.4), "PWMB": (-15.24, 2.54),
    "BIN2": (-15.24, -10.16), "BIN1": (-15.24, -7.62), "GND": (-7.62, -25.4),
    "STBY": (-15.24, 10.16), "VCC": (-7.62, 25.4), "AIN1": (-15.24, -2.54),
    "AIN2": (-15.24, -5.08), "PWMA": (-15.24, 5.08), "VM1": (2.54, 25.4),
}

def TB6612(ref, at, footprint="Package_SO:SSOP-24_5.3x8.2mm_P0.65mm"):
    base = snap(at)
    g.add_component("Driver_Motor", "TB6612FNG", ref, "TB6612FNG", base,
                     {str(n): "" for n in range(1, 25)}, footprint=footprint,
                     datasheet="https://toshiba.semicon-storage.com/us/product/linear/motordriver/detail.TB6612FNG.html")
    return {name: pin_at(base, off) for name, off in TB6612_PINS.items()}

ESP32_PINS = {
    "GND": (0, -30.48), "3V3": (0, 30.48), "IO0": (-15.24, 20.32), "IO1": (-15.24, 17.78),
    "IO2": (-15.24, 15.24), "IO3": (-15.24, 12.7), "IO4": (-15.24, 10.16), "IO5": (-15.24, 7.62),
    "IO6": (-15.24, 5.08), "IO7": (-15.24, 2.54), "IO8": (-15.24, 0), "IO9": (-15.24, -2.54),
    "IO10": (-15.24, -5.08), "IO11": (-15.24, -7.62), "IO12": (-15.24, -10.16), "IO13": (-15.24, -12.7),
    "IO14": (-15.24, -15.24), "IO15": (-15.24, -17.78), "IO16": (-15.24, -20.32), "IO17": (-15.24, -22.86),
    "IO18": (-15.24, -25.4), "USB_D-": (15.24, 17.78), "USB_D+": (15.24, 15.24), "IO21": (15.24, 12.7),
    "IO26": (15.24, 10.16), "IO47": (15.24, -22.86), "IO33": (15.24, 7.62), "IO34": (15.24, 5.08),
    "IO48": (15.24, -25.4), "IO35": (15.24, 2.54), "IO36": (15.24, 0), "IO37": (15.24, -2.54),
    "IO38": (15.24, -5.08), "IO39": (15.24, -7.62), "IO40": (15.24, -10.16), "IO41": (15.24, -12.7),
    "IO42": (15.24, -15.24), "TXD0": (15.24, 25.4), "RXD0": (15.24, 22.86), "IO45": (15.24, -17.78),
    "IO46": (15.24, -20.32), "EN": (-15.24, 25.4),
}

def ESP32(ref, at, footprint="RF_Module:ESP32-S2-MINI-1"):
    # Footprint name genuinely says S2 in the stock KiCad library -- the S3-MINI-1
    # module is mechanically/pad compatible with the S2-MINI-1 footprint, this is
    # the library's own documented footprint assignment, not a typo introduced here.
    base = snap(at)
    g.add_component("RF_Module", "ESP32-S3-MINI-1", ref, "ESP32-S3-MINI-1", base,
                     {str(n): "" for n in range(1, 66)}, footprint=footprint,
                     datasheet="https://www.espressif.com/sites/default/files/documentation/esp32-s3-mini-1_mini-1u_datasheet_en.pdf")
    return {name: pin_at(base, off) for name, off in ESP32_PINS.items()}

def PWR(sym, at):
    g.add_power_symbol(sym, at)

def RAIL(net, pin_pos, rotation=0):
    g.add_label(net, pin_pos, rotation=rotation)

def NC(at):
    g.add_no_connect(at)

def TXT(t, at, size=2.5):
    g.add_text(t, at, size=size)

_lane_ctr = [0]
def WIRE(p1, p2):
    # NOT a plain g.connect() call -- discovered the hard way (see PROJECT_NOTES.md
    # fact #9 and its 2026-07-11-later addendum) that g.connect()'s automatic midpoint
    # bend is only collision-safe when nothing ELSE routes between roughly the same
    # two X columns. This schematic has many parallel same-column-to-same-column
    # wires (motor outputs -> connector, encoder pull-ups -> connector, ESP32
    # support resistors -> IC pins) where two independent g.connect() calls compute
    # the IDENTICAL snapped midpoint X, so their vertical bend segments overlap and
    # silently short two unrelated nets together -- confirmed happening for real
    # (AO2/BO2 shorted, and separately EN/IO0 shorted) before this fix. Every
    # Z-routed wire here gets a small unique offset (cycling so it can never grow
    # large enough to cross into a neighbouring section) so no two bends can land
    # on the same X.
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 or y1 == y2:
        g.add_wire(p1, p2)
        return
    _lane_ctr[0] = (_lane_ctr[0] + 1) % 12
    midx = snap(((x1 + x2) / 2 + _lane_ctr[0] * 3.81, 0))[0]
    c1 = (midx, y1)
    c2 = (midx, y2)
    g.add_wire(p1, c1)
    g.add_wire(c1, c2)
    g.add_wire(c2, p2)

# Reference-designator counters, seeded past everything already used in the
# Power/MCU sections (R1-R5, C1-C8, J1-J4 + J8 (both hardcoded, MCU's CN3/CN4
# headers), Q1, U1, F1, L1) so new parts never collide. J8 is deliberately
# skipped by the "J" counter below (still seeded at 4, so ref("J") produces
# J5, J6, J7, ... -- never reaching J8) since it's assigned directly above.
_ctr = {"R": 5, "C": 8, "Q": 1, "D": 0, "J": 4, "U": 1, "SW": 0}
def ref(prefix):
    _ctr[prefix] = _ctr.get(prefix, 0) + 1
    return f"{prefix}{_ctr[prefix]}"

# ---------------------------------------------------------------------------
# POWER SECTION -- unchanged from build_power_mcu.py, battery input chain y=150
# ---------------------------------------------------------------------------
TXT("POWER", (10, 190), size=5)

j1p1, j1p2 = CONN2("J1", "BATT_IN_2S", (20, 150), footprint="Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical")
RAIL("GND", j1p2, rotation=180)
PWR("PWR_FLAG", j1p2)

j2p1, j2p2 = CONN2("J2", "EXT_SWITCH", (55, 150),
                    footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
WIRE(j1p1, j2p1)

f1p1, f1p2 = FUSE("F1", "3A_resettable", (90, 150))
WIRE(j2p2, f1p1)

# Reverse-polarity protection P-MOSFET. Orientation matters and is easy to
# get backwards (the first revision did): battery side must connect to the
# DRAIN and the load rail to the SOURCE, gate pulled to GND. At power-up the
# body diode (anode=drain, cathode=source on a P-FET) conducts battery ->
# load, the gate then sits ~Vbatt below the source and the channel turns on,
# shorting out the diode drop. With the battery REVERSED, the body diode is
# reverse-biased and Vgs is positive, so both conduction paths block. The
# original battery->source wiring would have conducted a reversed battery
# straight through the body diode -- no protection at all.
qD, qG, qS = QPMOS("Q1", "Q_PMOS (e.g. DMP2035U-7)", (125, 150))
WIRE(f1p2, qD)

r1p1, r1p2 = R("R1", "100k", (125, 115))
WIRE(qG, r1p1)
RAIL("GND", r1p2, rotation=270)

RAIL("VM_BATT", qS, rotation=90)
PWR("PWR_FLAG", qS)

c1p1, c1p2 = C("C1", "100uF", (155, 150), footprint="Capacitor_SMD:C_1210_3225Metric")
RAIL("VM_BATT", c1p1, rotation=90)
RAIL("GND", c1p2, rotation=270)

c2p1, c2p2 = C("C2", "100nF", (175, 150))
RAIL("VM_BATT", c2p1, rotation=90)
RAIL("GND", c2p2, rotation=270)

c4p1, c4p2 = C("C4", "10uF", (210, 150))
RAIL("VM_BATT", c4p1, rotation=90)
RAIL("GND", c4p2, rotation=270)

U1_BASE = snap((240, 150))
g.add_component("Regulator_Switching", "AP63200WU", "U1",
                 "AP63203WU (fixed 3.3V; symbol is pin-compatible AP63200WU base)", U1_BASE,
                 {"1": "", "2": "", "3": "", "4": "", "5": "", "6": ""},
                 footprint="Package_TO_SOT_SMD:TSOT-23-6",
                 datasheet="https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf")
u1_fb  = pin_at(U1_BASE, (10.16, -2.54))
u1_en  = pin_at(U1_BASE, (-10.16, -2.54))
u1_in  = pin_at(U1_BASE, (-10.16, 2.54))
u1_gnd = pin_at(U1_BASE, (0, -7.62))
u1_sw  = pin_at(U1_BASE, (10.16, 2.54))
u1_bst = pin_at(U1_BASE, (10.16, 0))

RAIL("VM_BATT", u1_en, rotation=180)
RAIL("VM_BATT", u1_in, rotation=180)
RAIL("GND", u1_gnd, rotation=270)
RAIL("PLUS3V3", u1_fb, rotation=0)
PWR("PWR_FLAG", u1_fb)

bst_p1, bst_p2 = L("L1", "3.3uH", (275, 152.54))
WIRE(u1_sw, bst_p1)
c3p1, c3p2 = C("C3", "100nF", (260, 130))
WIRE(u1_bst, c3p1)
WIRE(c3p2, u1_sw)

c5p1, c5p2 = C("C5", "22uF", (300, 152.54))
WIRE(bst_p2, c5p1)
RAIL("PLUS3V3", c5p1, rotation=90)
RAIL("GND", c5p2, rotation=270)

TXT("+3V3 is the single regulated logic rail: the ESP32 dev board, mux logic, encoder VCC,\nphototransistor pull-ups, and IR LED driver current all come from here (not raw VM_BATT).",
    (200, 100), size=2.2)

j3p1, j3p2, j3p3 = CONN3("J3", "BATT_BALANCE_2S", (20, 60))
RAIL("GND", j3p3, rotation=180)

r2p1, r2p2 = R("R2", "10k", (60, 65))
WIRE(j3p2, r2p1)
r3p1, r3p2 = R("R3", "22k", (60, 40))
WIRE(r2p2, r3p1)
RAIL("GND", r3p2, rotation=270)
c6p1, c6p2 = C("C6", "100nF", (80, 52))
WIRE(r2p2, c6p1)
RAIL("GND", c6p2, rotation=270)
RAIL("VBAT_CELL1_SENSE", r2p2, rotation=0)

r4p1, r4p2 = R("R4", "10k", (110, 65))
WIRE(j3p1, r4p1)
r5p1, r5p2 = R("R5", "6.2k", (110, 40))
WIRE(r4p2, r5p1)
RAIL("GND", r5p2, rotation=270)
c7p1, c7p2 = C("C7", "100nF", (130, 52))
WIRE(r4p2, c7p1)
RAIL("GND", c7p2, rotation=270)
RAIL("VBAT_PACK_SENSE", r4p2, rotation=0)

TXT("VBAT_CELL1_SENSE = cell1 voltage (0-4.2V) scaled to <=2.9V.\nVBAT_PACK_SENSE = full pack voltage (0-8.4V) scaled to <=3.3V.\nFirmware computes cell2 = pack - cell1. Both wired to ESP32 ADC pins A2/A1\n(VBAT_PACK_SENSE/VBAT_CELL1_SENSE) -- see GPIO allocation table in PROJECT_NOTES.md.",
    (20, 20), size=2.2)

# ---------------------------------------------------------------------------
# (MCU SECTION REMOVED 2026-07-13 -- STM32 dropped; the ESP32 in the CONTROLLER
#  section below is now the sole controller. All former STM32 nets are sourced
#  there instead. See PROJECT_NOTES.md.)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# MOTOR DRIVER (SOCKETED BREAKOUT) + ENCODERS SECTION
# ---------------------------------------------------------------------------
# User decision (2026-07-12): the TB6612FNG goes on a SOCKETED breakout board
# (e.g. SparkFun ROB-14451 / Pololu carrier), not a bare SSOP-24 SMD chip --
# plugged into female headers on this carrier PCB, same modular philosophy as
# the socketed STM32 and ESP32 boards. Modeled here as TWO 1x8 female-socket
# rows (J10 control, J11 power+outputs) with FUNCTIONAL pin labels. The exact
# pin order and the spacing between the two rows VARIES by breakout vendor
# (SparkFun and Pololu differ) -- treat this footprint as the reference
# arrangement and VERIFY/adjust the header spacing against your actual board
# before ordering the PCB (same class of assembly-time check as the motor
# connector pinout). The breakout carries its own VM/VCC decoupling, so no
# on-carrier decoupling caps are placed here (unlike the bare-chip version).
TXT("MOTOR DRIVER (socketed TB6612 breakout) + ENCODERS  --  2x N20-with-encoder motors", (10, 230), size=5)

# J10 = control-side header (ESP32 -> driver logic inputs)
J10_MAP = ["STBY", "PWMA", "AIN1", "AIN2", "PWMB", "BIN1", "BIN2", "GND"]
j10 = CONN_COL("J10", "TB6612_BREAKOUT_CTRL", (95, 320), 8,
               footprint="Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical")
for pos, net in zip(j10, J10_MAP):
    if net == "GND":
        PWR("GND", pos)
    else:
        RAIL(net, pos, rotation=180)

# J11 = power + motor-output header
J11_MAP = ["VM_BATT", "PLUS3V3", "GND", "MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N", "GND"]
j11 = CONN_COL("J11", "TB6612_BREAKOUT_PWR_OUT", (120, 320), 8,
               footprint="Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical")
for pos, net in zip(j11, J11_MAP):
    if net == "GND":
        PWR("GND", pos)
    else:
        RAIL(net, pos, rotation=0)

TXT("Breakout logic inputs: STBY, AIN1/AIN2, BIN1/BIN2 are plain ESP32 GPIO; PWMA/PWMB are\nESP32 LEDC PWM outputs (firmware configures PWM). VM=raw battery, VCC=+3V3 logic, GND common.\nAO1/AO2 -> motor A (MOTA_P/N), BO1/BO2 -> motor B (MOTB_P/N). The breakout's own board\ncarries VM/VCC decoupling. VERIFY the breakout's real pin order + row spacing before fab.",
    (10, 258), size=2.0)

# Motor A connector: M+/M- come from the breakout outputs (MOTA_P/N), plus
# encoder VCC/GND/A/B with defensive pull-ups.
jA = CONN6("J5", "MOTOR_A_N20_ENCODER", (200, 330))
RAIL("MOTA_P", jA[0], rotation=0)
RAIL("MOTA_N", jA[1], rotation=0)
RAIL("PLUS3V3", jA[2], rotation=0)
RAIL("GND", jA[3], rotation=0)
rea1, rea2 = R("R6", "10k", (220, 320))
WIRE(rea1, jA[4])
RAIL("PLUS3V3", rea2, rotation=90)
RAIL("ENC1_A", jA[4], rotation=0)
reb1, reb2 = R("R7", "10k", (220, 300))
WIRE(reb1, jA[5])
RAIL("PLUS3V3", reb2, rotation=90)
RAIL("ENC1_B", jA[5], rotation=0)

# Motor B connector
jB = CONN6("J6", "MOTOR_B_N20_ENCODER", (200, 260))
RAIL("MOTB_P", jB[0], rotation=0)
RAIL("MOTB_N", jB[1], rotation=0)
RAIL("PLUS3V3", jB[2], rotation=0)
RAIL("GND", jB[3], rotation=0)
rec1, rec2 = R("R8", "10k", (220, 250))
WIRE(rec1, jB[4])
RAIL("PLUS3V3", rec2, rotation=90)
RAIL("ENC2_A", jB[4], rotation=0)
red1, red2 = R("R9", "10k", (220, 230))
WIRE(red1, jB[5])
RAIL("PLUS3V3", red2, rotation=90)
RAIL("ENC2_B", jB[5], rotation=0)

TXT("10k pull-ups on all 4 encoder lines -- defensive: N20-encoder wire-color-to-\nfunction mapping is unverified for the exact unit ordered (see PROJECT_NOTES.md),\nand encoder output stage (open-drain vs push-pull) isn't confirmed either. A pull-up\nis required if open-drain and harmless if push-pull.\nMotor connector pin order is FUNCTIONAL (M+,M-,ENC_VCC,ENC_GND,ENC_A,ENC_B) --\nverify against the real wire-to-pin mapping at assembly time, not assumed here.",
    (10, 400), size=2.0)

# ---------------------------------------------------------------------------
# CONTROLLER -- socketed Arduino Nano ESP32 (ESP32-S3), the SOLE controller
# ---------------------------------------------------------------------------
# User decision (2026-07-13): the STM32 is DROPPED entirely. One ESP32-S3
# (Arduino Nano ESP32) now does all real-time control AND wireless telemetry,
# saving a whole socketed dev-board footprint plus the old UART flash-relay.
# Modeled with the REAL KiCad footprint Module:Arduino_Nano (true ~18x45mm
# board outline/courtyard) driven from ONE 30-pin symbol (Conn_02x15_Odd_Even),
# whose pin numbers map 1:1 to the footprint pads. Pad->function mapping is
# locked against the footprint's USB silk marker at (7.62, 35.56): footprint
# pads 1-15 = analog row VIN..D13, pads 16-30 = digital row D12..D1 (identical
# ordering to KiCad's Arduino Nano reference, which the old STM32 rows were
# already verified against).
#
# The control NET NAMES are unchanged from the STM32 design (STBY, PWMA, ENC1_A,
# MUX_S0 ...), so every downstream consumer (TB6612 header J10/J11, motor
# connectors J5/J6, muxes U4/U5, button SW1, battery dividers) is untouched --
# only the pin that SOURCES each net moved here. ESP32 ADC inputs must be real
# ADC pins, so the 3 analog nets (MUX_SENSE + both battery senses) sit on
# A0/A1/A2; everything else is plain GPIO (LEDC PWM works on any pin).
TXT("CONTROLLER  --  socketed Arduino Nano ESP32 (ESP32-S3): control + sensors + telemetry", (300, 230), size=5)

A1_MAP = {
    # analog row: footprint pads 1..15 = VIN,GND,RST,5V,A7,A6,A5,A4,A3,A2,A1,A0,AREF,3V3,D13
    1:  None,               # VIN   -- NC (board powered via 3V3; never back-feed)
    2:  "GND",              # GND
    3:  None,               # RESET -- NC
    4:  None,               # 5V    -- NC
    5:  "USER_BTN",         # A7
    6:  "LED_PULSE",        # A6
    7:  "MUX_S3",           # A5
    8:  "MUX_S2",           # A4
    9:  "MUX_S1",           # A3
    10: "VBAT_PACK_SENSE",  # A2  (ADC)
    11: "VBAT_CELL1_SENSE", # A1  (ADC)
    12: "MUX_SENSE",        # A0  (ADC)
    13: None,               # AREF -- NC
    14: "PLUS3V3",          # 3V3 -- powers the board from our regulated rail
    15: "MUX_S0",           # D13
    # digital row: footprint pads 16..30 = D12,D11,D10,D9,D8,D7,D6,D5,D4,D3,D2,GND,RST,D0,D1
    16: "ENC1_A",           # D12
    17: "ENC1_B",           # D11
    18: "ENC2_A",           # D10
    19: "ENC2_B",           # D9
    20: "PWMA",             # D8
    21: "PWMB",             # D7
    22: "AIN1",             # D6
    23: "AIN2",             # D5
    24: "BIN1",             # D4
    25: "BIN2",             # D3
    26: "STBY",             # D2
    27: "GND",              # GND
    28: None,               # RESET -- NC
    29: None,               # D0/RX -- NC (free for USB-serial debug)
    30: None,               # D1/TX -- NC
}

def a1_pin(n):
    # Conn_02x15_Odd_Even geometry (verified from the KiCad symbol): odd pins on
    # the left (x=-5.08), even on the right (x=+7.62), rows top->bottom at
    # y = 17.78 - 2.54*row. Pin number == footprint pad number.
    if n % 2 == 1:
        x, row = -5.08, (n - 1) // 2
    else:
        x, row = 7.62, (n - 2) // 2
    return (x, 17.78 - 2.54 * row)

A1_BASE = snap((360, 300))
g.add_component("Connector_Generic", "Conn_02x15_Odd_Even", "A1",
                "Arduino Nano ESP32 (ESP32-S3) -- sole controller, socketed",
                A1_BASE, {str(n): "" for n in range(1, 31)},
                footprint="Module:Arduino_Nano",
                datasheet="https://docs.arduino.cc/hardware/nano-esp32")
for _n in range(1, 31):
    _pos = pin_at(A1_BASE, a1_pin(_n))
    _net = A1_MAP[_n]
    if _net is None:
        NC(_pos)
    elif _net == "GND":
        PWR("GND", _pos)
    else:
        RAIL(_net, _pos, rotation=(180 if _n % 2 == 1 else 0))

# 3V3 decoupling at the controller (kept as C8 from the old MCU section).
c8p1, c8p2 = C("C8", "100nF", (A1_BASE[0] + 32, A1_BASE[1] + 12))
RAIL("PLUS3V3", c8p1, rotation=90)
RAIL("GND", c8p2, rotation=270)

TXT("Single ESP32-S3 runs everything: TB6612 (STBY/PWMA/PWMB/AIN*/BIN*), 4 encoder inputs,\n"
    "the 2x HEF4067 sensor muxes (MUX_S0-S3 select, MUX_SENSE ADC, LED_PULSE), the two\n"
    "battery-sense ADCs, and USER_BTN. Wi-Fi/BLE telemetry is built in; flashed over the\n"
    "board's own USB-C -- no separate programmer or UART relay. The 3 analog nets are on\n"
    "A0-A2 (real ADC pins). The Nano-ESP32 header-to-GPIO map, and which pins are\n"
    "strapping/input-only, must be confirmed against the Arduino Nano ESP32 pinout in\n"
    "firmware -- see PROJECT_NOTES.md.",
    (300, 360), size=2.0)

# ---------------------------------------------------------------------------
# CONNECTORS / DEBUG SECTION
# ---------------------------------------------------------------------------
TXT("CONNECTORS / DEBUG", (600, 230), size=5)

btn1, btn2 = SWPUSH("SW1", (620, 300))
rbtn1, rbtn2 = R("R10", "10k", (640, 300))
WIRE(rbtn2, btn1)
RAIL("PLUS3V3", rbtn1, rotation=90)
RAIL("USER_BTN", btn1, rotation=180)
RAIL("GND", btn2, rotation=0)

TXT("USER_BTN (ESP32 A7) -- active-low start-run button, pulled up to +3V3.\nStandard micromouse UX (arm, then start a run). One of the ESP32 analog-capable\npins; the full net/pin allocation is in PROJECT_NOTES.md.\n\nNo separate debug/programming header on this board: the Arduino Nano ESP32 is\nflashed over its own onboard USB-C, and firmware is updated the same way (or\nover-the-air via Wi-Fi). No BOOT0/SWD/UART-relay hardware is needed now that the\nSTM32 is gone -- the ESP32's native USB handles programming and console.",
    (600, 260), size=2.0)

# ---------------------------------------------------------------------------
# IR SENSOR ARRAY -- 6 wall + 8 line sensors via 2x HEF4067BT mux/demux
# ---------------------------------------------------------------------------
TXT("IR SENSOR ARRAY  --  6 wall + 8 line sensors", (10, 420), size=5)

# Refs from here on are HARDCODED (not via the running ref() counter) so that
# adding/removing parts in the module sections above can never shift the
# sensor reference numbers, which build_pcb.py and gen_connections.py depend
# on (Q2..Q29 / R13..R40 / D1..D14). The sensor loop below re-seeds the Q/R/D
# counters to fixed values to reproduce exactly that numbering.
U4 = HEF4067("U4", (60, 500))   # read-mux: phototransistor commons -> MUX_SENSE (ADC)
U5 = HEF4067("U5", (60, 440))   # write-demux: LED_PULSE -> selected emitter driver

RAIL("PLUS3V3", U4["VDD"], rotation=270)
RAIL("GND", U4["VSS"], rotation=90)
RAIL("GND", U4["E"], rotation=180)   # inhibit tied low -- always enabled
RAIL("MUX_S0", U4["A0"], rotation=180)
RAIL("MUX_S1", U4["A1"], rotation=180)
RAIL("MUX_S2", U4["A2"], rotation=180)
RAIL("MUX_S3", U4["A3"], rotation=180)
RAIL("MUX_SENSE", U4["Z"], rotation=180)
NC(U4["Y14"])
NC(U4["Y15"])
c11a, c11b = C("C13", "100nF", (30, 470))
WIRE(c11a, U4["VDD"])
RAIL("GND", c11b, rotation=270)

RAIL("PLUS3V3", U5["VDD"], rotation=270)
RAIL("GND", U5["VSS"], rotation=90)
RAIL("GND", U5["E"], rotation=180)
RAIL("MUX_S0", U5["A0"], rotation=180)
RAIL("MUX_S1", U5["A1"], rotation=180)
RAIL("MUX_S2", U5["A2"], rotation=180)
RAIL("MUX_S3", U5["A3"], rotation=180)
RAIL("LED_PULSE", U5["Z"], rotation=180)
NC(U5["Y14"])
NC(U5["Y15"])
c12a, c12b = C("C14", "100nF", (30, 410))
WIRE(c12a, U5["VDD"])
RAIL("GND", c12b, rotation=270)

TXT("2x HEF4067BT 16-ch analog mux/demux, sharing select lines MUX_S0-S3.\nEach sensor: SFH309 phototransistor (collector -> 47k pull-up to +3V3 AND to its\nread-mux channel; emitter -> GND) + SFH4550 IR LED (anode -> current-limit resistor\n-> +3V3; cathode -> BSS138 low-side switch drain; switch source -> GND; switch gate\n-> its write-demux channel). Firmware pulses LED_PULSE while stepping MUX_S0-S3\nthrough one channel at a time (crosstalk avoidance), sampling MUX_SENSE 'bright' then\n'ambient' with the LED off, subtracting -- see PROJECT_NOTES.md IR sensor circuit design.\nCurrent-limit: wall 33R (~50mA pulsed) / line 120R (~15mA, latched-capable), sized for ~3.3V rail, SFH4550 Vf~1.35V typ, allowing\n~0.3-0.5V for the BSS138 switch's on-resistance at 3.3V gate drive (not independently\nverified against the BSS138 datasheet's Vgs=3.3V Rds(on) curve in this session --\ntune at bring-up if dimmer/brighter than expected).",
    (150, 460), size=2.0)

# Re-seed the ref counters so the sensor loop reproduces exactly Q2..Q29,
# R13..R40, D1..D14 regardless of how many parts the module sections above
# used (build_pcb.py and gen_connections.py hardcode these numbers).
_ctr["Q"] = 1
_ctr["R"] = 12
_ctr["D"] = 0

SENSOR_NAMES = ["WALL1", "WALL2", "WALL3", "WALL4", "WALL5", "WALL6",
                "LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8"]
MUX_CHANNELS = [f"Y{i}" for i in range(14)]

SENSOR_X0 = 250
SENSOR_DX = 48
WALL_ROW_Y = 490
LINE_ROW_Y = 560

for i, name in enumerate(SENSOR_NAMES):
    is_wall = i < 6
    row_y = WALL_ROW_Y if is_wall else LINE_ROW_Y
    col = i if is_wall else i - 6
    x = SENSOR_X0 + col * SENSOR_DX
    ch = MUX_CHANNELS[i]

    # WALL sensors (i<6): THT parts, top side, leads bent to aim at walls.
    # LINE sensors (i>=6): SMD parts, mounted on the BOTTOM face looking down
    # at the floor (user decision 2026-07-12; QTR-8A-style discrete SMD
    # emitter+phototransistor, ~3mm ride height). Real SMD part choices from
    # research: emitter = Osram SFH4045N (940nm, 2-SMD); receiver = Osram
    # SFH320FA (PLCC-2 phototransistor, IR-suited). Footprints here are
    # practical 2-pad SMD stand-ins (1206 LED + LPT80A phototransistor land
    # pattern) -- confirm against the exact chosen part before fab, same as
    # any footprint on this board.
    if is_wall:
        photo_fp = "LED_THT:LED_D3.0mm_Clear"
        photo_val = "SFH309"
        led_fp = "LED_THT:LED_D5.0mm_IRGrey"
        led_val = "SFH4550 (THT, LD271 base symbol)"
    else:
        # Both optics on a compact 1206 land pattern: the 9.525mm QTR pitch is
        # a hard mechanical constraint, so the phototransistor footprint must
        # stay small (the Osram_LPT80A land pattern is ~11mm wide and would
        # overlap its neighbours at this pitch). A 1206 2-pad SMD pattern fits
        # with margin and suits both the SFH4045N emitter and a small SMD
        # phototransistor like the SFH320FA (PLCC-2) -- confirm the exact land
        # pattern against the chosen phototransistor before fab.
        photo_fp = "LED_SMD:LED_1206_3216Metric"
        photo_val = ("SMD phototransistor 940nm, DAYLIGHT-FILTERED REQUIRED (e.g. Osram SFH320FA "
                     "-- an unfiltered part re-opens optical feedback from the red indicator LEDs)")
        led_fp = "LED_SMD:LED_1206_3216Metric"
        led_val = "SMD IR LED 940nm (e.g. Osram SFH4045N)"

    # receiver + pull-up, tied to the read-mux channel
    rx_c, rx_e = SFH309(ref("Q"), (x, row_y), footprint=photo_fp)
    RAIL("GND", rx_e, rotation=270)
    rp1, rp2 = R(ref("R"), "47k", (x, row_y + 15))
    WIRE(rp2, rx_c)
    RAIL("PLUS3V3", rp1, rotation=90)
    RAIL(f"{name}_SENSE", rx_c, rotation=0)
    RAIL(f"{name}_SENSE", U4[ch], rotation=180 if HEF4067_PINS[ch][0] > 0 else 0)

    # emitter + current-limit resistor + low-side switch, tied to the write-demux channel.
    # Wall: 33R (~50mA pulsed, 60-180mm range). Line: 120R (~15mA) -- low enough
    # for firmware to LATCH all 8 line emitters on continuously in line-follow
    # mode (~120mA total), which is what makes the top-side indicator LEDs live
    # (adversarial review: pulsed emitters leave the node ambient-dominated ~93%
    # of the time; at ~3mm line range 15mA has ample margin, QTR-class boards
    # run continuous at similar currents).
    lr1, lr2 = R(ref("R"), "33" if is_wall else "120", (x + 16, row_y + 15))
    RAIL("PLUS3V3", lr1, rotation=90)
    led_k, led_a = LED_SFH4550(ref("D"), (x + 16, row_y), footprint=led_fp)
    WIRE(lr2, led_a)
    sw_g, sw_s, sw_d = QN_BSS138(ref("Q"), (x + 16, row_y - 15))
    WIRE(led_k, sw_d)
    RAIL("GND", sw_s, rotation=270)
    RAIL(f"{name}_LED", sw_g, rotation=180)
    RAIL(f"{name}_LED", U5[ch], rotation=180 if HEF4067_PINS[ch][0] > 0 else 0)

# ---------------------------------------------------------------------------
# LINE-SENSOR INDICATOR LEDs (user request 2026-07-15): one visible top-side
# LED per line sensor whose brightness tracks the IR receiver ANALOGICALLY.
# Circuit: BSS138 gate tied straight to LINEx_SENSE -- a MOSFET gate draws no
# DC current, so the 47k analog divider feeding the mux/ADC is completely
# unloaded (an NPN follower would have skimmed ~10uA base current = ~0.5V of
# divider error). Drain sinks a visible LED from +3V3 through 1k. More
# reflection -> phototransistor pulls the node LOW -> FET less enhanced ->
# dimmer; over a dark line the node rises -> brighter. So: LED BRIGHT = dark
# line under that sensor, with a true analog transition (BSS138 Vth ~1.3V sits
# mid-range of the 0-3.3V node swing). No firmware involved -- the indicators
# live on the per-sensor nodes UPSTREAM of the mux, so all 8 work continuously.
TXT("LINE-SENSOR INDICATORS  --  8 top-side LEDs, one per line channel", (10, 640), size=5)
TXT("BSS138 gate on each LINEx_SENSE node (zero DC load: gate leakage <=100nA worst-case = ~5mV\non the 47k divider; if one channel ever reads pinned, suspect its Q30-Q37 gate). Drain sinks\na super-red 0603 from +3V3 via 1k (~1.4mA). In practice a THRESHOLD indicator: the BSS138's\n~150-300mV dark-to-full band makes it crisp on/off around ~1.2V -- ideal for reading line\nposition across 8 LEDs at a glance. LED ON = dark line under that sensor.\nFIRMWARE RULE: indicators are only meaningful while the line emitters are LIT -- pulsed\nscanning leaves the node ambient-dominated ~93% of the time. Line emitters are 120R\n(~15mA), sized so line-follow mode can latch all 8 on continuously (~120mA).",
    (10, 655), size=2.0)

IND_ROW_Y = 700
for k in range(1, 9):
    x = SENSOR_X0 + (k - 1) * SENSOR_DX
    ind_g, ind_s, ind_d = QN_BSS138(ref("Q"), (x, IND_ROW_Y))          # Q30..Q37
    RAIL(f"LINE{k}_SENSE", ind_g, rotation=180)
    RAIL("GND", ind_s, rotation=270)
    ir1, ir2 = R(ref("R"), "1k", (x + 16, IND_ROW_Y + 15))             # R41..R48
    RAIL("PLUS3V3", ir1, rotation=90)
    # Same LD271 base symbol trick as the IR emitters (extends-skips-ERC), with
    # the real intended part recorded in Value.
    base = snap((x + 16, IND_ROW_Y))
    g.add_component("LED", "LD271", ref("D"),                          # D15..D22
                     "Indicator LED 0603 super-red AlInGaP, high-efficiency bin REQUIRED at 1.4mA (e.g. Kingbright APT1608SURCK; LD271 base symbol for ERC)",
                     base, {"1": "", "2": ""},
                     footprint="LED_SMD:LED_0603_1608Metric")
    ind_led_k, ind_led_a = pin_at(base, (-5.08, 0)), pin_at(base, (2.54, 0))
    WIRE(ir2, ind_led_a)
    WIRE(ind_led_k, ind_d)

with open(r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_sch", "w", encoding="utf-8", newline="\n") as f:
    f.write(g.render(title="Micromouse PCB"))

print("wrote", len(g.symbol_instances), "components,", len(g.label_instances), "labels,",
      len(g.wires), "wires,", len(g.no_connects), "no-connects,",
      "unique lib symbols:", len(g.lib_symbols_needed))
