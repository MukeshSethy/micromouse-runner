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
    # Rev 4b: CD74HC4067M (HC family) replaces HEF4067BT -- the CD4000-family
    # part is only specified from VDD=3V with kR-class Ron and slow switching
    # at 3.3V (adversarial datasheet review); the HC part is ~70R and fast.
    # Pin geometry verified IDENTICAL to the HEF symbol (pad-for-pad), so the
    # HEF4067_PINS offsets stay valid.
    base = snap(at)
    g.add_component("74xx", "CD74HC4067M", ref, "CD74HC4067M", base,
                     {str(n): "" for n in range(1, 25)}, footprint=footprint,
                     datasheet="https://www.ti.com/lit/ds/symlink/cd74hc4067.pdf")
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
TXT("POWER  --  1S LiPo -> TPS63001 buck-boost -> 3V3", (10, 190), size=5)

# 1S LiPo (3.0-4.2V). A plain buck (rev<=3's AP63203) cannot make 3.3V from a
# cell that sags below ~3.8V, so the regulator is a TPS63001 BUCK-BOOST
# (1.8-5.5V in, fixed 3.3V out, 1.2A -- covers ESP32-S3 WiFi bursts). Motors
# run from the raw protected cell rail (TB6612 VM min 2.5V); order 3V-wound
# N20 motors, a 6V wind at 3.7V gives ~60% speed. Single cell = no balance
# connector and ONE battery divider, tapped DOWNSTREAM of the switch/fuse/FET
# so a stored pack is never drained by the divider (fixes the rev<=3 balance-
# lead storage-drain risk).
j1p1, j1p2 = CONN2("J1", "BATT_IN_1S", (20, 150), footprint="Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical")
RAIL("GND", j1p2, rotation=180)
PWR("PWR_FLAG", j1p2)

j2p1, j2p2 = CONN2("J2", "EXT_SWITCH", (55, 150),
                    footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
WIRE(j1p1, j2p1)

f1p1, f1p2 = FUSE("F1", "2A_resettable", (90, 150))
WIRE(j2p2, f1p1)

# Reverse-polarity P-MOSFET: battery -> DRAIN, load -> SOURCE, gate to GND
# (see PROJECT_NOTES for the body-diode proof). At 1S the gate sees
# -3.0..-4.2V -- use a low-threshold P-FET (DMP2035U: Vgs(th) ~-0.7V, fully
# enhanced by -2.5V).
qD, qG, qS = QPMOS("Q1", "Q_PMOS low-Vth (e.g. DMP2035U-7)", (125, 150))
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

# TPS63001 buck-boost. Instantiated as the TPS63000 BASE symbol (TPS63001
# `extends` it, and extends-symbols silently skip ERC pin checks -- same
# workaround as the AP63203/LD271/BSS138 cases, real part recorded in Value).
# Fixed-3.3V version: FB ties directly to VOUT.
U1_BASE = snap((250, 150))
g.add_component("Regulator_Switching", "TPS63000", "U1",
                 "TPS63001 (fixed 3.3V buck-boost; TPS63000 base symbol so ERC checks pins)",
                 U1_BASE, {str(n): "" for n in range(1, 12)},
                 footprint="Package_SON:Texas_DRC0010J_ThermalVias",
                 datasheet="https://www.ti.com/lit/ds/symlink/tps63001.pdf")
u1_vout = pin_at(U1_BASE, (10.16, 10.16))
u1_l2   = pin_at(U1_BASE, (-10.16, -10.16))
u1_pgnd = pin_at(U1_BASE, (0, -15.24))
u1_l1   = pin_at(U1_BASE, (-10.16, 0))
u1_vin  = pin_at(U1_BASE, (-10.16, 10.16))
u1_en   = pin_at(U1_BASE, (-10.16, 5.08))
u1_ps   = pin_at(U1_BASE, (-10.16, 2.54))
u1_vina = pin_at(U1_BASE, (-10.16, 7.62))
u1_gnd  = pin_at(U1_BASE, (-2.54, -15.24))
u1_fb   = pin_at(U1_BASE, (10.16, 2.54))

RAIL("VM_BATT", u1_vin, rotation=180)
RAIL("VM_BATT", u1_en, rotation=180)     # always-on when battery switched on
RAIL("VM_BATT", u1_vina, rotation=180)   # analog supply sense
RAIL("GND", u1_ps, rotation=180)         # PS/SYNC low = power-save enabled
RAIL("GND", u1_pgnd, rotation=270)
RAIL("GND", u1_gnd, rotation=270)
RAIL("PLUS3V3", u1_vout, rotation=0)
# (no PWR_FLAG here: TPS63000's VOUT pin is already Power-Output typed --
# adding a flag makes ERC flag two power outputs on one net)
WIRE(u1_fb, pin_at(U1_BASE, (10.16, 10.16)))  # FB -> VOUT (fixed-voltage part)

# Buck-boost inductor between L1 and L2 pins (1.5uH per TPS63001 datasheet).
bst_p1, bst_p2 = L("L1", "1.5uH", (222, 130))
WIRE(u1_l1, bst_p1)
WIRE(u1_l2, bst_p2)

c3p1, c3p2 = C("C3", "100nF", (238, 118))   # VINA filter (datasheet 0.1uF)
WIRE(c3p1, u1_vina)
RAIL("GND", c3p2, rotation=270)

c5p1, c5p2 = C("C5", "22uF", (285, 150))
RAIL("PLUS3V3", c5p1, rotation=90)
RAIL("GND", c5p2, rotation=270)

TXT("+3V3 is the single regulated logic rail: the ESP32-S3 module, mux logic, encoder VCC,\nphototransistor pull-ups, indicator drivers and IR LED current all come from here.",
    (200, 100), size=2.2)

# Battery voltage divider: VM_BATT (protected rail) -> R2/R3 -> VBAT_SENSE.
# 10k/22k scales 4.2V max to 2.89V (inside the 3.3V ADC range). C6 low-passes
# motor PWM noise. Tapped downstream of the switch so storage packs see no load.
r2p1, r2p2 = R("R2", "22k", (60, 65))
RAIL("VM_BATT", r2p1, rotation=90)
r3p1, r3p2 = R("R3", "33k", (60, 40))
WIRE(r2p2, r3p1)
RAIL("GND", r3p2, rotation=270)
c6p1, c6p2 = C("C6", "100nF", (80, 52))
WIRE(r2p2, c6p1)
RAIL("GND", c6p2, rotation=270)
RAIL("VBAT_SENSE", r2p2, rotation=0)

TXT("VBAT_SENSE = cell voltage (0-4.2V) scaled to <=2.52V by 22k/33k (the S3 ADC calibrated\nrange tops at ~2.9V with worst error near the top -- keep headroom). Into ADC1 IO8.\nFirmware low-battery cutoff at 3.0V/cell. Single 1S cell: no balance lead.",
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
# CONTROLLER -- ESP32-S3-WROOM-1 SMD module (U3), the SOLE controller
# ---------------------------------------------------------------------------
# User decisions (2026-07-15): bare ESP32-S3-WROOM-1 module -- the only ESP32
# in stock KiCad with BOTH an exact footprint AND a shipped 3D STEP model;
# dual-core LX7 @ 240MHz + FreeRTOS (speed/RTOS requirement); 10 ADC1 channels
# so all 6 wall sensors read DIRECTLY (mux only for the line array); plus a
# rear USB-C for flashing, a JTAG header for debugging, and 3 user buttons.
#
# LOCKED PIN MAP (ADC1 = IO1..IO10 is the only WiFi-safe ADC):
#   IO1-6  WALL1-6_SENSE   IO7 MUX_SENSE   IO8 VBAT_SENSE
#   IO9/10 AIN1/AIN2 (ADC-capable pins spent as motor GPIOs)
#   IO11-13 MUX_S0-2   IO14 LINE_EMIT   IO15-17 WALL_EMIT_FRONT/DIAG/SIDE
#   IO18/21 PWMA/PWMB (LEDC)   IO38 BIN1
#   IO45 BIN2 / IO46 STBY -- STRAPPING pins used as motor outputs: safe ONLY
#     because they idle LOW and carry no pull-ups (IO45 high at reset would
#     select 1.8V flash supply = brick; never add a pull-up to these nets)
#   IO39-42 JTAG (MTCK/MTDO/MTDI/MTMS) -> J8, dedicated for debugging
#   IO43(TXD0)/IO44(RXD0) ENC2_B/ENC2_A   IO47/48 ENC1_A/B  (console = USB-CDC)
#   IO0 BTN1/BOOT   IO35/36 BTN2/BTN3 (internal pull-ups; on octal-PSRAM -R8
#     modules IO35-37 are unavailable -> buttons 2/3 lost, control unaffected)
#   IO37 spare (NC)
TXT("CONTROLLER  --  ESP32-S3-WROOM-1 (dual-core 240MHz, FreeRTOS, WiFi): control + telemetry", (300, 230), size=5)

WROOM_PADS = {
    "1": ("GND", (0, -27.94)),    "2": ("3V3", (0, 27.94)),     "3": ("EN", (-15.24, 22.86)),
    "4": ("IO4", (-15.24, 7.62)), "5": ("IO5", (-15.24, 5.08)), "6": ("IO6", (-15.24, 2.54)),
    "7": ("IO7", (-15.24, 0)),    "8": ("IO15", (-15.24, -20.32)), "9": ("IO16", (-15.24, -22.86)),
    "10": ("IO17", (15.24, 17.78)), "11": ("IO18", (15.24, 15.24)), "12": ("IO8", (-15.24, -2.54)),
    "13": ("USB_D-", (15.24, 12.7)), "14": ("USB_D+", (15.24, 10.16)), "15": ("IO3", (-15.24, 10.16)),
    "16": ("IO46", (15.24, -17.78)), "17": ("IO9", (-15.24, -5.08)), "18": ("IO10", (-15.24, -7.62)),
    "19": ("IO11", (-15.24, -10.16)), "20": ("IO12", (-15.24, -12.7)), "21": ("IO13", (-15.24, -15.24)),
    "22": ("IO14", (-15.24, -17.78)), "23": ("IO21", (15.24, 7.62)), "24": ("IO47", (15.24, -20.32)),
    "25": ("IO48", (15.24, -22.86)), "26": ("IO45", (15.24, -15.24)), "27": ("IO0", (-15.24, 17.78)),
    "28": ("IO35", (15.24, 5.08)), "29": ("IO36", (15.24, 2.54)), "30": ("IO37", (15.24, 0)),
    "31": ("IO38", (15.24, -2.54)), "32": ("IO39", (15.24, -5.08)), "33": ("IO40", (15.24, -7.62)),
    "34": ("IO41", (15.24, -10.16)), "35": ("IO42", (15.24, -12.7)), "36": ("RXD0", (15.24, 20.32)),
    "37": ("TXD0", (15.24, 22.86)), "38": ("IO2", (-15.24, 12.7)), "39": ("IO1", (-15.24, 15.24)),
    "40": ("GND", (0, -27.94)),   "41": ("GND", (0, -27.94)),
}
U3_NET = {  # module pad -> net (None = explicit no-connect)
    "2": "PLUS3V3", "3": "ESP_EN",
    "39": "WALL1_SENSE", "38": "WALL2_SENSE", "15": "WALL3_SENSE",       # IO1-3
    "4": "WALL4_SENSE", "5": "WALL5_SENSE", "6": "WALL6_SENSE",          # IO4-6
    "7": "MUX_SENSE", "12": "VBAT_SENSE",                                # IO7/IO8
    "17": "AIN1", "18": "AIN2",                                          # IO9/IO10
    "19": "MUX_S0", "20": "MUX_S1", "21": "MUX_S2",                      # IO11-13
    "22": "LINE_EMIT",                                                   # IO14
    "8": "WALL_EMIT_FRONT", "9": "WALL_EMIT_DIAG", "10": "WALL_EMIT_SIDE",  # IO15-17
    "11": "PWMA", "23": "PWMB",                                          # IO18/IO21
    "28": "USER_BTN2", "29": "USER_BTN3", "30": None,                    # IO35/36, IO37 spare
    "31": "BIN1",                                                        # IO38
    "32": "JTAG_TCK", "33": "JTAG_TDO", "34": "JTAG_TDI", "35": "JTAG_TMS",  # IO39-42
    "36": "ENC2_A_S3", "37": "ENC2_B_S3",   # IO44(RXD0)/IO43(TXD0) via 1k guards
    "26": "BIN2", "16": "STBY",                                          # IO45/IO46 straps (idle-low outputs)
    "24": "ENC1_A", "25": "ENC1_B",                                      # IO47/IO48
    "27": "USER_BTN",                                                    # IO0 (BOOT strap)
    "13": "USB_DM", "14": "USB_DP",
    "1": "GND", "40": "GND", "41": "GND",
}
U3_BASE = snap((360, 300))
g.add_component("RF_Module", "ESP32-S3-WROOM-1", "U3",
                "ESP32-S3-WROOM-1-N16 (non-R8: octal-PSRAM variants lose IO35-37 = buttons 2/3)",
                U3_BASE, {str(n): "" for n in range(1, 42)},
                footprint="RF_Module:ESP32-S3-WROOM-1",
                datasheet="https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf")
_done_pos = set()
for _pad, (_nm, _off) in WROOM_PADS.items():
    _pos = pin_at(U3_BASE, _off)
    if _pos in _done_pos:
        continue                       # stacked GND pins (1/40/41) share one position
    _done_pos.add(_pos)
    _net = U3_NET[_pad]
    if _net is None:
        NC(_pos)
    elif _net == "GND":
        PWR("GND", _pos)
    else:
        RAIL(_net, _pos, rotation=(180 if _off[0] < 0 else 0))

# EN reset circuit per Espressif hardware design guidelines: 10k pull-up +
# 1uF RC delay + reset button (SW2). Hold SW1 (IO0) + tap SW2 = ROM download.
r11a, r11b = R("R11", "10k", (415, 258))
RAIL("PLUS3V3", r11a, rotation=90)
RAIL("ESP_EN", r11b, rotation=270)
c9a, c9b = C("C9", "1uF", (430, 258))
RAIL("ESP_EN", c9a, rotation=90)
RAIL("GND", c9b, rotation=270)
sw2a, sw2b = SWPUSH("SW2", (447, 265))
RAIL("ESP_EN", sw2a, rotation=180)
RAIL("GND", sw2b, rotation=0)

# Module decoupling: 10uF bulk + 100nF.
c10a, c10b = C("C10", "10uF", (415, 235))
RAIL("PLUS3V3", c10a, rotation=90)
RAIL("GND", c10b, rotation=270)
c8p1, c8p2 = C("C8", "100nF", (430, 235))
RAIL("PLUS3V3", c8p1, rotation=90)
RAIL("GND", c8p2, rotation=270)

# USB-C receptacle (16P, GCT USB4105 class) at the REAR of the robot (user
# requirement) for flashing + CDC console via the S3's native USB. CC1/CC2 get
# 5.1k pull-downs (UFP). VBUS deliberately NOT connected: the board is battery
# powered; back-feeding 3V3 from 5V VBUS would need a regulator + power mux.
# Flash with the battery connected and switched on.
J7_BASE = snap((480, 300))
g.add_component("Connector", "USB_C_Receptacle_USB2.0_16P", "J7",
                "USB-C rear (GCT USB4105; VBUS unused -- battery powers the board)",
                J7_BASE, {k: "" for k in ["A1","A4","A5","A6","A7","A8","A9","A12",
                                           "B1","B4","B5","B6","B7","B8","B9","B12","SH"]},
                footprint="Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
                datasheet="https://gct.co/files/drawings/usb4105.pdf")
NC(pin_at(J7_BASE, (15.24, 15.24)))            # VBUS stack (A4/A9/B4/B9)
NC(pin_at(J7_BASE, (15.24, -12.7)))            # SBU1
NC(pin_at(J7_BASE, (15.24, -15.24)))           # SBU2
rcc1a, rcc1b = R("R12", "5.1k", (508, 270))
WIRE(rcc1a, pin_at(J7_BASE, (15.24, 10.16)))   # CC1
RAIL("GND", rcc1b, rotation=270)
rcc2a, rcc2b = R("R56", "5.1k", (518, 264))
WIRE(rcc2a, pin_at(J7_BASE, (15.24, 7.62)))    # CC2
RAIL("GND", rcc2b, rotation=270)
RAIL("USB_DP_C", pin_at(J7_BASE, (15.24, -2.54)), rotation=0)   # D+ (A6)
RAIL("USB_DP_C", pin_at(J7_BASE, (15.24, -5.08)), rotation=0)   # D+ (B6)
RAIL("USB_DM_C", pin_at(J7_BASE, (15.24, 2.54)), rotation=0)    # D- (A7)
RAIL("USB_DM_C", pin_at(J7_BASE, (15.24, 0)), rotation=0)       # D- (B7)
PWR("GND", pin_at(J7_BASE, (0, -22.86)))                      # GND stack
RAIL("GND", pin_at(J7_BASE, (-7.62, -22.86)), rotation=180)   # SHIELD


# --- Verification-driven guard components (adversarial review 2026-07-15) ---
# ENC2 series guards: IO43=U0TXD is DRIVEN by the ROM at every boot (prints
# boot messages) while a push-pull encoder can drive the same node -- 1k in
# series bounds the contention current; PCNT inputs are high-Z. Firmware must
# set the console to USB-Serial-JTAG so UART0 is never re-enabled.
re2a1, re2a2 = R("R57", "1k", (415, 330))
RAIL("ENC2_A", re2a1, rotation=90)
RAIL("ENC2_A_S3", re2a2, rotation=270)
re2b1, re2b2 = R("R58", "1k", (430, 330))
RAIL("ENC2_B", re2b1, rotation=90)
RAIL("ENC2_B_S3", re2b2, rotation=270)

# Emitter-gate pull-downs: IO14-17 float from power-on until app init (no
# internal pulls at reset) -- 100k holds every emitter bank OFF through the
# boot/brownout window.
for _ref, _net, _gx in (("R61", "LINE_EMIT", 445), ("R62", "WALL_EMIT_FRONT", 455),
                         ("R63", "WALL_EMIT_DIAG", 465), ("R64", "WALL_EMIT_SIDE", 475)):
    _p1, _p2 = R(_ref, "100k", (_gx, 330))
    RAIL(_net, _p1, rotation=90)
    RAIL("GND", _p2, rotation=270)

# Strap insurance: IO45 (BIN2) high at reset would switch VDD_SPI to 1.8V and
# brick the boot; with the TB6612 breakout UNPLUGGED its trace is a floating
# stub on a strap. 10k pull-downs guarantee both straps read low at reset and
# double as motor-safety (STBY held low = driver disabled until firmware acts).
rs45a, rs45b = R("R65", "10k", (490, 330))
RAIL("BIN2", rs45a, rotation=90)
RAIL("GND", rs45b, rotation=270)
rs46a, rs46b = R("R66", "10k", (505, 330))
RAIL("STBY", rs46a, rotation=90)
RAIL("GND", rs46b, rotation=270)

# USB ESD array (exposed user-handled connector on a robot) + 22R series
# resistors near the module (Espressif schematic checklist). USBLC6 rail pin
# clamps to +3V3 (VBUS is unused on this board).
U6_BASE = snap((520, 300))
# Base symbol USBLC6-2P6 instantiated directly (USBLC6-2SC6 `extends` it and
# extends-symbols skip ERC pin checks -- the standing workaround); real SOT-23-6
# part recorded in Value + footprint.
g.add_component("Power_Protection", "USBLC6-2P6", "U6",
                "USBLC6-2SC6 (SOT-23-6; 2P6 base symbol so ERC checks pins)",
                U6_BASE, {str(n): "" for n in range(1, 7)},
                footprint="Package_TO_SOT_SMD:SOT-23-6",
                datasheet="https://www.st.com/resource/en/datasheet/usblc6-2.pdf")
RAIL("USB_DM_C", pin_at(U6_BASE, (-5.08, 0)), rotation=180)    # I/O1 conn side
RAIL("USB_DP_C", pin_at(U6_BASE, (-5.08, -2.54)), rotation=180)  # I/O2 conn side
RAIL("GND", pin_at(U6_BASE, (0, -7.62)), rotation=270)
RAIL("PLUS3V3", pin_at(U6_BASE, (0, 5.08)), rotation=90)
ru1a, ru1b = R("R59", "22", (545, 295))
WIRE(ru1a, pin_at(U6_BASE, (5.08, 0)))         # I/O1 module side
RAIL("USB_DM", ru1b, rotation=270)
ru2a, ru2b = R("R60", "22", (555, 289))
WIRE(ru2a, pin_at(U6_BASE, (5.08, -2.54)))     # I/O2 module side
RAIL("USB_DP", ru2b, rotation=270)

# JTAG debug header (J8): 2.54mm 1x6 strip -- a 1.27mm 2x5 is UNROUTABLE at
# this board's 0.3mm no-inter-pin clearance (0.53mm pad gaps; router-proven).
# Order: 3V3, TMS, TCK, TDO, TDI, GND -- jumper-wire friendly to ESP-Prog.
J8_JTAG = ["PLUS3V3", "JTAG_TMS", "JTAG_TCK", "JTAG_TDO", "JTAG_TDI", "GND"]
j8 = CONN_COL("J8", "JTAG_1x6 (3V3,TMS,TCK,TDO,TDI,GND)", (530, 320), 6,
              footprint="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical")
for _pos, _net in zip(j8, J8_JTAG):
    if _net == "GND":
        PWR("GND", _pos)
    else:
        RAIL(_net, _pos, rotation=180)

TXT("ESP32-S3-WROOM-1 on FreeRTOS: 6 wall sensors DIRECT on ADC1 IO1-IO6 (a fired pair is\n"
    "sampled in parallel), line array via U4 (IO7 + IO11-13), battery IO8, TB6612 on\n"
    "IO9/10/18/21/38/45/46 (straps 45/46 = idle-low outputs ONLY -- never add pull-ups),\n"
    "encoders IO43/44/47/48 (PCNT hardware quadrature via GPIO matrix), JTAG on the real\n"
    "JTAG quad IO39-42 -> J8 (ESP-Prog). Buttons: SW1=IO0 (start/BOOT), SW3=IO35, SW4=IO36\n"
    "(internal pull-ups). USB-C (rear) on the native USB pads = flash + console; UART0\n"
    "pins repurposed as encoder inputs. Every analog net sits on ADC1 (IO1-IO8).",
    (300, 368), size=2.0)

# ---------------------------------------------------------------------------
# CONNECTORS / DEBUG SECTION
# ---------------------------------------------------------------------------
TXT("USER INTERFACE  --  3 buttons", (600, 230), size=5)

btn1, btn2 = SWPUSH("SW1", (620, 300))
rbtn1, rbtn2 = R("R10", "10k", (640, 300))
WIRE(rbtn2, btn1)
RAIL("PLUS3V3", rbtn1, rotation=90)
RAIL("USER_BTN", btn1, rotation=180)
RAIL("GND", btn2, rotation=0)

sw3a, sw3b = SWPUSH("SW3", (620, 330))
RAIL("USER_BTN2", sw3a, rotation=180)
RAIL("GND", sw3b, rotation=0)
sw4a, sw4b = SWPUSH("SW4", (620, 350))
RAIL("USER_BTN3", sw4a, rotation=180)
RAIL("GND", sw4b, rotation=0)

TXT("SW1 = USER_BTN on IO0: start-run button AND the BOOT strap (hold SW1, tap SW2=reset\n"
    "-> ROM download mode). External 10k pull-up R10 keeps the strap solid.\n"
    "SW3/SW4 = USER_BTN2/3 on IO35/IO36 (menu/select UX): active-low, firmware enables the\n"
    "internal pull-ups -- no external resistors. NOTE: on octal-PSRAM (-R8) modules IO35/36\n"
    "do not exist; buttons 2/3 are the sacrificial feature (control is unaffected).\n"
    "SW2 (reset) lives in the controller section on ESP_EN.",
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
U4 = HEF4067("U4", (60, 500))   # read-mux: LINE phototransistor nodes -> MUX_SENSE (ADC1 IO7)

RAIL("PLUS3V3", U4["VDD"], rotation=270)
RAIL("GND", U4["VSS"], rotation=90)
RAIL("GND", U4["E"], rotation=180)   # inhibit tied low -- always enabled
RAIL("MUX_S0", U4["A0"], rotation=180)
RAIL("MUX_S1", U4["A1"], rotation=180)
RAIL("MUX_S2", U4["A2"], rotation=180)
RAIL("GND", U4["A3"], rotation=180)  # only 8 channels used -> S3 tied low
RAIL("MUX_SENSE", U4["Z"], rotation=180)
for _ch in range(8, 16):             # Y8-Y15 unused (line array is Y0-Y7)
    NC(U4[f"Y{_ch}"])
c11a, c11b = C("C13", "100nF", (30, 470))
WIRE(c11a, U4["VDD"])
RAIL("GND", c11b, rotation=270)

TXT("ONE HEF4067 (line array only -- user decision 2026-07-15: wall sensors are read\ndirectly on ESP32 ADC1 pins). Each sensor: phototransistor (collector -> 47k pull-up\nto +3V3 AND to its readout node; emitter -> GND) + IR LED (anode -> current-limit\nresistor -> +3V3; cathode -> its GROUP's low-side switch). Emitters are GANGED:\nfront pair / diagonal pair / side pair / all-8 line bank, each on one BSS138 driven\nby its own GPIO (IO15/16/17/14). Firing a wall pair and sampling BOTH its ADC pins\nin the same pulse halves scan time vs the old serial mux walk; read bright, read\nambient (group off), subtract. Current-limit: wall 33R (~50mA pulsed) / line 120R\n(~15mA, latch-capable for line-follow + indicators). UKMARS-practice grouping keeps\nmutually-staring sensors on different groups.",
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

    # receiver + pull-up. WALL sensors: node goes STRAIGHT to an ESP32 ADC1
    # pin (label only -- no mux). LINE sensors: node feeds read-mux channel
    # Y0-Y7 (= LINE index).
    rx_c, rx_e = SFH309(ref("Q"), (x, row_y), footprint=photo_fp)
    RAIL("GND", rx_e, rotation=270)
    # pull-up x-aligned with the collector pin -> straight vertical wire
    rp1, rp2 = R(ref("R"), "47k", (x + 2.54, row_y + 15))
    WIRE(rp2, rx_c)
    RAIL("PLUS3V3", rp1, rotation=90)
    RAIL(f"{name}_SENSE", rx_c, rotation=0)
    if not is_wall:
        ch = f"Y{i - 6}"
        RAIL(f"{name}_SENSE", U4[ch], rotation=180 if HEF4067_PINS[ch][0] > 0 else 0)

    # emitter + current-limit resistor; cathode joins its GROUP's switched
    # net (one BSS138 per group, below) instead of a per-sensor switch.
    # limiter x-aligned with the LED anode pin -> straight vertical wire
    lr1, lr2 = R(ref("R"), "33" if is_wall else "120", (x + 18.54, row_y + 15))
    RAIL("PLUS3V3", lr1, rotation=90)
    led_k, led_a = LED_SFH4550(ref("D"), (x + 16, row_y), footprint=led_fp)
    WIRE(lr2, led_a)
    _grp = ("EMIT_FRONT_K" if i < 2 else "EMIT_DIAG_K" if i < 4 else
            "EMIT_SIDE_K" if i < 6 else "EMIT_LINE_K")
    RAIL(_grp, led_k, rotation=180)

# Group emitter switches: one BSS138 per group (Q16-Q19), gate driven directly
# by an ESP32 GPIO (no demux -- U5 deleted in rev 4). Gate nets idle low.
for _gref, _gate, _knet, _gx in ((None, "WALL_EMIT_FRONT", "EMIT_FRONT_K", 250),
                                  (None, "WALL_EMIT_DIAG", "EMIT_DIAG_K", 320),
                                  (None, "WALL_EMIT_SIDE", "EMIT_SIDE_K", 390),
                                  (None, "LINE_EMIT", "EMIT_LINE_K", 460)):
    _g, _s, _d = QN_BSS138(ref("Q"), (_gx, 620))
    RAIL(_gate, _g, rotation=180)
    RAIL("GND", _s, rotation=270)
    RAIL(_knet, _d, rotation=0)

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
    ind_g, ind_s, ind_d = QN_BSS138(ref("Q"), (x, IND_ROW_Y))          # Q20..Q27
    RAIL(f"LINE{k}_SENSE", ind_g, rotation=180)
    RAIL("GND", ind_s, rotation=270)
    ir1, ir2 = R(ref("R"), "1k", (x + 10.16, IND_ROW_Y + 15))          # R41..R48
    RAIL("PLUS3V3", ir1, rotation=90)
    # Same LD271 base symbol trick as the IR emitters (extends-skips-ERC), with
    # the real intended part recorded in Value. LED cathode x-aligned with the
    # FET drain, limiter x-aligned with the anode -> straight wires, no bends.
    base = snap((x + 7.62, IND_ROW_Y))
    g.add_component("LED", "LD271", ref("D"),                          # D15..D22
                     "Indicator LED 0603 super-red AlInGaP, high-efficiency bin REQUIRED at 1.4mA (e.g. Kingbright APT1608SURCK; LD271 base symbol for ERC)",
                     base, {"1": "", "2": ""},
                     footprint="LED_SMD:LED_0603_1608Metric")
    ind_led_k, ind_led_a = pin_at(base, (-5.08, 0)), pin_at(base, (2.54, 0))
    WIRE(ir2, ind_led_a)
    WIRE(ind_led_k, ind_d)



# ---------------------------------------------------------------------------
# WALL-SENSOR INDICATOR LEDs (user request 2026-07-15): 6 top-side LEDs, one
# per wall receiver. POLARITY IS INVERTED vs the line indicators: a wall
# REFLECTION pulls the sense node LOW, so these use a P-channel FET (BSS84
# class; Q_PMOS base symbol) -- source at +3V3, gate on the node, drain
# sinking the LED through 1k. Node low (wall present) -> Vgs negative -> LED
# ON = wall seen. Same zero-DC-load gate principle as the line indicators;
# same threshold (not analog) behavior; meaningful while the wall emitters
# are lit (latch a group in debug mode: 2x50mA, inside SFH4550 continuous
# rating).
TXT("WALL-SENSOR INDICATORS  --  6 top-side LEDs, LED ON = wall seen (PMOS, inverted node)", (10, 760), size=5)
for k in range(1, 7):
    x = SENSOR_X0 + (k - 1) * SENSOR_DX
    wd, wg, ws = QPMOS(ref("Q"), "BSS84 (PMOS indicator driver; Q_PMOS base symbol)", (x, 800))   # Q28..Q33
    RAIL(f"WALL{k}_SENSE", wg, rotation=180)
    RAIL("PLUS3V3", ws, rotation=90)
    wr1, wr2 = R(ref("R"), "1k", (x + 2.54, 815))                                   # R49..R54
    WIRE(wd, wr1)   # straight vertical (aligned columns)
    base = snap((x, 830))
    g.add_component("LED", "LD271", ref("D"),                                       # D23..D28
                     "Indicator LED 0603 super-red AlInGaP, high-eff bin (e.g. APT1608SURCK)",
                     base, {"1": "", "2": ""},
                     footprint="LED_SMD:LED_0603_1608Metric")
    w_led_k, w_led_a = pin_at(base, (-5.08, 0)), pin_at(base, (2.54, 0))
    WIRE(wr2, w_led_a)
    RAIL("GND", w_led_k, rotation=180)

with open(r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_sch", "w", encoding="utf-8", newline="\n") as f:
    f.write(g.render(title="Micromouse PCB"))

print("wrote", len(g.symbol_instances), "components,", len(g.label_instances), "labels,",
      len(g.wires), "wires,", len(g.no_connects), "no-connects,",
      "unique lib symbols:", len(g.lib_symbols_needed))
