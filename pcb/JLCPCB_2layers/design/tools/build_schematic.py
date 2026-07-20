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
# BOM part numbers, emitted as hidden MPN/Manufacturer properties on every
# symbol (gen_sch field_provider). Every MPN below was adversarially verified
# against manufacturer datasheets + live distributor listings (2026-07-16):
# packages match the design footprints, and every SOT-23 FET was checked for
# pin1=G/pin2=S/pin3=D. Notes:
#  - SFH 309 FA: ams-OSRAM LAST TIME BUY 2026-12-01 -- order lifetime qty.
#  - PT11-21B/L41/TR8: real Everlight MPN (datasheet DPT-0000132) but big
#    distributors stock only the UNFILTERED -C variant, which this design
#    must NOT use; source the B from Everlight/brokers, or use SFH 320 FA.
#  - TB6612FNG: Toshiba body is 5.6mm vs the 5.3mm KiCad SSOP-24 footprint
#    body -- same 0.65 pitch and lead span, solderable; noted for review.
# ---------------------------------------------------------------------------
_MPN_STATIC = {
    # Rev 6 sourcing rule (user): every line verifiably IN STOCK on
    # lioncircuits.com/parts/{MPN} (checked 2026-07-17; Lion sources turnkey
    # from Digi-Key/Mouser/Element14/Arrow/Avnet/RS -- NOT LCSC).
    "U1": ("AP63203WU-7", "Diodes Incorporated"),          # 3V3 buck, 2A, 3.8-32V in
    "U2": ("TB6612FNG,C,8,EL", "Toshiba"),
    "U3": ("ESP32-S3-WROOM-1-N8R2", "Espressif Systems"),  # quad-PSRAM: IO35-37 usable
    "U4": ("CD74HC4067M96", "Texas Instruments"),
    "U6": ("USBLC6-2SC6", "STMicroelectronics"),
    "U7": ("TPS54302DDCR", "Texas Instruments"),           # 6V motor buck, 3A, 28V in
    "U8": ("BNO055", "Bosch Sensortec"),                   # 9-axis IMU, 3.3V native I2C
    "Q1": ("DMP3098L-7", "Diodes Incorporated"),           # -30V/-3.8A/Vgs +/-20V (2S-safe gate)
    "L1": ("SRP4020TA-4R7M", "Bourns"),
    "L2": ("SRP4020TA-4R7M", "Bourns"),
    "F1": ("MINISMDC350F/16-2", "Littelfuse"),             # PPTC 3.5A hold/7A trip, 16V (rev 7.1: double-stall headroom)
    "J1": ("B2B-XH-A", "JST"),                             # 2S battery main (XH: 3A/contact)
    "J9": ("B3B-XH-A(LF)(SN)", "JST"),                     # 2S balance tap (standard XH-3)
    "SW5": ("PCM12SMTR", "C&K"), "SW6": ("PCM12SMTR", "C&K"),
    # J5/J6 (motor connectors) rev 7.2: JST ZH B6B-ZR -- the robu GA12-N20
    # motors ship with a factory 14cm cable terminated in a JST ZH 1.5mm
    # 6-pos plug, so a ZH header on the board means the motor plugs STRAIGHT
    # IN (user requirement: zero soldering/harness work). ZH is 1A/contact:
    # fine for THIS motor (robu datasheet stall = 0.23A; the generic-N20
    # 1.6A figure kept in sims is a different, hotter wind). In Stock at
    # Lion (verified 2026-07-20). Pin order matches the robu cable, NOT the
    # old functional order -- see the J5/J6 section below.
    "J5": ("B6B-ZR(LF)(SN)", "JST"),
    "J6": ("B6B-ZR(LF)(SN)", "JST"),
    # Rev 7.2 additions: XT60 parallel battery input (male on the PCB, mating
    # the pack's female lead; normal BOM line -- Lion procures turnkey even
    # when the catalog page shows OOS) and the IO46 buzzer driver chain.
    "J10": ("XT60-M", "AMASS"),   # male on PCB (pack lead = female)
    "BZ1": ("CMT-8504-100-SMT-TR", "Same Sky (CUI Devices)"),
    "Q34": ("MMBT2222A-7-F", "Diodes Incorporated"),
    "D29": ("1N4148W-7-F", "Diodes Incorporated"),
    # 2-layer additions: status/power LEDs (red, reuse the wall-indicator part)
    # + WS2812B addressable RGB. J8 (JTAG header) removed.
    "D30": ("APT1608SURCK", "Kingbright"),
    "D31": ("APT1608SURCK", "Kingbright"),
    "D32": ("WS2812B", "Worldsemi"),
    "J7": ("USB4105-GF-A", "GCT"),
    "SW1": ("PTS645VL582LFS", "C&K"), "SW2": ("PTS645VL582LFS", "C&K"),
    "SW3": ("PTS645VL582LFS", "C&K"), "SW4": ("PTS645VL582LFS", "C&K"),
    "C30": ("EEE-FT1C221AP", "Panasonic"),                 # 220uF/16V SMD alu (motor bulk)
}
_CAP_MPN = {
    # 0805 X7R/X5R unless noted. 2S rails (VM_BATT 8.4V max / VM_6V) must use
    # the 25V-class parts -- the old 6.3/10V bulk parts are 1S-only.
    "100nF": ("CL21B104KBCNNNC", "Samsung Electro-Mechanics"),   # 50V
    "1uF":   ("CL21B105KAFNNNE", "Samsung Electro-Mechanics"),   # 25V
    "10uF":  ("CL21A106KPFNNNE", "Samsung Electro-Mechanics"),   # 10V: 3V3 rail only
    "22uF":  ("CL21A226KPCLRNC", "Samsung Electro-Mechanics"),   # 10V: 3V3 rail only
    "10uF/25V": ("CL32B106KBJNNNE", "Samsung Electro-Mechanics"),  # 1210 25V
    "22uF/25V": ("CL32A226KAJNNNE", "Samsung Electro-Mechanics"),  # 1210 25V
    "22pF":  ("CL21C220JBANNNC", "Samsung Electro-Mechanics"),   # 50V C0G
}

def _res_code(v):
    # Yageo value code: "5.1k"->5K1, "10k"->10K, "33"->33R, "120"->120R
    v = v.strip()
    if "." in v:
        a, b = v.split(".", 1)
        unit = b[-1].upper() if b and b[-1] in "kKmM" else "R"
        return f"{a}{unit}{b.rstrip('kKmMrR')}"
    if v and v[-1] in "kKmM":
        return v[:-1] + v[-1].upper()
    return v + "R"

def _bom_fields(ref, value, footprint):
    if ref in _MPN_STATIC:
        mpn, mfr = _MPN_STATIC[ref]
        return {"MPN": mpn, "Manufacturer": mfr}
    fp = footprint.rsplit(":", 1)[-1]
    if fp == "SOT-23":
        if "BSS138" in value:
            return {"MPN": "BSS138LT1G", "Manufacturer": "onsemi"}
        if "BSS84" in value:
            return {"MPN": "BSS84LT1G", "Manufacturer": "onsemi"}
    if fp.startswith("LED_D5.0mm_IRBlack"):
        return {"MPN": "PT334-6B", "Manufacturer": "Everlight"}
    if fp.startswith("LED_D5.0mm"):
        # Rev 6: IR333-A replaces SFH4550/TSAL6400 (TSAL6400 shows lifecycle
        # "Obsolete" on Lion Circuits' own page; IR333-A is In Stock, no flag)
        return {"MPN": "IR333-A", "Manufacturer": "Everlight"}
    if fp == "TCRT5000":
        return {"MPN": "TCRT5000", "Manufacturer": "Vishay"}
    if fp.startswith("LED_0603"):
        return {"MPN": "APT1608SURCK", "Manufacturer": "Kingbright"}
    if fp.startswith("R_0805") and value and value[0].isdigit():
        return {"MPN": f"RC0805FR-07{_res_code(value)}L", "Manufacturer": "Yageo"}
    if fp.startswith("C_") and value in _CAP_MPN:
        mpn, mfr = _CAP_MPN[value]
        return {"MPN": mpn, "Manufacturer": mfr}
    return None

g.field_provider = _bom_fields

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

def CONN2(ref, value, at, footprint="Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal", dnp=False):
    base = snap(at)
    g.add_component("Connector_Generic", "Conn_01x02", ref, value, base, {"1": "", "2": ""}, footprint=footprint, dnp=dnp)
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
    # Q_PMOS_GSD: pins NUMBERED 1/2/3 (G/S/D) matching the SOT-23 pads. The
    # old Device:Q_PMOS numbers its pins literally "D"/"G"/"S" -- no SOT-23
    # pad carries those names, so every QPMOS pad loaded NETLESS and both the
    # router and DRC connectivity were structurally blind to it (rev-5 audit:
    # Q1 + Q28..Q33 floating, battery power path broken). Same pin geometry.
    base = snap(at)
    g.add_component("Transistor_FET", "Q_PMOS_GSD", ref, value, base,
                     {"1": "", "2": "", "3": ""}, footprint=footprint)
    return pin_at(base, (2.54, 5.08)), pin_at(base, (-5.08, 0)), pin_at(base, (2.54, -5.08))  # D, G, S

def LED_SFH4550(ref, at, footprint="LED_THT:LED_D5.0mm_IRGrey", value=None):
    # SFH4550's own symbol uses `extends "LD271"`, which silently skips ERC
    # pin-connectivity checking (PROJECT_NOTES facts #2/#8: confirmed empirically
    # that AP63203WU-extends-AP63200WU produced zero pin_not_connected errors with
    # every pin floating). Instantiate the real LD271 base symbol directly instead
    # -- same physical pinout, footprint, and datasheet part -- with the actual
    # part name (SFH4550) recorded in Value.
    base = snap(at)
    g.add_component("LED", "LD271", ref,
                     value or "IR333-A (real part; LD271 base symbol used so ERC checks pins)",
                     base, {"1": "", "2": ""}, footprint=footprint,
                     datasheet="http://www.osram-os.com/Graphics/XPic3/00116140_0.pdf")
    return pin_at(base, (-5.08, 0)), pin_at(base, (2.54, 0))  # K (cathode), A (anode)

def SFH309(ref, at, footprint="LED_THT:LED_D3.0mm_Clear", value=None):
    base = snap(at)
    g.add_component("Sensor_Optical", "SFH309", ref, value or "SFH309", base, {"1": "", "2": ""}, footprint=footprint,
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

def SWPUSH(ref, at, value="SW_Push", footprint="Button_Switch_THT:SW_PUSH_6mm"):
    base = snap(at)
    g.add_component("Switch", "SW_Push", ref, value, base, {"1": "", "2": ""}, footprint=footprint)
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
_ctr = {"R": 5, "C": 8, "Q": 1, "D": 0, "J": 4, "U": 1, "SW": 0, "LS": 0}
def ref(prefix):
    _ctr[prefix] = _ctr.get(prefix, 0) + 1
    return f"{prefix}{_ctr[prefix]}"

# ---------------------------------------------------------------------------
# POWER SECTION -- rev 6: 2S LiPo -> AP63203 (3V3, 2A) + TPS54302 (6.0V motor
# rail, 3A). Two slide switches: SW5 enables everything EXCEPT motors (3V3
# buck EN); SW6 additionally enables the motor rail (6V buck EN, pulled from
# the SW5-gated node so motors require BOTH switches on). No onboard charger:
# a 2S pack charges on an external balance charger; J9 receives the pack's
# balance plug for per-cell monitoring while driving.
# ---------------------------------------------------------------------------
TXT("POWER  --  2S LiPo -> AP63203 3V3 (2A) + TPS54302 6V motor rail (3A); SW5=logic, SW6=motors", (10, 190), size=5)

# 2S LiPo (6.0-8.4V) on JST-XH (3A/contact -- rated for the twin-N20 stall
# peak). Usable pack window 6.6-8.4V (3.3V/cell firmware cutoff): above 6.6V
# the 6V buck regulates; in the last few hundred mV of dropout it degrades
# gracefully toward ~Vbat (documented competition practice -- firmware also
# feeds Vbat forward into the PWM scale).
j1p1, j1p2 = CONN2("J1", "BATT_IN_2S", (20, 150), footprint="Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical")
RAIL("GND", j1p2, rotation=180)
PWR("PWR_FLAG", j1p2)
RAIL("BATT_RAW", j1p1, rotation=0)

# XT60 parallel battery input (rev 7.2, user request "keep both options"):
# electrically IDENTICAL to J1 (BATT_RAW/GND) -- the pack plugs into EITHER
# J1 (JST-XH lead) OR J10 (XT60 lead), never both at once ("ONE PACK ONLY"
# board silk).
j10p1, j10p2 = CONN2("J10", "BATT_IN_XT60 (parallel option -- ONE PACK ONLY)", (55, 110),
                     footprint="Connector_AMASS:AMASS_XT60-M_1x02_P7.20mm_Vertical")
# J10 stays a NORMAL BOM line (user 2026-07-20): Lion sources turnkey and can
# procure even when their catalog page shows Out of Stock -- let them try; if
# they can't, hand-fitting an XT60-M (~Rs.30, robu) is a one-minute fallback.
# Gender: XT60-M = MALE on the PCB, mating the FEMALE XT60 every LiPo pack
# lead carries (Amass convention: battery=F, device=M).
RAIL("BATT_RAW", j10p1, rotation=0)
RAIL("GND", j10p2, rotation=180)

# Balance tap (JST-XH 3-pin = the standard 2S balance plug): pin1 GND (B-),
# pin2 pack midpoint (B1+), pin3 pack + (B2+, same wire pair as J1 pin 1).
# Monitoring only -- charge current never flows through this board.
# Rev 7.2 (user): the balance plug is OPTIONAL -- with J9 unplugged the
# R75/R76 divider drains BAT_MID_SENSE to ~0 V, which firmware detects
# (cell-1 reading < 0.5 V = physically impossible with a pack connected)
# and falls back to pack-level-only monitoring via VBAT_SENSE.
j9p1, j9p2, j9p3 = CONN3("J9", "BALANCE_2S", (20, 110))
RAIL("GND", j9p1, rotation=180)
RAIL("BAT_MID", j9p2, rotation=180)
RAIL("BATT_RAW", j9p3, rotation=180)

f1p1, f1p2 = FUSE("F1", "2.6A/16V PPTC", (90, 150), footprint="Fuse:Fuse_1812_4532Metric")
RAIL("BATT_RAW", f1p1, rotation=90)

# Reverse-polarity P-MOSFET: battery -> DRAIN, load -> SOURCE, gate to GND
# (body-diode proof in PROJECT_NOTES). At 2S the gate sees -6.0..-8.4V --
# DMP3098L-7 is Vgs +/-20V rated (the rev<=5 DMP2035U was +/-8V: 2S-unsafe),
# -30V/-3.8A, Rds(on) well-enhanced by -4.5V.
qD, qG, qS = QPMOS("Q1", "Q_PMOS reverse guard (DMP3098L-7: Vgs +/-20V, 2S-safe)", (125, 150))
WIRE(f1p2, qD)

r1p1, r1p2 = R("R1", "100k", (125, 115))
WIRE(qG, r1p1)
RAIL("GND", r1p2, rotation=270)

RAIL("VM_BATT", qS, rotation=90)
PWR("PWR_FLAG", qS)

# Input bulk: 10uF/25V ceramics (X5R 1210 -- 25V class holds real capacitance
# at 8.4V bias; the old 6.3-10V parts were 1S-only) + 100nF HF.
c1p1, c1p2 = C("C1", "10uF/25V", (155, 150), footprint="Capacitor_SMD:C_1210_3225Metric")
RAIL("VM_BATT", c1p1, rotation=90)
RAIL("GND", c1p2, rotation=270)

c2p1, c2p2 = C("C2", "100nF", (175, 150))
RAIL("VM_BATT", c2p1, rotation=90)
RAIL("GND", c2p2, rotation=270)

c4p1, c4p2 = C("C4", "10uF/25V", (210, 150), footprint="Capacitor_SMD:C_1210_3225Metric")
RAIL("VM_BATT", c4p1, rotation=90)
RAIL("GND", c4p2, rotation=270)

# --- 3V3 logic buck: AP63203WU-7 (TSOT-26, fixed 3.3V, 2A, 3.8-32V in,
# 1.1MHz). Base symbol AP63200WU instantiated (AP63203WU `extends` it and
# extends-symbols skip ERC pin checks -- standing workaround), real part in
# Value. Pinout (TSOT-26): 1 FB / 2 EN / 3 VIN / 4 GND / 5 SW / 6 BST.
U1_BASE = snap((250, 150))
g.add_component("Regulator_Switching", "AP63200WU", "U1",
                 "AP63203WU-7 (fixed 3.3V 2A buck; AP63200WU base symbol so ERC checks pins)",
                 U1_BASE, {str(n): "" for n in range(1, 7)},
                 footprint="Package_TO_SOT_SMD:TSOT-23-6",
                 datasheet="https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf")
u1_fb  = pin_at(U1_BASE, (10.16, -2.54))
u1_en  = pin_at(U1_BASE, (-10.16, -2.54))
u1_vin = pin_at(U1_BASE, (-10.16, 2.54))
u1_gnd = pin_at(U1_BASE, (0, -7.62))
u1_sw  = pin_at(U1_BASE, (10.16, 2.54))
u1_bst = pin_at(U1_BASE, (10.16, 0))

RAIL("VM_BATT", u1_vin, rotation=180)
RAIL("PWR_EN", u1_en, rotation=180)      # soft power switch node (R69 + SW5)
RAIL("GND", u1_gnd, rotation=270)
RAIL("SW_3V3", u1_sw, rotation=0)
# AP63203 (fixed): FB pin is the VOUT sense -- tie to the output rail.
RAIL("PLUS3V3", u1_fb, rotation=0)
PWR("PWR_FLAG", pin_at(U1_BASE, (10.16, -2.54)))

# Bootstrap cap BST->SW (datasheet 0.1uF) + power inductor SW -> 3V3.
cb1a, cb1b = C("C3", "100nF", (238, 118))
RAIL("SW_3V3", cb1a, rotation=90)
WIRE(cb1b, u1_bst)
l1p1, l1p2 = L("L1", "4.7uH", (272, 150), footprint="n20:L_Bourns_SRP4020TA")
RAIL("SW_3V3", l1p1, rotation=90)
RAIL("PLUS3V3", l1p2, rotation=270)

# Output caps: 2x 22uF (10V class is fine on the 3.3V rail).
c5p1, c5p2 = C("C5", "22uF", (285, 150))
RAIL("PLUS3V3", c5p1, rotation=90)
RAIL("GND", c5p2, rotation=270)
c7p1, c7p2 = C("C7", "22uF", (295, 150))
RAIL("PLUS3V3", c7p1, rotation=90)
RAIL("GND", c7p2, rotation=270)

# SW5 = master soft switch: R69 pulls PWR_EN to the battery rail (AP63203 EN
# is VIN-tolerant); PCM12SMTR slide grounds it = everything off.
# R69 = 100k, NOT the rev-5 1M: PWR_EN also SOURCES the R70/R71 MOT_EN
# divider, and with a 1M source impedance the whole string computed to
# MOT_EN = 0.64V -- BELOW the TPS54302's 1.21V enable threshold: the motor
# rail could never turn on (caught by circuit_tests P10, 2026-07-17). With
# 100k/220k/110k the string gives MOT_EN = 0.256*VBAT = 1.69V at the 6.6V
# pack floor (worst-case threshold 1.31V: real margin) and 2.15V at 8.4V.
# Off-state drain through the string: ~20uA (acceptable; unplug for storage).
r69a, r69b = R("R69", "100k", (232, 143))
RAIL("VM_BATT", r69a, rotation=90)
RAIL("PWR_EN", r69b, rotation=270)
SW5_BASE = snap((243, 155))
g.add_component("Switch", "SW_SPDT", "SW5",
                 "PWR ALL (PCM12SMTR slide; slide-to-GND = OFF)", SW5_BASE,
                 {"1": "", "2": "", "3": ""},
                 footprint="Button_Switch_SMD:SW_SPDT_PCM12")
RAIL("GND", pin_at(SW5_BASE, (5.08, 2.54)), rotation=0)      # throw A -> GND
RAIL("PWR_EN", pin_at(SW5_BASE, (-5.08, 0)), rotation=180)   # common -> EN node
NC(pin_at(SW5_BASE, (5.08, -2.54)))                          # throw B unused

TXT("+3V3 is the regulated logic rail: ESP32-S3, mux, IMU, encoder VCC, PT pull-ups,\nindicator drivers and IR LED current. VM_6V feeds ONLY the TB6612 VM pins.",
    (200, 100), size=2.2)

# --- 6V MOTOR RAIL: TPS54302 (SOT-23-6, 3A, 4.5-28V in, 400kHz). FB divider
# 100k/11k -> 0.596V x (1+100/11) = 6.01V. Motors therefore see a REGULATED
# 6.0V with the buck's 3A current limit as a hard supply-side ceiling
# (per-channel limits are TB6612's own). Pinout: 1 GND / 2 SW / 3 VIN /
# 4 FB / 5 EN / 6 BOOT.
U7_BASE = snap((250, 230))
g.add_component("Regulator_Switching", "TPS54302", "U7",
                 "TPS54302DDCR (6.0V/3A motor buck; FB=100k/11k)",
                 U7_BASE, {str(n): "" for n in range(1, 7)},
                 footprint="Package_TO_SOT_SMD:SOT-23-6",
                 datasheet="https://www.ti.com/lit/ds/symlink/tps54302.pdf")
u7_gnd = pin_at(U7_BASE, (0, -7.62))
u7_sw  = pin_at(U7_BASE, (10.16, 0))
u7_vin = pin_at(U7_BASE, (-10.16, 2.54))
u7_fb  = pin_at(U7_BASE, (10.16, -2.54))
u7_en  = pin_at(U7_BASE, (-10.16, -2.54))
u7_bst = pin_at(U7_BASE, (10.16, 2.54))

RAIL("VM_BATT", u7_vin, rotation=180)
RAIL("GND", u7_gnd, rotation=270)
RAIL("MOT_EN", u7_en, rotation=180)
RAIL("SW_6V", u7_sw, rotation=0)
RAIL("FB_6V", u7_fb, rotation=0)

cb2a, cb2b = C("C15", "100nF", (238, 205))
RAIL("SW_6V", cb2a, rotation=90)
WIRE(cb2b, u7_bst)
l2p1, l2p2 = L("L2", "4.7uH", (272, 230), footprint="n20:L_Bourns_SRP4020TA")
RAIL("SW_6V", l2p1, rotation=90)
RAIL("VM_6V", l2p2, rotation=270)
PWR("PWR_FLAG", l2p2)

# 6V rail caps: 2x 22uF/25V 1210 at the buck + the 220uF/16V alu bulk (C30)
# lives at the TB6612 VM entry (motor hot-loop, standards item).
c16a, c16b = C("C16", "22uF/25V", (285, 230), footprint="Capacitor_SMD:C_1210_3225Metric")
RAIL("VM_6V", c16a, rotation=90)
RAIL("GND", c16b, rotation=270)
c17a, c17b = C("C17", "22uF/25V", (295, 230), footprint="Capacitor_SMD:C_1210_3225Metric")
RAIL("VM_6V", c17a, rotation=90)
RAIL("GND", c17b, rotation=270)
c18a, c18b = C("C18", "10uF/25V", (305, 230), footprint="Capacitor_SMD:C_1210_3225Metric")
RAIL("VM_BATT", c18a, rotation=90)
RAIL("GND", c18b, rotation=270)

# FB divider (6.01V)
r73a, r73b = R("R73", "100k", (315, 230))
RAIL("VM_6V", r73a, rotation=90)
RAIL("FB_6V", r73b, rotation=270)
r74a, r74b = R("R74", "11k", (325, 230))
RAIL("FB_6V", r74a, rotation=90)
RAIL("GND", r74b, rotation=270)

# SW6 = motor enable. The pull-up feeds from PWR_EN (NOT VM_BATT): motors can
# only be enabled when SW5 is already on -- "SW6 enables supply to motors
# ALSO". The R69/R70/R71 string (100k/220k/110k) puts the TPS54302 EN at
# 1.69-2.15V across the pack window: above the worst-case 1.31V rising
# threshold, far below any absolute limit. SW6 shorts MOT_EN to GND = off.
r70a, r70b = R("R70", "220k", (232, 250))
RAIL("PWR_EN", r70a, rotation=90)
RAIL("MOT_EN", r70b, rotation=270)
r71a, r71b = R("R71", "110k", (222, 250))
RAIL("MOT_EN", r71a, rotation=90)
RAIL("GND", r71b, rotation=270)
SW6_BASE = snap((243, 262))
g.add_component("Switch", "SW_SPDT", "SW6",
                 "PWR MOTORS (PCM12SMTR slide; slide-to-GND = motors OFF)", SW6_BASE,
                 {"1": "", "2": "", "3": ""},
                 footprint="Button_Switch_SMD:SW_SPDT_PCM12")
RAIL("GND", pin_at(SW6_BASE, (5.08, 2.54)), rotation=0)
RAIL("MOT_EN", pin_at(SW6_BASE, (-5.08, 0)), rotation=180)
NC(pin_at(SW6_BASE, (5.08, -2.54)))

# Battery telemetry dividers -> MUX channels (rev 6: IO8/IO37 were reclaimed
# for MUX_S3/IMU_INT; VBAT, the pack midpoint and VBUS all read through the
# 4067's spare channels). Pack: 100k/39k -> 8.4V => 2.36V. Midpoint:
# 100k/100k -> 4.2V => 2.1V. Tapped DOWNSTREAM of Q1 (VBAT) so a stored pack
# sees only J9's 200k midpoint path (~21uA) -- acceptable for a pack that is
# unplugged for storage anyway (documented).
r2p1, r2p2 = R("R2", "100k", (60, 65))
RAIL("VM_BATT", r2p1, rotation=90)
r3p1, r3p2 = R("R3", "39k", (60, 40))
WIRE(r2p2, r3p1)
RAIL("GND", r3p2, rotation=270)
c6p1, c6p2 = C("C6", "100nF", (80, 52))
WIRE(r2p2, c6p1)
RAIL("GND", c6p2, rotation=270)
RAIL("VBAT_SENSE", r2p2, rotation=0)

r75a, r75b = R("R75", "100k", (100, 65))
RAIL("BAT_MID", r75a, rotation=90)
r76a, r76b = R("R76", "100k", (100, 40))
WIRE(r75b, r76a)
RAIL("GND", r76b, rotation=270)
c19a, c19b = C("C19", "100nF", (118, 52))
WIRE(r75b, c19a)
RAIL("GND", c19b, rotation=270)
RAIL("BAT_MID_SENSE", r75b, rotation=0)

TXT("VBAT_SENSE = pack (0-8.4V) x 39/139 <= 2.36V; BAT_MID_SENSE = cell-1 (0-4.2V) x 1/2 <= 2.1V.\nBoth + VBUS_SENSE read through mux channels Y8/Y9/Y10 (ADC1 IO7). Firmware cutoff:\n3.3V/cell (either cell) = 6.6V pack floor; the 6V rail is in regulation across that window.",
    (20, 20), size=2.2)

# ---------------------------------------------------------------------------
# (MCU SECTION REMOVED 2026-07-13 -- STM32 dropped; the ESP32 in the CONTROLLER
#  section below is now the sole controller. All former STM32 nets are sourced
#  there instead. See PROJECT_NOTES.md.)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# MOTOR DRIVER (BARE SMD TB6612FNG) + ENCODERS SECTION
# ---------------------------------------------------------------------------
# User decision (2026-07-16): back to the bare SSOP-24 chip (U2) -- the
# socketed breakout ate board area and its vendor-variable pinout was a
# standing fab risk. The stock SSOP-24 footprint ships with a real 3D model,
# so representation is exact. On-carrier decoupling returns (the breakout's
# own caps are gone): 10uF + 100nF on VM at the chip, 100nF on VCC, per the
# Toshiba application circuit.
TXT("MOTOR DRIVER (TB6612FNG, SMD)  --  2x N20-with-encoder motors", (10, 230), size=5)

U2 = TB6612("U2", (95, 310))
RAIL("VM_6V", U2["VM1"], rotation=90)
RAIL("VM_6V", U2["VM2"], rotation=90)
RAIL("VM_6V", U2["VM3"], rotation=90)
RAIL("PLUS3V3", U2["VCC"], rotation=90)
RAIL("GND", U2["GND"], rotation=270)
RAIL("GND", U2["PGND1"], rotation=270)
RAIL("GND", U2["PGND2"], rotation=270)
# Rev 6 IN/IN PWM mode: PWMA/PWMB tied HIGH (permanent), the four IN pins
# carry LEDC PWM (Toshiba-documented drive mode; frees two GPIOs for I2C).
# STBY tied HIGH through R55: the hardware motor kill is now SW6 (VM_6V buck
# EN) and TB6612's IN pins have internal pull-downs, so a held-in-reset MCU
# leaves the outputs off. IO46 (the old STBY strap risk) is freed to a clean
# no-connect.
RAIL("PLUS3V3", U2["PWMA"], rotation=180)
RAIL("PLUS3V3", U2["PWMB"], rotation=180)
r55a, r55b = R("R55", "10k", (60, 285))
RAIL("PLUS3V3", r55a, rotation=90)
WIRE(r55b, U2["STBY"])
RAIL("AIN1", U2["AIN1"], rotation=180)
RAIL("AIN2", U2["AIN2"], rotation=180)
RAIL("BIN1", U2["BIN1"], rotation=180)
RAIL("BIN2", U2["BIN2"], rotation=180)
RAIL("MOTA_P", U2["AO1"], rotation=0)
RAIL("MOTA_N", U2["AO2"], rotation=0)
RAIL("MOTB_P", U2["BO1"], rotation=0)
RAIL("MOTB_N", U2["BO2"], rotation=0)

# VM decoupling for 2S/6V: C30 220uF/16V alu bulk (hot-loop, standards item)
# + 10uF/25V + 100nF ceramics at the pins.
c30a, c30b = C("C30", "220uF/16V", (118, 335), footprint="Capacitor_SMD:CP_Elec_6.3x7.7")
RAIL("VM_6V", c30a, rotation=90)
RAIL("GND", c30b, rotation=270)
c11a, c11b = C("C11", "10uF/25V", (130, 335), footprint="Capacitor_SMD:C_1210_3225Metric")
RAIL("VM_6V", c11a, rotation=90)
RAIL("GND", c11b, rotation=270)
c12a, c12b = C("C12", "100nF", (142, 335))
RAIL("VM_6V", c12a, rotation=90)
RAIL("GND", c12b, rotation=270)
c14a, c14b = C("C14", "100nF", (154, 335))
RAIL("PLUS3V3", c14a, rotation=90)
RAIL("GND", c14b, rotation=270)

TXT("Bare TB6612FNG (U2, SSOP-24) in IN/IN PWM mode: PWMA/PWMB tied 3V3, AIN/BIN = LEDC\n(IN1=PWM,IN2=0 fwd-coast; IN1=PWM,IN2=1 rev-brake). VM = regulated 6.0V rail (TPS54302,\n3A limit) gated by SW6; STBY pulled high (R55) -- motor kill = SW6 + IN pins' internal\npull-downs. Decoupling: C30 220uF/16V alu + C11 10uF/25V + C12 100nF on VM, C14 on VCC.",
    (10, 258), size=2.0)

# Motor A connector -- rev 7.2 DIRECT-PLUG: JST ZH B6B-ZR, 1.5mm, matches
# the plug already crimped on the robu GA12-N20's factory cable. Pin order
# is therefore the MOTOR CABLE's order (robu listing wire table:
# 1 Red=M1, 2 Black=VCC, 3 Yellow=C1, 4 Green=C2, 5 Blue=GND, 6 White=M2),
# NOT the old functional grouping. The listing table conflicts with the
# listing PHOTO on whether pos 2/5 are VCC/GND or GND/VCC -- METER-VERIFY
# the two power wires before first plug-in (HANDOFF section 17); if swapped,
# remedy is lifting the two crimp retainers and swapping positions 2/5 in
# the housing (no soldering).
jA = CONN6("J5", "MOTOR_A_N20_ENCODER", (200, 330),
           footprint="Connector_JST:JST_ZH_B6B-ZR_1x06_P1.50mm_Vertical")
RAIL("MOTA_P", jA[0], rotation=0)      # 1 Red    M1 (motor +)
RAIL("PLUS3V3", jA[1], rotation=0)     # 2 Black  encoder VCC
rea1, rea2 = R("R6", "10k", (220, 320))
WIRE(rea1, jA[2])
RAIL("PLUS3V3", rea2, rotation=90)
RAIL("ENC1_A", jA[2], rotation=0)      # 3 Yellow C1
reb1, reb2 = R("R7", "10k", (220, 300))
WIRE(reb1, jA[3])
RAIL("PLUS3V3", reb2, rotation=90)
RAIL("ENC1_B", jA[3], rotation=0)      # 4 Green  C2
RAIL("GND", jA[4], rotation=0)         # 5 Blue   encoder GND
RAIL("MOTA_N", jA[5], rotation=0)      # 6 White  M2 (motor -)

# Motor B connector (same cable order)
jB = CONN6("J6", "MOTOR_B_N20_ENCODER", (200, 260),
           footprint="Connector_JST:JST_ZH_B6B-ZR_1x06_P1.50mm_Vertical")
RAIL("MOTB_P", jB[0], rotation=0)
RAIL("PLUS3V3", jB[1], rotation=0)
rec1, rec2 = R("R8", "10k", (220, 250))
WIRE(rec1, jB[2])
RAIL("PLUS3V3", rec2, rotation=90)
RAIL("ENC2_A", jB[2], rotation=0)
red1, red2 = R("R9", "10k", (220, 230))
WIRE(red1, jB[3])
RAIL("PLUS3V3", red2, rotation=90)
RAIL("ENC2_B", jB[3], rotation=0)
RAIL("GND", jB[4], rotation=0)
RAIL("MOTB_N", jB[5], rotation=0)

TXT("10k pull-ups on all 4 encoder lines -- defensive: N20-encoder wire-color-to-\nfunction mapping is unverified for the exact unit ordered (see PROJECT_NOTES.md),\nand encoder output stage (open-drain vs push-pull) isn't confirmed either. A pull-up\nis required if open-drain and harmless if push-pull.\nRev 7.2: J5/J6 are JST ZH B6B-ZR in the ROBU CABLE order (M1,VCC,C1,C2,GND,M2) --\nthe motor's factory plug goes straight in, zero soldering. METER-VERIFY pins 2/5\n(VCC/GND) against the actual cable before first plug-in; swap crimps 2/5 if reversed.",
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
# LOCKED PIN MAP rev 6 (ADC1 = IO1..IO10 is the only WiFi-safe ADC):
#   IO1-6  WALL1-6_SENSE   IO7 MUX_SENSE (line array + battery telemetry)
#   IO8 MUX_S3 (4067 high select -- VBAT/BAT_MID/VBUS moved onto mux Y8/9/10)
#   IO9/10 AIN1/AIN2 (LEDC PWM, IN/IN mode)   IO11-13 MUX_S0-2
#   IO14 LINE_EMIT   IO15-17 WALL_EMIT_FRONT/DIAG/SIDE
#   IO18 IMU_SDA / IO21 IMU_SCL (I2C to BNO055; freed by IN/IN motor mode)
#   IO37 IMU_INT   IO38 BIN1
#   IO45 BIN2 -- STRAPPING pin as motor output: safe ONLY because it idles
#     LOW and carries only R65's pull-DOWN (IO45 high at reset selects 1.8V
#     flash supply = brick; never add a pull-up to this net)
#   IO46 BUZZ_CTRL (rev 7.2: buzzer driver -- the ONLY free GPIO; strap-safe:
#     the NPN base + 220R load only ever pulls it toward GND = boot default)
#   IO39-42 JTAG (MTCK/MTDO/MTDI/MTMS) -> J8, dedicated for debugging
#   IO43(TXD0)/IO44(RXD0) ENC2_B/ENC2_A   IO47/48 ENC1_A/B  (console = USB-CDC)
#   IO0 BTN1/BOOT   IO35/36 BTN2/BTN3 (internal pull-ups; N8R2 = quad PSRAM,
#     so IO35-37 exist -- only octal -R8 modules lose them)
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
    "7": "VBAT_SENSE", "12": "BAT_MID_SENSE",                           # IO7/IO8 ADC1 (battery direct; mux removed)
    "17": "VBUS_SENSE", "18": "AIN2",                                   # IO9 ADC1 (VBUS) / IO10 LEDC PWM
    "19": "AIN1", "20": "STATUS_LED", "21": None,                      # IO11 LEDC PWM; IO12 status LED; IO13 spare
    "22": "RGB_DATA",                                                   # IO14 -> WS2812B addressable RGB
    "8": "WALL_EMIT_FRONT", "9": "WALL_EMIT_DIAG", "10": "WALL_EMIT_SIDE",  # IO15-17
    "11": "IMU_SDA", "23": "IMU_SCL",                                    # IO18/IO21 (I2C, BNO055)
    "28": "USER_BTN2", "29": "USER_BTN3", "30": "IMU_INT",               # IO35/36; IO37 = BNO055 interrupt
    "31": "BIN1",                                                        # IO38
    "32": None, "33": None, "34": None, "35": None,   # IO39-42 ex-JTAG (J8 removed; debug via native USB-C JTAG)
    "36": "ENC2_A_S3", "37": "ENC2_B_S3",   # IO44(RXD0)/IO43(TXD0) via 1k guards
    "26": "BIN2", "16": "BUZZ_CTRL",   # IO45 strap (idle-low output); IO46 -> buzzer driver (rev 7.2; strap-safe: Q34's B-E junction + R81 only ever pull the pin LOW, its required boot state)
    "24": "ENC1_A", "25": "ENC1_B",                                      # IO47/IO48
    "27": "USER_BTN",                                                    # IO0 (BOOT strap)
    "13": "USB_DM", "14": "USB_DP",
    "1": "GND", "40": "GND", "41": "GND",
}
U3_BASE = snap((360, 300))
g.add_component("RF_Module", "ESP32-S3-WROOM-1", "U3",
                "ESP32-S3-WROOM-1-N8R2 (quad PSRAM: IO35-37 usable; octal -R8 would lose them)",
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
sw2a, sw2b = SWPUSH("SW2", (447, 265), value="RESET")
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
RAIL("USB_VBUS", pin_at(J7_BASE, (15.24, 15.24)), rotation=0)  # VBUS stack -> sense divider
NC(pin_at(J7_BASE, (15.24, -12.7)))            # SBU1
NC(pin_at(J7_BASE, (15.24, -15.24)))           # SBU2
rcc1a, rcc1b = R("R12", "5.1k", (508, 270))
WIRE(rcc1a, pin_at(J7_BASE, (15.24, 10.16)))   # CC1
RAIL("GND", rcc1b, rotation=270)
# VBUS presence divider: 10k/15k, 5V -> 3.0V into IO37 (digital read = solid
# high; <=3.6V abs max respected). Firmware detects a plugged USB cable.
# Also gives the 4-pad VBUS stack a real routed net instead of a dangling NC.
# (-R8 modules lose IO37 -> cable detect is sacrificial there, like buttons B/C.)
rv1a, rv1b = R("R67", "10k", (533, 268))
RAIL("USB_VBUS", rv1a, rotation=90)
RAIL("VBUS_SENSE", rv1b, rotation=270)
rv2a, rv2b = R("R68", "15k", (543, 268))
RAIL("VBUS_SENSE", rv2a, rotation=90)
RAIL("GND", rv2b, rotation=270)
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
for _ref, _net, _gx in (("R62", "WALL_EMIT_FRONT", 455),
                         ("R63", "WALL_EMIT_DIAG", 465), ("R64", "WALL_EMIT_SIDE", 475)):
    # R61/LINE_EMIT pulldown removed with the line emitter group (2-layer).
    _p1, _p2 = R(_ref, "100k", (_gx, 330))
    RAIL(_net, _p1, rotation=90)
    RAIL("GND", _p2, rotation=270)

# Strap insurance: IO45 (BIN2) high at reset would switch VDD_SPI to 1.8V and
# brick the boot. A 10k pull-down guarantees the strap reads low at reset.
# (Rev 6: R66 deleted -- STBY is tied high at U2 and IO46 is a clean NC, so
# the second strap risk no longer exists.)
rs45a, rs45b = R("R65", "10k", (490, 330))
RAIL("BIN2", rs45a, rotation=90)
RAIL("GND", rs45b, rotation=270)


# USB ESD array (exposed user-handled connector on a robot). USBLC6 rail pin
# clamps to +3V3 (VBUS is unused on this board). Rev 6: NO 22R series
# resistors -- the ESP32-S3's integrated FS PHY meets the USB driver-impedance
# window internally and every Espressif S3 devkit routes GPIO19/20 directly
# to the connector (standards review 2026-07-17); dropping R59/R60 also
# removes two parts from the most congested routing pocket on the board.
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
RAIL("USB_DM", pin_at(U6_BASE, (5.08, 0)), rotation=0)        # I/O1 module side (direct)
RAIL("USB_DP", pin_at(U6_BASE, (5.08, -2.54)), rotation=0)    # I/O2 module side (direct)

# JTAG header J8 REMOVED (2-layer edition, user request): debugging uses the
# ESP32-S3 native USB-Serial-JTAG over the rear USB-C (J7). The dedicated JTAG
# GPIOs IO39-42 are freed and no-connected in the pin map above.

TXT("ESP32-S3-WROOM-1 on FreeRTOS: 6 wall sensors DIRECT on ADC1 IO1-IO6 (a fired pair is\n"
    "sampled in parallel), line array via U4 (IO7 + IO11-13), battery IO8, TB6612 on\n"
    "IO9/10/38/45, buzzer IO46 (straps 45/46 = idle-low outputs ONLY -- never add pull-ups),\n"
    "encoders IO43/44/47/48 (PCNT hardware quadrature via GPIO matrix), JTAG on the real\n"
    "JTAG quad IO39-42 -> J8 (ESP-Prog). Buttons: SW1=IO0 (start/BOOT), SW3=IO35, SW4=IO36\n"
    "(internal pull-ups). USB-C (rear) on the native USB pads = flash + console; UART0\n"
    "pins repurposed as encoder inputs. Every analog net sits on ADC1 (IO1-IO8).",
    (300, 368), size=2.0)

# ---------------------------------------------------------------------------
# CONNECTORS / DEBUG SECTION
# ---------------------------------------------------------------------------
TXT("USER INTERFACE  --  3 buttons", (600, 230), size=5)

btn1, btn2 = SWPUSH("SW1", (620, 300), value="BTN_A (start / BOOT)")
rbtn1, rbtn2 = R("R10", "10k", (640, 300))
WIRE(rbtn2, btn1)
RAIL("PLUS3V3", rbtn1, rotation=90)
RAIL("USER_BTN", btn1, rotation=180)
RAIL("GND", btn2, rotation=0)

sw3a, sw3b = SWPUSH("SW3", (620, 330), value="BTN_B")
RAIL("USER_BTN2", sw3a, rotation=180)
RAIL("GND", sw3b, rotation=0)
sw4a, sw4b = SWPUSH("SW4", (620, 350), value="BTN_C")
RAIL("USER_BTN3", sw4a, rotation=180)
RAIL("GND", sw4b, rotation=0)

TXT("Buttons are lettered on the silkscreen: A=SW1, B=SW3, C=SW4, RST=SW2.\n"
    "SW1/A = USER_BTN on IO0: start-run button AND the BOOT strap (hold A, tap RST\n"
    "-> ROM download mode). External 10k pull-up R10 keeps the strap solid.\n"
    "SW3/SW4 = USER_BTN2/3 on IO35/IO36 (menu/select UX): active-low, firmware enables the\n"
    "internal pull-ups -- no external resistors. NOTE: on octal-PSRAM (-R8) modules IO35/36\n"
    "do not exist; buttons 2/3 are the sacrificial feature (control is unaffected).\n"
    "SW2 (reset) lives in the controller section on ESP_EN.",
    (600, 260), size=2.0)

# ---------------------------------------------------------------------------
# IMU -- BNO055 9-axis (accel+gyro+mag, on-chip fusion), rev-6 user request.
# 3.3V-native (VDD and VDDIO both 3V3 -- the ICM-20948 alternative was
# rejected: its VDDIO is 1.8V-only and would force level shifters). I2C mode:
# PS0=PS1=GND; COM0=SDA, COM1=SCL, COM2=GND, COM3=addr select (GND = 0x28).
# Wiring cross-checked against the Adafruit breakout reference netlist.
# INTERNAL 32.768kHz oscillator (rev 6.1): the external crystal was dropped.
# It is a Bosch RECOMMENDATION for best fusion time-base accuracy, not a
# requirement -- the BNO055 has a built-in oscillator (Adafruit's default
# configuration runs internal, CLK_SEL=0). Fitting the crystal 3.2mm from a
# 0.5mm-pitch LGA-28 in this dense cluster made XIN32/XOUT32 (both north-row
# LGA pads) unroutable; internal-clock removes X1/C21/C22 and the two hardest
# nets on the board. Firmware leaves SYS_TRIGGER.CLK_SEL at 0. INT -> IO37.
# ---------------------------------------------------------------------------
TXT("IMU  --  BNO055 9-axis on I2C (IO18=SDA, IO21=SCL, IO37=INT), addr 0x28; internal osc", (600, 420), size=5)
U8_BASE = snap((650, 480))
g.add_component("Sensor_Motion", "BNO055", "U8",
                 "BNO055 (9-axis IMU + fusion; 3.3V native; I2C 0x28)",
                 U8_BASE, {str(n): "" for n in range(1, 29)},
                 footprint="n20:BNO055",
                 datasheet="https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bno055-ds000.pdf")
RAIL("GND", pin_at(U8_BASE, (-2.54, -17.78)), rotation=270)     # GND (2)
RAIL("PLUS3V3", pin_at(U8_BASE, (-2.54, 17.78)), rotation=90)   # VDD (3)
RAIL("PLUS3V3", pin_at(U8_BASE, (2.54, 17.78)), rotation=90)    # VDDIO (28)
RAIL("GND", pin_at(U8_BASE, (2.54, -17.78)), rotation=270)      # GNDIO (25)
RAIL("GND", pin_at(U8_BASE, (15.24, -10.16)), rotation=0)       # PS1 (5) -> I2C mode
RAIL("GND", pin_at(U8_BASE, (15.24, -7.62)), rotation=0)        # PS0 (6) -> I2C mode
RAIL("GND", pin_at(U8_BASE, (-15.24, -12.7)), rotation=180)     # COM3 (17) addr = 0x28
RAIL("GND", pin_at(U8_BASE, (-15.24, -10.16)), rotation=180)    # COM2 (18) unused in I2C
RAIL("IMU_SCL", pin_at(U8_BASE, (-15.24, -7.62)), rotation=180)  # COM1 (19)
RAIL("IMU_SDA", pin_at(U8_BASE, (-15.24, -5.08)), rotation=180)  # COM0 (20)
RAIL("IMU_INT", pin_at(U8_BASE, (-15.24, 7.62)), rotation=180)   # INT (14)
NC(pin_at(U8_BASE, (-15.24, 0)))                                 # BL_IND (10) unused

# nBOOT_LOAD_PIN + nRESET pull-ups (10k)
r79a, r79b = R("R79", "10k", (615, 445))
WIRE(r79b, pin_at(U8_BASE, (-15.24, 2.54)))                      # nBOOT (4)
RAIL("PLUS3V3", r79a, rotation=90)
r80a, r80b = R("R80", "10k", (602, 445))
WIRE(r80b, pin_at(U8_BASE, (-15.24, 12.7)))                      # nRESET (11)
RAIL("PLUS3V3", r80a, rotation=90)

# CAP pin: internal LDO bypass (Adafruit reference: 100nF to GND)
c20a, c20b = C("C20", "100nF", (690, 445))
WIRE(c20a, pin_at(U8_BASE, (15.24, -12.7)))                      # CAP (9)
RAIL("GND", c20b, rotation=270)

# Internal oscillator: XIN32/XOUT32 unused. Per the BNO055 datasheet, leave
# them open in internal-clock mode (no external load). Explicit no-connects
# keep ERC clean.
NC(pin_at(U8_BASE, (15.24, 0)))                                  # XIN32 (27) -- internal osc
NC(pin_at(U8_BASE, (15.24, 12.7)))                              # XOUT32 (26) -- internal osc

# Supply decoupling (VDD + VDDIO) + I2C pull-ups (4.7k, 400kHz)
c23a, c23b = C("C23", "100nF", (640, 445))
RAIL("PLUS3V3", c23a, rotation=90)
RAIL("GND", c23b, rotation=270)
c24a, c24b = C("C24", "10uF", (652, 445))
RAIL("PLUS3V3", c24a, rotation=90)
RAIL("GND", c24b, rotation=270)
r77a, r77b = R("R77", "4.7k", (585, 500))
RAIL("PLUS3V3", r77a, rotation=90)
RAIL("IMU_SDA", r77b, rotation=270)
r78a, r78b = R("R78", "4.7k", (572, 500))
RAIL("PLUS3V3", r78a, rotation=90)
RAIL("IMU_SCL", r78b, rotation=270)

TXT("BNO055 mid-line placement (user requirement): geometric center of rotation sensing.\nMag data is calibration-grade only on a motor robot (1A at 5mm ~ Earth field); the\nyaw-rate loop uses the gyro. Fusion runs on-chip (100Hz NDOF) or raw gyro at 523Hz.",
    (600, 560), size=2.0)

# ---------------------------------------------------------------------------
# IR SENSOR ARRAY -- 6 wall sensors (2-layer edition)
# ---------------------------------------------------------------------------
# The 8-channel LINE array and its read-mux (U4 CD74HC4067 + C13 decoupling)
# are REMOVED. Wall sensors read DIRECTLY on ADC1 IO1-6; battery telemetry
# (VBAT/BAT_MID/VBUS) reads DIRECTLY on ADC1 IO7/IO8/IO9 (was mux Y8/Y9/Y10).
TXT("IR SENSOR ARRAY  --  6 wall sensors (direct ADC; line array + mux U4 removed)", (10, 420), size=5)

TXT("ONE HEF4067 (line array only -- user decision 2026-07-15: wall sensors are read\ndirectly on ESP32 ADC1 pins). Each sensor: phototransistor (collector -> 47k pull-up\nto +3V3 AND to its readout node; emitter -> GND) + IR LED (anode -> current-limit\nresistor -> +3V3; cathode -> its GROUP's low-side switch). Emitters are GANGED:\nfront pair / diagonal pair / side pair / all-8 line bank, each on one BSS138 driven\nby its own GPIO (IO15/16/17/14). Firing a wall pair and sampling BOTH its ADC pins\nin the same pulse halves scan time vs the old serial mux walk; read bright, read\nambient (group off), subtract. Current-limit: wall 33R (~50mA pulsed) / line 120R\n(~15mA, latch-capable for line-follow + indicators). UKMARS-practice grouping keeps\nmutually-staring sensors on different groups.",
    (150, 460), size=2.0)

# Re-seed the ref counters so the sensor loop reproduces exactly Q2..Q29,
# R13..R40, D1..D14 regardless of how many parts the module sections above
# used (build_pcb.py and gen_connections.py hardcode these numbers).
_ctr["Q"] = 1
_ctr["R"] = 12
_ctr["D"] = 0

# 2-layer JLCPCB edition: the 8-sensor LINE array is removed (LS1-8 + their
# indicators/emitter group). Only the 6 wall sensors remain (read directly on
# ESP32 ADC1). The mux U4 stays -- it still carries battery telemetry.
SENSOR_NAMES = ["WALL1", "WALL2", "WALL3", "WALL4", "WALL5", "WALL6"]
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
        # PT334-6B: 5mm filtered (black-lens) phototransistor, stocked by
        # Indian marketplaces (hubtronics/rarecomponents/robu black-lens
        # pack) -- replaces SFH 309 FA (ams-OSRAM Last-Time-Buy 2026-12-01).
        # ASSEMBLY TRAP: PT334's LONG lead is the EMITTER (opposite of the
        # long-lead=anode LED instinct).
        photo_fp = "LED_THT:LED_D5.0mm_IRBlack"
        photo_val = "PT334-6B (5mm filtered PT; LONG LEAD = EMITTER; SFH309 base symbol so ERC checks pins)"
        led_fp = "LED_THT:LED_D5.0mm_IRGrey"
        led_val = "IR333-A (Everlight 5mm 940nm 20deg; LD271 base symbol; TSAL6400 is lifecycle-Obsolete at Lion)"
    else:
        photo_fp = photo_val = led_fp = led_val = None  # line: single TCRT5000

    # receiver + pull-up. WALL sensors: node goes STRAIGHT to an ESP32 ADC1
    # pin (label only -- no mux). LINE sensors: node feeds read-mux channel
    # Y0-Y7 (= LINE index).
    if is_wall:
        rx_c, rx_e = SFH309(ref("Q"), (x, row_y), footprint=photo_fp, value=photo_val)
    else:
        # Rev 5.3 (India sourcing): one Vishay TCRT5000 reflective sensor per
        # line channel -- integrated 940nm emitter + DAYLIGHT-FILTERED
        # phototransistor, the commodity part of Indian robotics shops
        # (electronicscomp/robu/robocraze), replacing the hard-to-source
        # 1206 IR pair. With 32mm wheels the underside rides ~9mm off the
        # floor, putting the TCRT face at ~2.4mm -- its datasheet-optimal
        # sensing distance. PC817 base symbol: pins 1=A 2=K 3=E 4=C match
        # the project TCRT5000 footprint.
        LS_BASE = snap((x, row_y))
        g.add_component("Isolator", "PC817", ref("LS"),
                         "TCRT5000 (reflective sensor, filtered PT; PC817 base symbol so ERC checks pins)",
                         LS_BASE, {"1": "", "2": "", "3": "", "4": ""},
                         footprint="n20:TCRT5000")
        rx_c = pin_at(LS_BASE, (7.62, 2.54))     # pin 4 = PT collector
        rx_e = pin_at(LS_BASE, (7.62, -2.54))    # pin 3 = PT emitter
    RAIL("GND", rx_e, rotation=270)
    # pull-up x-aligned with the collector pin -> straight vertical wire
    rp1, rp2 = R(ref("R"), "47k", (rx_c[0], row_y + 15))
    WIRE(rp2, rx_c)
    RAIL("PLUS3V3", rp1, rotation=90)
    RAIL(f"{name}_SENSE", rx_c, rotation=0)
    if not is_wall:
        ch = f"Y{i - 6}"
        RAIL(f"{name}_SENSE", U4[ch], rotation=180 if HEF4067_PINS[ch][0] > 0 else 0)

    # emitter + current-limit resistor; cathode joins its GROUP's switched
    # net (one BSS138 per group, below) instead of a per-sensor switch.
    # limiter x-aligned with the LED anode pin -> straight vertical wire
    if is_wall:
        led_k, led_a = LED_SFH4550(ref("D"), (x + 16, row_y), footprint=led_fp, value=led_val)
    else:
        led_a = pin_at(LS_BASE, (-7.62, 2.54))   # pin 1 = LED anode
        led_k = pin_at(LS_BASE, (-7.62, -2.54))  # pin 2 = LED cathode
    lr1, lr2 = R(ref("R"), "33" if is_wall else "120", (led_a[0], row_y + 15))
    RAIL("PLUS3V3", lr1, rotation=90)
    WIRE(lr2, led_a)
    _grp = ("EMIT_FRONT_K" if i < 2 else "EMIT_DIAG_K" if i < 4 else
            "EMIT_SIDE_K" if i < 6 else "EMIT_LINE_K")
    RAIL(_grp, led_k, rotation=180)

# Line channels no longer consume Q8-15/D7-14 (single TCRT5000 each, LS1-8).
# Re-seed the counters so every later ref keeps its historical number
# (Q16.. group FETs, Q20.. indicator drivers, D15.. indicator LEDs).
_ctr["Q"] = 15
_ctr["D"] = 14

# Group emitter switches: one BSS138 per group (Q16-Q19), gate driven directly
# by an ESP32 GPIO (no demux -- U5 deleted in rev 4). Gate nets idle low.
for _gref, _gate, _knet, _gx in ((None, "WALL_EMIT_FRONT", "EMIT_FRONT_K", 250),
                                  (None, "WALL_EMIT_DIAG", "EMIT_DIAG_K", 320),
                                  (None, "WALL_EMIT_SIDE", "EMIT_SIDE_K", 390)):
    # LINE_EMIT group removed with the line array (2-layer edition).
    _g, _s, _d = QN_BSS138(ref("Q"), (_gx, 620))
    RAIL(_gate, _g, rotation=180)
    RAIL("GND", _s, rotation=270)
    RAIL(_knet, _d, rotation=0)

# LINE-SENSOR INDICATOR LEDs removed with the line array (2-layer edition):
# the 8 D15-D22 / Q20-Q27 / R41-R48 per-line indicators are gone. Wall-sensor
# indicators (below) are retained -- they serve the wall sensors that stay.

# ---------------------------------------------------------------------------
# WALL-SENSOR INDICATOR LEDs (user request 2026-07-15): 6 top-side LEDs, one
# per wall receiver. POLARITY IS INVERTED vs the line indicators: a wall
# REFLECTION pulls the sense node LOW, so these use a P-channel FET (BSS84
# class; Q_PMOS base symbol) -- source at +3V3, gate on the node, drain
# sinking the LED through 1k. Node low (wall present) -> Vgs negative -> LED
# ON = wall seen. Same zero-DC-load gate principle as the line indicators;
# same threshold (not analog) behavior; meaningful while the wall emitters
# are lit (latch a group in debug mode: 2x50mA, inside IR333-A continuous
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

# (Buzzer block lives at the END of the file: its WIRE() call must not shift
# the global dogleg lane counter for any pre-existing wire -- a rev-7.2 lane
# shift silently shorted U8's boot strap to GND until the netlist diff caught it.)
# --- Buzzer (rev 7.2, user request): CMT-8504 magnetic transducer on IO46,
# the ONLY free GPIO (module pad 16). Externally driven at ~4 kHz by LEDC.
# Datasheet: coil 15R typ, operating 1-6 Vo-p -> at 3V3 the peak coil
# current is ~220 mA, so the driver is an MMBT2222A (600 mA) with R81 = 220R
# base drive (12 mA, forced beta ~18 = hard saturation; the datasheet app
# circuit itself uses 180R). D29 1N4148W clamps the coil's turn-off flyback
# into 3V3. STRAP-SAFE: R81 + Q34's B-E junction can only ever pull IO46
# toward GND, which is its required boot-strap state (ROM messaging default);
# the buzzer cannot sound before app init because the pin resets to
# input/pull-down and the NPN needs +0.6 V to conduct.
buz_ctrl1, buz_ctrl2 = R("R81", "220", (560, 345))
RAIL("BUZZ_CTRL", buz_ctrl1, rotation=90)
q34_base = snap((575, 358))
g.add_component("Transistor_BJT", "Q_NPN_BEC", "Q34",
                "MMBT2222A (buzzer low-side driver; Q_NPN_BEC base symbol so ERC checks pins)",
                q34_base, {"1": "", "2": "", "3": ""},
                footprint="Package_TO_SOT_SMD:SOT-23",
                datasheet="https://www.diodes.com/assets/Datasheets/ds30040.pdf")
q34_b = pin_at(q34_base, (-5.08, 0))
q34_e = pin_at(q34_base, (2.54, -5.08))
q34_c = pin_at(q34_base, (2.54, 5.08))
WIRE(buz_ctrl2, q34_b)
RAIL("GND", q34_e, rotation=270)
RAIL("BUZZ_DRV", q34_c, rotation=90)

bz1_base = snap((600, 340))
g.add_component("Device", "Buzzer", "BZ1",
                "CMT-8504-100-SMT (magnetic transducer 8.5mm, 15R coil, 4kHz; pads 3/4 are mechanical dummies)",
                bz1_base, {"1": "", "2": ""},
                footprint="Buzzer_Beeper:MagneticBuzzer_CUI_CMT-8504-100-SMT",
                datasheet="https://www.sameskydevices.com/product/resource/pdf/cmt-8504-100-smt-tr.pdf")
RAIL("PLUS3V3", pin_at(bz1_base, (-2.54, 2.54)), rotation=180)   # pin 1 "+" -> rail
RAIL("BUZZ_DRV", pin_at(bz1_base, (-2.54, -2.54)), rotation=180)  # pin 2 "-" -> collector

d29_base = snap((600, 360))
g.add_component("Device", "D", "D29",
                "1N4148W (flyback clamp across the buzzer coil)",
                d29_base, {"1": "", "2": ""},
                footprint="Diode_SMD:D_SOD-123",
                datasheet="https://www.diodes.com/assets/Datasheets/ds30086.pdf")
RAIL("PLUS3V3", pin_at(d29_base, (-3.81, 0)), rotation=180)   # pin 1 K -> 3V3
RAIL("BUZZ_DRV", pin_at(d29_base, (3.81, 0)), rotation=0)     # pin 2 A -> switched node

# ---------------------------------------------------------------------------
# STATUS / POWER / RGB LEDs (2-layer edition, user request). Added at the END
# (after the buzzer) using shared net labels instead of WIRE() so no dogleg
# lane counter shifts. All good-stock JLC parts.
# ---------------------------------------------------------------------------
TXT("STATUS / POWER / RGB LEDs", (600, 600), size=5)

# Power LED -- always on from +3V3 (dev-board power-good indicator)
_pr1, _pr2 = R("R82", "1k", (610, 640))
RAIL("PLUS3V3", _pr1, rotation=90)
RAIL("PWRLED_A", _pr2, rotation=270)
_pb = snap((610, 620))
g.add_component("LED", "LD271", "D30", "Power LED 0603 green (JLC good-stock)",
                _pb, {"1": "", "2": ""}, footprint="LED_SMD:LED_0603_1608Metric")
RAIL("PWRLED_A", pin_at(_pb, (2.54, 0)), rotation=0)          # anode
RAIL("GND", pin_at(_pb, (-5.08, 0)), rotation=180)           # cathode

# Status LED -- ESP-driven on IO12 (flashing/status, dev-board style)
_sr1, _sr2 = R("R83", "1k", (660, 640))
RAIL("STATUS_LED", _sr1, rotation=90)
RAIL("STATLED_A", _sr2, rotation=270)
_sb = snap((660, 620))
g.add_component("LED", "LD271", "D31", "Status LED 0603 blue (JLC good-stock)",
                _sb, {"1": "", "2": ""}, footprint="LED_SMD:LED_0603_1608Metric")
RAIL("STATLED_A", pin_at(_sb, (2.54, 0)), rotation=0)
RAIL("GND", pin_at(_sb, (-5.08, 0)), rotation=180)

# RGB addressable WS2812B on IO14 (powered from +3V3 so 3.3V data meets the
# 0.7*VDD input threshold; DOUT unused = single LED)
_rb = snap((715, 625))
g.add_component("LED", "WS2812B", "D32", "WS2812B addressable RGB 5050 (JLC good-stock)",
                _rb, {"1": "", "2": "", "3": "", "4": ""},
                footprint="LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm")
RAIL("PLUS3V3", pin_at(_rb, (0, 7.62)), rotation=90)         # 1 VDD
RAIL("GND",     pin_at(_rb, (0, -7.62)), rotation=270)       # 3 VSS
RAIL("RGB_DATA", pin_at(_rb, (-7.62, 0)), rotation=0)        # 4 DIN
NC(pin_at(_rb, (7.62, 0)))                                   # 2 DOUT unused
_rc1, _rc2 = C("C31", "100nF", (690, 650))
RAIL("PLUS3V3", _rc1, rotation=90)
RAIL("GND", _rc2, rotation=270)

with open(r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\micromouse-pcb.kicad_sch", "w", encoding="utf-8", newline="\n") as f:
    f.write(g.render(title="Micromouse PCB"))

print("wrote", len(g.symbol_instances), "components,", len(g.label_instances), "labels,",
      len(g.wires), "wires,", len(g.no_connects), "no-connects,",
      "unique lib symbols:", len(g.lib_symbols_needed))
