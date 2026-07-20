"""THT-variant schematic generator (micromouse-tht). Carrier-board
architecture: ESP32-S3-DevKitC-1 + TB6612 breakout + GY-BNO055 breakout on
female headers; CD74HC4067E in a DIP socket; every other part hand-solder THT.

Mirrors the rev-7.2 SMD design's NET NAMES wherever the circuit carries over
(so the fw pin gates and connection docs port), with these deltas:
  - USB cluster DELETED (the DevKit brings its own USB-C: J7/U6/CC/VBUS gone)
  - LM2596 TO-220 bucks replace AP63203/TPS54302 (ON/OFF# enable logic is
    inverted vs the SMD parts: LOW = ON -- see the switch blocks)
  - piezo buzzer PS1240 replaces the magnetic CMT-8504 (base R -> 1k)
ALL connections are made with global labels (RAIL) -- zero WIRE doglegs, so
the SMD generator's lane-counter geometry trap cannot exist here.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_sch import SchGen, snap, pin_at

g = SchGen("micromouse-tht", paper="A1")

_MPN_STATIC = {
    # Every line Lion-verified 2026-07-20 (tht-variant/BOM-THT.csv is the
    # authority; jellybean DIP mux = Lion-procures despite the OOS page).
    "U1": ("LM2596T-3.3/NOPB", "Texas Instruments"),
    "U7": ("LM2596T-ADJ/NOPB", "Texas Instruments"),
    "U4": ("CD74HC4067E", "Texas Instruments"),
    "Q1": ("IRF9540NPBF", "Infineon"),
    "F1": ("RUEF300", "Littelfuse"),
    "L1": ("RLB0914-330KL", "Bourns"), "L2": ("RLB0914-330KL", "Bourns"),
    "D30": ("1N5822", "onsemi"), "D31": ("1N5822", "onsemi"),
    "D29": ("1N4148", "onsemi"),
    "Q34": ("PN2222A", "onsemi"),
    "BZ1": ("PS1240P02BT", "TDK"),
    "J1": ("B2B-XH-A", "JST"), "J9": ("B3B-XH-A(LF)(SN)", "JST"),
    "J10": ("XT60-M", "AMASS"),
    "J5": ("B6B-ZR(LF)(SN)", "JST"), "J6": ("B6B-ZR(LF)(SN)", "JST"),
    "D40": ("WP154A4SUREQBFZGC", "Kingbright"),
    "D41": ("WP154A4SUREQBFZGC", "Kingbright"),
    "J11": ("PPTC081LFBN-RC", "Sullins"), "J12": ("PPTC081LFBN-RC", "Sullins"),
    "J13": ("PPTC221LFBN-RC", "Sullins"), "J14": ("PPTC221LFBN-RC", "Sullins"),
    "J15": ("PPTC061LFBN-RC", "Sullins"),
    "SW1": ("PTS645VL582LFS", "C&K"), "SW2": ("PTS645VL582LFS", "C&K"),
    "SW3": ("PTS645VL582LFS", "C&K"), "SW4": ("PTS645VL582LFS", "C&K"),
    "SW5": ("EG1218", "E-Switch"), "SW6": ("EG1218", "E-Switch"),
}

def _bom_fields(ref, value, footprint):
    if ref in _MPN_STATIC:
        mpn, mfr = _MPN_STATIC[ref]
        return {"MPN": mpn, "Manufacturer": mfr}
    fp = footprint.rsplit(":", 1)[-1]
    if fp.startswith("TO-92"):
        if "2N7000" in value: return {"MPN": "2N7000", "Manufacturer": "onsemi"}
        if "BS250" in value:  return {"MPN": "BS250P", "Manufacturer": "Diotec"}
    if fp.startswith("LED_D5.0mm_IRBlack"):
        return {"MPN": "PT334-6B", "Manufacturer": "Everlight"}
    if fp.startswith("LED_D5.0mm"):
        return {"MPN": "IR333-A", "Manufacturer": "Everlight"}
    if fp == "TCRT5000":
        return {"MPN": "TCRT5000", "Manufacturer": "Vishay"}
    if fp.startswith("LED_D3.0mm"):
        return {"MPN": "WP710A10ID", "Manufacturer": "Kingbright"}
    if fp.startswith("R_Axial") and value and value[0].isdigit():
        code = value.replace(".", "").upper()
        return {"MPN": f"CFR-25JB-52-{code}", "Manufacturer": "Yageo"}
    if fp.startswith("C_Disc") and value == "100nF":
        return {"MPN": "K104K15X7RF5TL2", "Manufacturer": "Vishay"}
    if fp.startswith("C_Rect") and value == "1uF":
        return {"MPN": "FG28X7R1E105KRT06", "Manufacturer": "TDK"}
    if fp.startswith("CP_Radial") and value.startswith("10uF"):
        return {"MPN": "ECA-1EM100", "Manufacturer": "Panasonic"}
    if fp.startswith("CP_Radial") and value.startswith("220uF"):
        return {"MPN": "EEU-FR1C221", "Manufacturer": "Panasonic"}
    return None

g.field_provider = _bom_fields

# ---------------- helpers (RAIL-only; no WIRE doglegs) -------------------------
def PWR(sym, at): g.add_power_symbol(sym, at)
def RAIL(net, pos, rotation=0): g.add_label(net, pos, rotation=rotation)
def NC(at): g.add_no_connect(at)
def TXT(t, at, size=2.5): g.add_text(t, at, size=size)

def R(ref, value, at, n1, n2):
    base = snap(at)
    g.add_component("Device", "R", ref, value, base, {"1": "", "2": ""},
                    footprint="Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal")
    RAIL(n1, pin_at(base, (0, 3.81)), rotation=90)
    RAIL(n2, pin_at(base, (0, -3.81)), rotation=270)

def C_DISC(ref, value, at, n1, n2):
    base = snap(at)
    g.add_component("Device", "C", ref, value, base, {"1": "", "2": ""},
                    footprint="Capacitor_THT:C_Disc_D7.5mm_W4.4mm_P5.00mm")
    RAIL(n1, pin_at(base, (0, 3.81)), rotation=90)
    RAIL(n2, pin_at(base, (0, -3.81)), rotation=270)

def C_RECT(ref, value, at, n1, n2):
    base = snap(at)
    g.add_component("Device", "C", ref, value, base, {"1": "", "2": ""},
                    footprint="Capacitor_THT:C_Rect_L7.0mm_W2.5mm_P5.00mm")
    RAIL(n1, pin_at(base, (0, 3.81)), rotation=90)
    RAIL(n2, pin_at(base, (0, -3.81)), rotation=270)

def C_ELEC(ref, value, at, n1, n2):
    base = snap(at)
    g.add_component("Device", "C_Polarized", ref, value, base, {"1": "", "2": ""},
                    footprint="Capacitor_THT:CP_Radial_D6.3mm_P2.50mm")
    RAIL(n1, pin_at(base, (0, 3.81)), rotation=90)   # pin 1 = +
    RAIL(n2, pin_at(base, (0, -3.81)), rotation=270)

def NMOS(ref, at, ng, ns, nd, value="2N7000 (TO-92 S-G-D)"):
    base = snap(at)
    g.add_component("Transistor_FET", "Q_NMOS_SGD", ref, value, base,
                    {"1": "", "2": "", "3": ""},
                    footprint="Package_TO_SOT_THT:TO-92_Inline")
    RAIL(ng, pin_at(base, (-5.08, 0)), rotation=180)
    RAIL(ns, pin_at(base, (2.54, -5.08)), rotation=270)
    RAIL(nd, pin_at(base, (2.54, 5.08)), rotation=90)

def PMOS_DGS(ref, at, ng, ns, nd, value="BS250P (TO-92 D-G-S)"):
    base = snap(at)
    g.add_component("Transistor_FET", "Q_PMOS_DGS", ref, value, base,
                    {"1": "", "2": "", "3": ""},
                    footprint="Package_TO_SOT_THT:TO-92_Inline")
    RAIL(ng, pin_at(base, (-5.08, 0)), rotation=180)
    RAIL(ns, pin_at(base, (2.54, -5.08)), rotation=270)
    RAIL(nd, pin_at(base, (2.54, 5.08)), rotation=90)

def DIODE(ref, value, at, nk, na, fp="Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal"):
    base = snap(at)
    g.add_component("Device", "D", ref, value, base, {"1": "", "2": ""}, footprint=fp)
    RAIL(nk, pin_at(base, (-3.81, 0)), rotation=180)
    RAIL(na, pin_at(base, (3.81, 0)), rotation=0)

def CONN(ref, value, at, n, nets, fp):
    """1xN connector; nets[i] applied to pin i+1 (None = NC)."""
    base = snap(at)
    g.add_component("Connector_Generic", f"Conn_01x{n:02d}", ref, value, base,
                    {str(k): "" for k in range(1, n + 1)}, footprint=fp)
    top_y = 2.54 * ((n - 1) // 2)
    for i, net in enumerate(nets):
        pos = pin_at(base, (-5.08, top_y - 2.54 * i))
        if net is None:
            NC(pos)
        elif net == "GND":
            PWR("GND", pos)
        else:
            RAIL(net, pos, rotation=180)

# ================================ POWER =========================================
TXT("THT POWER -- 2S LiPo -> LM2596T-3.3 + LM2596T-ADJ@6.0V (TO-220); ON/OFF# is LOW=ON", (10, 20), size=4)

CONN("J1", "BATT_IN_2S (XH)", (20, 40), 2, ["BATT_RAW", "GND"],
     "Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical")
PWR("PWR_FLAG", pin_at(snap((20, 40)), (-5.08, -2.54)))
CONN("J10", "BATT_IN_XT60 (parallel -- ONE PACK ONLY)", (45, 40), 2, ["BATT_RAW", "GND"],
     "Connector_AMASS:AMASS_XT60-M_1x02_P7.20mm_Vertical")
CONN("J9", "BALANCE_2S (optional)", (70, 40), 3, ["GND", "BAT_MID", "BATT_RAW"],
     "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical")

F1B = snap((95, 40))
g.add_component("Device", "Fuse", "F1", "RUEF300 3A/6A radial PPTC", F1B, {"1": "", "2": ""},
                footprint="Fuse:Fuse_Bourns_MF-RG300")
RAIL("BATT_RAW", pin_at(F1B, (0, 3.81)), rotation=90)
RAIL("F1_OUT", pin_at(F1B, (0, -3.81)), rotation=270)

# reverse-polarity P-FET: battery->DRAIN, load->SOURCE, gate to GND via R1
Q1B = snap((115, 40))
g.add_component("Transistor_FET", "Q_PMOS_GDS", "Q1",
                "IRF9540N (TO-220 G-D-S reverse guard, Vgs +/-20V)", Q1B,
                {"1": "", "2": "", "3": ""},
                footprint="Package_TO_SOT_THT:TO-220-3_Vertical")
RAIL("Q1_G", pin_at(Q1B, (-5.08, 0)), rotation=180)
RAIL("F1_OUT", pin_at(Q1B, (2.54, 5.08)), rotation=90)      # D
RAIL("VM_BATT", pin_at(Q1B, (2.54, -5.08)), rotation=270)   # S
PWR("PWR_FLAG", pin_at(Q1B, (2.54, -5.08)))
R("R1", "100k", (130, 40), "Q1_G", "GND")

C_ELEC("C1", "10uF/25V", (145, 40), "VM_BATT", "GND")
C_DISC("C2", "100nF", (155, 40), "VM_BATT", "GND")

def LM2596(ref, value, at, n_out_sw, n_fb, n_en):
    base = snap(at)
    # base symbol LM2596T-12 instantiated directly (the -3.3/-ADJ variants
    # `extends` it and extends-symbols skip ERC pin checks -- standing
    # workaround); real part in Value. Pins: 1 VIN / 2 OUT / 3 GND / 4 FB /
    # 5 ~ON/OFF (LOW = ON).
    g.add_component("Regulator_Switching", "LM2596T-12", ref, value, base,
                    {str(n): "" for n in range(1, 6)},
                    footprint="Package_TO_SOT_THT:TO-220-5_Vertical",
                    datasheet="https://www.ti.com/lit/ds/symlink/lm2596.pdf")
    RAIL("VM_BATT", pin_at(base, (-12.7, 2.54)), rotation=180)
    RAIL(n_out_sw, pin_at(base, (12.7, -2.54)), rotation=0)
    PWR("GND", pin_at(base, (0, -7.62)))
    RAIL(n_fb, pin_at(base, (12.7, 2.54)), rotation=0)
    RAIL(n_en, pin_at(base, (-12.7, -2.54)), rotation=180)

# 3V3 rail
LM2596("U1", "LM2596T-3.3 (TO-220-5)", (30, 70), "SW_3V3", "PLUS3V3", "PWR_EN")
DIODE("D30", "1N5822 (catch)", (52, 78), "SW_3V3", "GND",
      fp="Diode_THT:D_DO-201AD_P5.08mm_Vertical_CathodeUp")
L1B = snap((62, 70))
g.add_component("Device", "L", "L1", "33uH 3A radial", L1B, {"1": "", "2": ""},
                footprint="Inductor_THT:L_Radial_D9.5mm_P5.00mm_Fastron_07HVP")
RAIL("SW_3V3", pin_at(L1B, (0, 3.81)), rotation=90)
RAIL("PLUS3V3", pin_at(L1B, (0, -3.81)), rotation=270)
PWR("PWR_FLAG", pin_at(L1B, (0, -3.81)))
C_ELEC("C5", "220uF/16V", (75, 70), "PLUS3V3", "GND")
C_DISC("C7", "100nF", (85, 70), "PLUS3V3", "GND")
# SW5: PWR_EN low = ON. R69 pulls PWR_EN up (OFF); slide shorts to GND (ON).
R("R69", "100k", (100, 70), "VM_BATT", "PWR_EN")
SW5B = snap((112, 70))
g.add_component("Switch", "SW_SPDT", "SW5", "PWR ALL (EG1218; toward GND = ON)", SW5B,
                {"1": "", "2": "", "3": ""},
                footprint="Button_Switch_THT:SW_Slide_SPDT_Angled_CK_OS102011MA1Q")
RAIL("PWR_EN", pin_at(SW5B, (5.08, 2.54)), rotation=0)   # common B? symbol SW_SPDT: 2=common
RAIL("PWR_EN", pin_at(SW5B, (-5.08, 0)), rotation=180)
PWR("GND", pin_at(SW5B, (5.08, -2.54)))

# 6V rail (ADJ: Vout = 1.23 * (1 + R73/R74) = 6.03V with 3.9k/1k)
LM2596("U7", "LM2596T-ADJ -> 6.0V (TO-220-5)", (30, 100), "SW_6V", "FB_6V", "MOT_EN")
DIODE("D31", "1N5822 (catch)", (52, 108), "SW_6V", "GND",
      fp="Diode_THT:D_DO-201AD_P5.08mm_Vertical_CathodeUp")
L2B = snap((62, 100))
g.add_component("Device", "L", "L2", "33uH 3A radial", L2B, {"1": "", "2": ""},
                footprint="Inductor_THT:L_Radial_D9.5mm_P5.00mm_Fastron_07HVP")
RAIL("SW_6V", pin_at(L2B, (0, 3.81)), rotation=90)
RAIL("VM_6V", pin_at(L2B, (0, -3.81)), rotation=270)
PWR("PWR_FLAG", pin_at(L2B, (0, -3.81)))
R("R73", "3.9k", (75, 100), "VM_6V", "FB_6V")
R("R74", "1k", (85, 100), "FB_6V", "GND")
C_ELEC("C16", "220uF/16V", (95, 100), "VM_6V", "GND")
C_DISC("C17", "100nF", (105, 100), "VM_6V", "GND")
# motors need BOTH switches: MOT_EN (low=ON) is pulled OFF to VM_BATT; the
# path to GND runs through Q35 (gate = 3V3 rail, so SW5 must be on) AND SW6.
R("R70", "100k", (120, 100), "VM_BATT", "MOT_EN")
NMOS("Q35", (132, 100), "PLUS3V3", "MOT_EN_SW", "MOT_EN")
SW6B = snap((146, 100))
g.add_component("Switch", "SW_SPDT", "SW6", "PWR MOTORS (EG1218; toward GND = ON)", SW6B,
                {"1": "", "2": "", "3": ""},
                footprint="Button_Switch_THT:SW_Slide_SPDT_Angled_CK_OS102011MA1Q")
RAIL("MOT_EN_SW", pin_at(SW6B, (5.08, 2.54)), rotation=0)
RAIL("MOT_EN_SW", pin_at(SW6B, (-5.08, 0)), rotation=180)
PWR("GND", pin_at(SW6B, (5.08, -2.54)))

# battery telemetry (same dividers as rev 7.2)
R("R2", "100k", (170, 40), "VM_BATT", "VBAT_SENSE")
R("R3", "39k", (180, 40), "VBAT_SENSE", "GND")
C_DISC("C6", "100nF", (190, 40), "VBAT_SENSE", "GND")
R("R75", "100k", (205, 40), "BAT_MID", "BAT_MID_SENSE")
R("R76", "100k", (215, 40), "BAT_MID_SENSE", "GND")
C_DISC("C19", "100nF", (225, 40), "BAT_MID_SENSE", "GND")

# ============================ CONTROLLER SOCKET =================================
TXT("CONTROLLER -- ESP32-S3-DevKitC-1-N8R2 on two 1x22 sockets (its own USB-C flashes it)", (10, 135), size=4)
# left row J13 (DevKitC-1 v1.x silk order, top->bottom)
# rev THT-2: line-follower array + mux REMOVED (this is a wall-following
# micromouse; the line array/mux was ~50 parts and drove the board over its
# footprint). Battery telemetry (VBAT_SENSE, BAT_MID_SENSE) now goes DIRECT to
# two DevKit ADC1 pins (the old mux-sense/select pins); the freed pins are NC.
CONN("J13", "DEVKIT_LEFT", (30, 180), 22,
     ["PLUS3V3", "PLUS3V3", "ESP_RST", "WALL4_SENSE", "WALL5_SENSE", "WALL6_SENSE",
      "VBAT_SENSE", "WALL_EMIT_FRONT", "WALL_EMIT_DIAG", "WALL_EMIT_SIDE",
      "IMU_SDA", "BAT_MID_SENSE", "WALL3_SENSE", "BUZZ_CTRL", "AIN1", "AIN2",
      "RGB1_R", "RGB1_G", "RGB1_B", "RGB2_R", "RGB2_G", "GND"],
     "Connector_PinSocket_2.54mm:PinSocket_1x22_P2.54mm_Vertical")
# right row J14. rev THT-2: external JTAG header (J8) DROPPED -- the DevKit has
# built-in USB-Serial-JTAG, so an external JTAG connector is redundant. Its 4
# GPIO (IO39-42) are freed: one carries the 6th RGB channel, three are spare.
CONN("J14", "DEVKIT_RIGHT", (70, 180), 22,
     ["GND", "ENC2_B_S3", "ENC2_A_S3", "WALL1_SENSE", "WALL2_SENSE",
      "RGB2_B", None, None, None, "BIN1", "IMU_INT",
      "USER_BTN3", "USER_BTN2", "USER_BTN", "BIN2", "ENC1_B", "ENC1_A",
      "IMU_SCL", None, None, "GND", "GND"],
     "Connector_PinSocket_2.54mm:PinSocket_1x22_P2.54mm_Vertical")

# 2x RGB indicator LEDs (common cathode, ESP-driven, rev THT-2). Kingbright
# WP154A4SUREQBFZGC 5mm 4-pin. Each anode via a limiter to a DevKit GPIO;
# common cathode to GND. NOTE: green/blue Vf (~3.0V) leaves little headroom
# from 3.3V -- G/B run dimmer than red (fine for a status indicator). Drive
# with LEDC PWM for colour mixing.
for _n in (1, 2):
    base = snap((70 + _n * 20, 120))
    g.add_component("Device", "LED_RKGB", f"D{39 + _n}",
                    "WP154A4SUREQBFZGC (5mm common-cathode RGB)", base,
                    {"1": "", "2": "", "3": "", "4": ""},
                    footprint="LED_THT:LED_D5.0mm-4_RGB")
    RAIL(f"RGB{_n}_RA", pin_at(base, (5.08, 5.08)), rotation=0)   # pin1 red anode
    PWR("GND", pin_at(base, (-5.08, 0)))                          # pin2 common K
    RAIL(f"RGB{_n}_GA", pin_at(base, (5.08, 0)), rotation=0)      # pin3 green anode
    RAIL(f"RGB{_n}_BA", pin_at(base, (5.08, -5.08)), rotation=0)  # pin4 blue anode
    R(f"R{200 + _n*3 - 2}", "180", (70 + _n*20 + 12, 125), f"RGB{_n}_R", f"RGB{_n}_RA")
    R(f"R{200 + _n*3 - 1}", "68", (70 + _n*20 + 12, 120), f"RGB{_n}_G", f"RGB{_n}_GA")
    R(f"R{200 + _n*3}", "68", (70 + _n*20 + 12, 115), f"RGB{_n}_B", f"RGB{_n}_BA")
TXT("DevKit is powered from PLUS3V3 (3V3 pins). CAUTION: do not run motors while\nits USB is plugged AND battery on -- same procedure table as the SMD board.\n5V pin NC. IO19/20 (USB D+/-) NC -- flashing uses the DevKit's own connector.", (10, 215), size=2.0)

# straps / buttons
R("R65", "10k", (110, 180), "BIN2", "GND")       # IO45 VDD_SPI strap insurance
R("R10", "10k", (120, 180), "PLUS3V3", "USER_BTN")
for ref, net, x, lbl in (("SW1", "USER_BTN", 132, "BTN_A (start/BOOT)"),
                          ("SW3", "USER_BTN2", 146, "BTN_B"),
                          ("SW4", "USER_BTN3", 160, "BTN_C"),
                          ("SW2", "ESP_RST", 174, "RESET")):
    B = snap((x, 180))
    g.add_component("Switch", "SW_Push", ref, lbl, B, {"1": "", "2": ""},
                    footprint="Button_Switch_THT:SW_PUSH_6mm")
    RAIL(net, pin_at(B, (-5.08, 0)), rotation=180)
    PWR("GND", pin_at(B, (5.08, 0)))

# (external JTAG header J8 REMOVED, rev THT-2: the DevKit's built-in
#  USB-Serial-JTAG covers flashing + debug; freed IO39-42 for RGB + spares)

# ============================ MOTOR DRIVER SOCKET ===============================
TXT("MOTOR DRIVER -- TB6612FNG breakout on two 1x8 sockets (SparkFun pin order; dry-fit!)", (10, 240), size=4)
CONN("J11", "TB6612_SIGNALS (PWMA,AIN2,AIN1,STBY,BIN1,BIN2,PWMB,GND)", (30, 270), 8,
     ["PLUS3V3", "AIN2", "AIN1", "PLUS3V3", "BIN1", "BIN2", "PLUS3V3", "GND"],
     "Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical")
CONN("J12", "TB6612_POWER (VM,VCC,GND,A01,A02,B02,B01,GND)", (70, 270), 8,
     ["VM_6V", "PLUS3V3", "GND", "MOTA_P", "MOTA_N", "MOTB_N", "MOTB_P", "GND"],
     "Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical")

# motor connectors: JST ZH direct-plug, robu cable order (rev 7.2 pinout)
CONN("J5", "MOTOR_A (M1,VCC,C1,C2,GND,M2)", (110, 270), 6,
     ["MOTA_P", "PLUS3V3", "ENC1_A", "ENC1_B", "GND", "MOTA_N"],
     "Connector_JST:JST_ZH_B6B-ZR_1x06_P1.50mm_Vertical")
CONN("J6", "MOTOR_B (M1,VCC,C1,C2,GND,M2)", (140, 270), 6,
     ["MOTB_P", "PLUS3V3", "ENC2_A", "ENC2_B", "GND", "MOTB_N"],
     "Connector_JST:JST_ZH_B6B-ZR_1x06_P1.50mm_Vertical")
R("R6", "10k", (170, 265), "PLUS3V3", "ENC1_A")
R("R7", "10k", (180, 265), "PLUS3V3", "ENC1_B")
R("R8", "10k", (190, 265), "PLUS3V3", "ENC2_A")
R("R9", "10k", (200, 265), "PLUS3V3", "ENC2_B")
# UART0 boot-contention guards (IO43/44 print ROM messages at every boot)
R("R57", "1k", (212, 265), "ENC2_A", "ENC2_A_S3")
R("R58", "1k", (222, 265), "ENC2_B", "ENC2_B_S3")

# ================================ IMU SOCKET ====================================
TXT("IMU -- GY-BNO055 breakout on a 1x6 socket (match YOUR module's pin order; ADR for 0x28)", (10, 295), size=4)
CONN("J15", "GY-BNO055 (VIN,GND,SCL,SDA,INT,ADR)", (30, 320), 6,
     ["PLUS3V3", "GND", "IMU_SCL", "IMU_SDA", "IMU_INT", None],
     "Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical")
R("R77", "4.7k", (60, 320), "PLUS3V3", "IMU_SDA")
R("R78", "4.7k", (70, 320), "PLUS3V3", "IMU_SCL")

# ================================ BUZZER ========================================
BZB = snap((95, 320))
g.add_component("Device", "Buzzer", "BZ1", "PS1240P02BT piezo (THT)", BZB,
                {"1": "", "2": ""}, footprint="Buzzer_Beeper:Buzzer_12x9.5RM7.6")
RAIL("PLUS3V3", pin_at(BZB, (-2.54, 2.54)), rotation=180)
RAIL("BUZZ_DRV", pin_at(BZB, (-2.54, -2.54)), rotation=180)
Q34B = snap((110, 320))
g.add_component("Transistor_BJT", "Q_NPN_EBC", "Q34", "PN2222A (TO-92 E-B-C)", Q34B,
                {"1": "", "2": "", "3": ""},
                footprint="Package_TO_SOT_THT:TO-92_Inline")
RAIL("BUZZ_B", pin_at(Q34B, (-5.08, 0)), rotation=180)
RAIL("GND", pin_at(Q34B, (2.54, -5.08)), rotation=270)
RAIL("BUZZ_DRV", pin_at(Q34B, (2.54, 5.08)), rotation=90)
R("R81", "1k", (125, 320), "BUZZ_CTRL", "BUZZ_B")
DIODE("D29", "1N4148", (138, 320), "PLUS3V3", "BUZZ_DRV")

# ============================ (LINE ARRAY + MUX REMOVED, rev THT-2) ============
# The 8x TCRT5000 line array, its CD74HC4067 mux, per-channel limiters/pull-ups,
# line-emitter gate (Q19/R61) and line indicators are all deleted for the THT
# variant -- a micromouse wall-follows, and those ~50 parts pushed the board
# past its footprint. Battery telemetry moved to direct DevKit ADC pins above.

# ============================ WALL SENSORS ======================================
TXT("WALL SENSORS -- 6x IR333-A + PT334-6B (0/45/90 deg pairs), 3 banked emitter gates", (10, 440), size=4)
_wall_bank = {1: "FRONT", 2: "FRONT", 3: "DIAG", 4: "DIAG", 5: "SIDE", 6: "SIDE"}
for k in range(1, 7):
    x = 25 + (k - 1) * 32
    bank = _wall_bank[k]
    DB = snap((x, 470))
    g.add_component("LED", "LD271", f"D{k}",
                    "IR333-A (LD271 base symbol so ERC checks pins)", DB,
                    {"1": "", "2": ""}, footprint="LED_THT:LED_D5.0mm_IRGrey")
    RAIL(f"EMIT_{bank}_K", pin_at(DB, (-5.08, 0)), rotation=180)     # K
    RAIL(f"Net-(D{k}-A)", pin_at(DB, (2.54, 0)), rotation=0)         # A
    R(f"R{130+k}", "33", (x, 485), "PLUS3V3", f"Net-(D{k}-A)")
    QB = snap((x + 14, 470))
    g.add_component("Sensor_Optical", "SFH309", f"Q{k+1}",
                    "PT334-6B (SFH309 base symbol so ERC checks pins)", QB,
                    {"1": "", "2": ""}, footprint="LED_THT:LED_D5.0mm_IRBlack")
    RAIL(f"WALL{k}_SENSE", pin_at(QB, (2.54, 5.08)), rotation=90)    # C
    PWR("GND", pin_at(QB, (2.54, -5.08)))                            # E
    R(f"R{140+k}", "47k", (x + 14, 485), "PLUS3V3", f"WALL{k}_SENSE")
for bank, gate, x in (("FRONT", "WALL_EMIT_FRONT", 220), ("DIAG", "WALL_EMIT_DIAG", 236),
                      ("SIDE", "WALL_EMIT_SIDE", 252)):
    NMOS({"FRONT": "Q16", "DIAG": "Q17", "SIDE": "Q18"}[bank], (x, 470),
         gate, "GND", f"EMIT_{bank}_K")
    R({"FRONT": "R62", "DIAG": "R63", "SIDE": "R64"}[bank], "100k", (x, 487),
      gate, "GND")

# ============================ INDICATORS ========================================
TXT("INDICATORS -- LED ON = wall seen: 6 wall channels (BS250P + 1k + 3mm LED)", (10, 510), size=4)
for k in range(1, 7):
    x = 25 + (k - 1) * 20
    PMOS_DGS(f"Q{120+k}", (x, 535), f"WALL{k}_SENSE", "PLUS3V3", f"WIND{k}")
    R(f"R{150+k}", "1k", (x, 552), f"WIND{k}", f"WLED{k}")
    DIODE(f"D{120+k}", "LED red 3mm", (x, 566), "GND", f"WLED{k}",
          fp="LED_THT:LED_D3.0mm")
# (line-channel indicators D131-138 / Q131-138 / R161-168 removed with the array)

with open(r"D:\Projects\micromouse-pcb\tht-assembly\pcb\micromouse-tht.kicad_sch",
          "w", encoding="utf-8", newline="\n") as f:
    f.write(g.render(title="Micromouse THT Carrier"))
print("wrote", len(g.symbol_instances), "components,", len(g.label_instances), "labels,",
      len(g.wires), "wires,", len(g.no_connects), "no-connects,",
      "libs:", len(g.lib_symbols_needed))
