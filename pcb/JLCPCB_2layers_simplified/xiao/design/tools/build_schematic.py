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
    # XIAO REVISION: U3 is now the Seeed XIAO nRF52840 Sense Plus module
    # (SKU 102010694) -- a whole pre-built, pre-reflowed module, NOT a raw
    # component. It has no JLCPCB/LCSC or Lion Circuits turnkey-assembly part
    # number (it isn't a bare-die/bare-package part their pick-and-place can
    # place from tape/reel). FLAG FOR REVIEW / BOM: hand-place + hand-solder
    # this module onto its footprint AFTER the rest of the board comes back
    # from JLC/Lion SMT assembly -- it is explicitly excluded from the
    # turnkey assembly service line items.
    "U3": ("102010694 (Seeed XIAO nRF52840 Sense Plus -- HAND-SOLDER, NOT part of turnkey SMT assembly)", "Seeed Studio"),
    # 6V motor buck (restored, XIAO revision -- see POWER section): reuses
    # the ORIGINAL (pre-simplification) full board's exact proven part.
    "U7": ("TPS54302DDCR", "Texas Instruments"),           # 6V motor buck, 3A, 28V in
    "Q1": ("DMP3098L-7", "Diodes Incorporated"),           # -30V/-3.8A/Vgs +/-20V (2S-safe gate)
    "L1": ("SRP4020TA-4R7M", "Bourns"),
    "L2": ("SRP4020TA-4R7M", "Bourns"),                    # 6V buck inductor, same part as L1
    # Rev 8 (2026-07-21): "MINISMDC350F/16-2" is not a real orderable
    # Littelfuse part at any distributor/LCSC/Lion checked -- looks like a
    # long-standing typo. The schematic's own FUSE() value ("2.6A/16V PPTC",
    # below) matches the REAL part MINISMDC260F/16-2 exactly (confirmed in
    # stock at LCSC C16490 and listed at Lion Circuits) -- corrected to that.
    # FLAG FOR REVIEW: this comment previously said "3.5A hold/7A trip" (rev
    # 7.1 stall-headroom note) which does NOT match the 2.6A value string --
    # unresolved discrepancy, re-verify actual required hold current.
    "F1": ("MINISMDC260F/16-2", "Littelfuse"),
    "J1": ("B2B-XH-A", "JST"),                             # 2S battery main (XH: 3A/contact)
    "SW5": ("PCM12SMTR", "C&K"), "SW6": ("PCM12SMTR", "C&K"),  # rev 9: restored motor switch
    "SW7": ("PCM12SMTR", "C&K"),  # 6V/7.5V toggle, same part reused as SPST
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
    # XIAO REVISION: J8 (JTAG), J7 (external USB-C), the WS2812B RGB LED
    # (D32), the BMI160 IMU (U8), the reset button (SW4/R11/C9), and the
    # per-wall-sensor indicator LEDs are all gone -- the XIAO module
    # provides its own IMU, RGB LED, USB-C port, and reset/bootloader
    # button, so none of that circuitry belongs on the carrier board anymore.
    # The plain power/motor-rail indicator LEDs (D30/D33) are KEPT (they
    # don't consume a GPIO); the ESP-driven status LED (D31, ex-IO12) is
    # REMOVED -- with the 20-signal/20-pin XIAO budget an exact fit, there is
    # no spare GPIO to drive a dedicated status LED, and the module's own
    # onboard RGB LED already covers that role in firmware.
    # Rev 8 (2026-07-21): swapped THT PTS645VL582LFS -> SMD KMR221NGLFS --
    # the THT part went out of stock; SMD also drops it from the
    # hand-solder list entirely (reflow only). Same 2-net (pad"1"/pad"2")
    # topology, so no schematic rewiring needed, only the footprint+MPN.
    # (First attempt used TL3301AF160QG, but its ~11.2mm gull-wing lead span
    # overlapped/shorted adjacent buttons on this board's 10mm button pitch
    # -- caught via DRC courtyard/shorting errors. KMR221NGLFS's ~5mm pad
    # span fits the pitch with margin; 2N/50mA/32V comfortably covers the
    # 12V/50mA design need.)
    "SW1": ("KMR221NGLFS", "C&K"), "SW2": ("KMR221NGLFS", "C&K"),
    "C30": ("EEE-FT1C221AP", "Panasonic"),                 # 220uF/16V SMD alu (motor bulk)
}
# Rev 8 (2026-07-21): per-value override for the generic Yageo R_0805 formula
# below, for values where the Yageo part isn't a clean dual-vendor (JLCPCB +
# Lion Circuits) common part. Only "10k" has a confirmed common replacement
# (Walsin, in stock at both) -- 47k/220k/110k/11k had no common part found
# after checking multiple manufacturers at both vendors (2026-07-21), so
# those stay on the Yageo formula (real MPN, in stock at Lion; JLC-side
# still substitutes via jlcpcb_lcsc_map.py as it already did before this
# audit) -- a documented per-vendor exception, not a unified part.
_RES_MPN = {
    "10k": ("WR08X1002FTL", "Walsin"),
}
_CAP_MPN = {
    # 0805 X7R/X5R unless noted. 2S rails (VM_BATT, 8.4V max) must use
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
    if fp.startswith("R_0805") and value in _RES_MPN:
        mpn, mfr = _RES_MPN[value]
        return {"MPN": mpn, "Manufacturer": mfr}
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

def SWPUSH(ref, at, value="SW_Push",
           footprint="Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2"):
    base = snap(at)
    g.add_component("Switch", "SW_Push", ref, value, base, {"1": "", "2": ""}, footprint=footprint)
    return pin_at(base, (-5.08, 0)), pin_at(base, (5.08, 0))

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

# ---------------------------------------------------------------------------
# XIAO nRF52840 Sense Plus module (U3) -- generic multi-pin symbol.
#
# There is no stock KiCad schematic symbol for this module, so (same trick
# the project already uses nowhere else, but the same PRINCIPLE as
# CONN_COL()'s generic single-row connector below) we instantiate a plain
# Connector_Generic:Conn_01x23 symbol -- 23 pins in one schematic column --
# and rely ENTIRELY on the real footprint (xiao:XIAO-nRF52840-Plus-SMD) for
# physical pad geometry. The schematic symbol's pin NUMBERS ("1".."23") are
# what matter: they must equal the real footprint's pad numbers 1-23 so
# build_pcb.py's netlist-driven pad->net mapping lands correctly. Pads 24-29
# on the real footprint (module-internal USB-C shield tabs + an onboard
# 2-pin LiPo JST connector -- confirmed present in Seeed's own .kicad_mod,
# not used by this design) are simply absent from this pin list; they load
# on the PCB with no net, which is correct (nothing on the carrier board
# needs them).
#
# PAD MAP (all 23 pins; D-pin identity per pad number is an ASSUMPTION --
# see the header comment block below and the final report: Seeed's assembled
# .kicad_mod gives pad NUMBERS and XY geometry, confirmed exactly against
# the spec, but not which pad number is electrically which D-pin/GPIO. This
# uses the standard, widely-documented sequential XIAO pin-table convention
# (pad1=D0, pad2=D1, ... pad11=D10, pad12=GND, pad13=5V, pad14=3V3; Plus
# pads 15-23 = the 9 extra GPIOs, no fixed D-number needed since the user
# spec frees their assignment). FLAG FOR REVIEW: verify against a real
# board/continuity-meter before fab.
#   1 D0(ADC) 2 D1(ADC) 3 D2(ADC) 4 D3(ADC) 5 D4(ADC) 6 D5(ADC) 7 D6 8 D7
#   9 D8 10 D9 11 D10 12 GND 13 5V(unused) 14 3V3
#   15-20 Plus pads (-Y edge) 21-23 Plus pads (+Y edge) -- all digital GPIO
# ---------------------------------------------------------------------------
_XIAO_N = 23
_XIAO_TOPY = 2.54 * ((_XIAO_N - 1) // 2)
XIAO_PIN_OFFSET = {str(n): (-5.08, _XIAO_TOPY - 2.54 * (n - 1)) for n in range(1, _XIAO_N + 1)}

def XIAO(ref, at, footprint="xiao:XIAO-nRF52840-Plus-SMD"):
    base = snap(at)
    g.add_component("Connector_Generic", f"Conn_01x{_XIAO_N:02d}", ref,
                     "Seeed XIAO nRF52840 Sense Plus (SKU 102010694): D0-D5 ADC-capable, "
                     "D6-D10 + 9 Plus pads digital-only. Own onboard IMU/RGB LED/USB-C/reset button.",
                     base, {str(n): "" for n in range(1, _XIAO_N + 1)}, footprint=footprint,
                     datasheet="https://wiki.seeedstudio.com/XIAO_BLE/")
    return {str(n): pin_at(base, XIAO_PIN_OFFSET[str(n)]) for n in range(1, _XIAO_N + 1)}

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
# POWER SECTION -- XIAO revision: 2S LiPo -> AP63203 (3V3, 2A) logic rail +
# RESTORED TPS54302 6.0V/3A motor buck (VM_6V). This reverses the ESP32
# cost-reduced variant's removal of the 6V rail: the user's explicit
# requirement here is a REGULATED, CONSTANT 6.0V motor supply whenever the
# battery is above 6V, not raw/switched battery voltage through a FET. The
# TPS54302 block + its SW6 EN-divider gating is copied verbatim (same part,
# same FB values, same wiring pattern) from the ORIGINAL (pre-simplification)
# full board's build_schematic.py. Two slide switches: SW5 enables everything
# (3V3 buck EN); SW6 separately gates the 6V buck's EN pin (a low-current
# logic signal -- SW6 never carries motor current) so logic+sensors can run
# with the motors off. No onboard charger: a 2S pack charges on an external
# balance charger.
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

# Balance tap + per-cell monitoring REMOVED (user, keep it simple): no J9
# connector, no BAT_MID divider. XIAO revision: battery voltage sense
# (VBAT_SENSE) is ALSO removed entirely (not just per-cell) -- it does not
# fit in the 6-ADC-pin budget once all 6 wall sensors occupy D0-D5, the only
# ADC-capable pins on this module. This is a deliberate, accepted gap (no
# battery-level telemetry in firmware); flagged in the final report.

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

# Output cap: 22uF (10V class is fine on the 3.3V rail) -- AP63203's own
# typical application circuit calls for a single output cap in this range;
# rev 9 (2026-07-23) passives-reduction pass removed the old C7, a second
# 22uF a few mm away on the SAME net with no distinct role from C5 (unlike
# the input side's C1(bulk)/C2(HF), which serve genuinely different jobs).
c5p1, c5p2 = C("C5", "22uF", (285, 150))
RAIL("PLUS3V3", c5p1, rotation=90)
RAIL("GND", c5p2, rotation=270)

# SW5 = master soft switch (logic power switch): R69 pulls PWR_EN to the
# battery rail (AP63203 EN is VIN-tolerant); PCM12SMTR slide grounds it =
# everything (logic side) off.
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

TXT("+3V3 is the regulated logic rail: XIAO module, encoder VCC, PT pull-ups, and IR LED\ncurrent. VM_6V (TPS54302, 3A limit) feeds ONLY the TB6612 VM pins -- a REGULATED,\nconstant 6.0V whenever VM_BATT is above ~6V (restored per user requirement; the ESP32\ncost-reduced variant's raw-battery-through-a-FET motor supply is NOT used here).",
    (200, 100), size=2.2)

# --- 6V MOTOR RAIL (RESTORED, XIAO revision): TPS54302 (SOT-23-6, 3A,
# 4.5-28V in, 400kHz), copied verbatim from the ORIGINAL (pre-simplification)
# full board's build_schematic.py -- same part, same FB divider values, same
# wiring pattern; only the placement coordinates are adapted to this
# schematic sheet. FB divider 100k/11k -> 0.596V x (1+100/11) = 6.01V.
# Motors therefore see a REGULATED 6.0V with the buck's 3A current limit as a
# hard supply-side ceiling (per-channel limits are TB6612's own). Pinout:
# 1 GND / 2 SW / 3 VIN / 4 FB / 5 EN / 6 BOOT.
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

# FB divider (6.01V baseline)
r73a, r73b = R("R73", "100k", (315, 230))
RAIL("VM_6V", r73a, rotation=90)
RAIL("FB_6V", r73b, rotation=270)
r74a, r74b = R("R74", "11k", (325, 230))
RAIL("FB_6V", r74a, rotation=90)
RAIL("GND", r74b, rotation=270)

# 6V/7.5V output toggle (user requirement): R85 (40.2k) in series with SW7
# (a plain on/off toggle) connects in PARALLEL with R74 when closed. Reuses
# the SAME PCM12SMTR part already qualified for SW5/SW6 (just wired as a
# simple 2-terminal SPST -- third pin left NC) rather than introducing a new
# switch part, per the "keep circuits simple" brief.
#   Toggle OPEN (default): R74 alone (11k) -> Vout = 0.596*(1+100/11) = 6.01V
#   Toggle CLOSED: R74 || R85 = 11k||40.2k = 8.637k
#                  -> Vout = 0.596*(1+100/8.637) = 7.50V
# Verified against this same divider's own 0.596V reference (already implied
# by the 100k/11k->6.01V figure above). NOTE (physical limitation, not a
# bug): the 7.5V setting only stays fully regulated while VM_BATT is above
# roughly 7.8-8.0V (buck dropout headroom); as the pack discharges below
# that, this setting progressively droops toward the raw battery voltage
# instead of holding a hard 7.5V.
r85a, r85b = R("R85", "40.2k", (335, 230))
RAIL("FB_6V", r85a, rotation=90)
SW7_BASE = snap((345, 230))
g.add_component("Switch", "SW_SPDT", "SW7",
                 "6V/7.5V toggle (PCM12SMTR reused as SPST; 3rd pin NC)", SW7_BASE,
                 {"1": "", "2": "", "3": ""},
                 footprint="Button_Switch_SMD:SW_SPDT_PCM12")
WIRE(r85b, pin_at(SW7_BASE, (-5.08, 0)))
RAIL("GND", pin_at(SW7_BASE, (5.08, 2.54)), rotation=0)
NC(pin_at(SW7_BASE, (5.08, -2.54)))

# SW6 = motor enable. The pull-up feeds from PWR_EN (NOT VM_BATT): motors can
# only be enabled when SW5 is already on -- "SW6 enables supply to motors
# ALSO". The R69/R70/R71 string (100k/220k/110k) puts the TPS54302 EN at
# 1.69-2.15V across the pack window: above the worst-case 1.31V rising
# threshold, far below any absolute limit. SW6 shorts MOT_EN to GND = off.
# SW6 only ever switches this microamp-level logic signal, never real motor
# current -- unlike the ESP32 variant's Q35 FET scheme, no series power FET
# is needed here at all.
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

# Battery voltage sense (VBAT_SENSE divider: R2/R3/C6 in earlier revisions)
# REMOVED ENTIRELY (XIAO revision, user-confirmed accepted gap): it does not
# fit in the 6-ADC-pin budget once all 6 wall sensors occupy D0-D5, the only
# ADC-capable pins on the XIAO module. No pack-level battery telemetry exists
# in this design; firmware has no ADC-based low-battery cutoff. BAT_MID
# divider (per-cell) was already removed with J9 in earlier revisions.

TXT("Battery voltage sense is NOT implemented in this design (accepted gap, XIAO\nrevision): the 6 wall sensors already consume all 6 ADC-capable pins (D0-D5) on\nthe module, so no ADC pin remains for VBAT_SENSE. The 6V motor rail (TPS54302)\nstays in regulation as long as VM_BATT is above ~6V; below that it degrades\ntoward VM_BATT (normal buck dropout behavior).",
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
# IN/IN PWM mode: PWMA/PWMB tied HIGH (permanent), the four IN pins carry
# direct GPIO PWM from the XIAO module. STBY tied HIGH through R55 (a
# soft/logic-level kill, unchanged): the HARDWARE motor kill is SW6 (cuts the
# TPS54302's EN, dropping VM_6V) and SW5 (cuts all power, logic included);
# TB6612's IN pins also have internal pull-downs, so a held-in-reset MCU
# leaves the outputs off.
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

# VM decoupling for the regulated 6V rail: C30 220uF/16V alu bulk (hot-loop,
# standards item) + 10uF/25V + 100nF ceramics at the pins -- this is where
# the TB6612's own decoupling needs to sit, per the Toshiba application
# circuit.
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

TXT("Bare TB6612FNG (U2, SSOP-24) in IN/IN PWM mode: PWMA/PWMB tied 3V3, AIN/BIN = direct\nGPIO PWM from the XIAO module (IN1=PWM,IN2=0 fwd-coast; IN1=PWM,IN2=1 rev-brake). VM =\nVM_6V, the RESTORED TPS54302-regulated 6.0V/3A motor rail (SW6-gated EN); STBY pulled\nhigh (R55) -- hardware motor kill = SW6 + SW5 + IN pins' internal pull-downs.\nDecoupling: C30 220uF/16V alu + C11 10uF/25V + C12 100nF on VM, C14 on VCC.",
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
# CONTROLLER -- Seeed XIAO nRF52840 Sense Plus module (U3), the SOLE
# controller. REPLACES the ESP32-S3-WROOM-1 entirely: the module's own
# onboard LSM6DS3TR-C IMU, simple RGB LED, native USB-C port, and
# reset/UF2-bootloader button provide everything those separate ESP32-era
# parts (U8/D32/J7/SW4 + their support circuitry) used to -- NONE of that
# needs any circuitry on this carrier board anymore.
#
# Every signal is a DIRECT native XIAO GPIO pin -- NO I2C GPIO expander, NO
# analog mux, NO shared/switched pins anywhere in this design (final,
# locked decision). Exactly 20 signals on 20 of the 23 available pins (11
# usable on the front header D0-D10 + 9 Plus pads; the 3 remaining main-
# header pins are GND/5V(unused)/3V3). The 6 ADC-needing wall-sensor signals
# are on D0-D5, the ONLY ADC-capable pins; everything else (14 signals) is
# on D6-D10 + the 9 Plus pads.
#
# PAD MAP / PIN ASSIGNMENT (see the XIAO() pad-map comment above for the
# pad-number <-> D-pin identity assumption; this is the actual per-signal
# assignment used in this design):
#   pad1  D0  WALL_FL_SENSE (ADC)   pad2  D1  WALL_FR_SENSE (ADC)
#   pad3  D2  WALL_DL_SENSE (ADC)   pad4  D3  WALL_DR_SENSE (ADC)
#   pad5  D4  WALL_SL_SENSE (ADC)   pad6  D5  WALL_SR_SENSE (ADC)
#   pad7  D6  AIN1   pad8  D7  AIN2   pad9  D8  BIN1   pad10 D9  BIN2
#   pad11 D10 BUZZ_CTRL
#   pad12 GND   pad13 5V (module's own USB VBUS output pin -- unused, NC)
#   pad14 3V3 (fed FROM this board's AP63203 3V3 rail)
#   pad15 Plus1 ENC1_A   pad16 Plus2 ENC1_B
#   pad17 Plus3 ENC2_A   pad18 Plus4 ENC2_B
#   pad19 Plus5 WALL_EMIT_FRONT   pad20 Plus6 WALL_EMIT_DIAG
#   pad21 Plus7 WALL_EMIT_SIDE
#   pad22 Plus8 USER_BTN   pad23 Plus9 USER_BTN2
TXT("CONTROLLER  --  Seeed XIAO nRF52840 Sense Plus (SKU 102010694): 20 signals on 20\ndirect native GPIO pins, exact fit. Own onboard IMU/RGB LED/USB-C/reset button.", (300, 230), size=5)

XIAO_NET = {  # module pad -> net (None = explicit no-connect)
    "1": "WALL_FL_SENSE", "2": "WALL_FR_SENSE", "3": "WALL_DL_SENSE",     # D0-D2 (ADC)
    "4": "WALL_DR_SENSE", "5": "WALL_SL_SENSE", "6": "WALL_SR_SENSE",     # D3-D5 (ADC)
    "7": "AIN1", "8": "AIN2", "9": "BIN1", "10": "BIN2",                 # D6-D9
    "11": "BUZZ_CTRL",                                                    # D10
    "12": "GND", "13": None, "14": "PLUS3V3",                            # GND / 5V(unused) / 3V3
    "15": "ENC1_A", "16": "ENC1_B", "17": "ENC2_A", "18": "ENC2_B",       # Plus1-4
    "19": "WALL_EMIT_FRONT", "20": "WALL_EMIT_DIAG", "21": "WALL_EMIT_SIDE",  # Plus5-7
    "22": "USER_BTN", "23": "USER_BTN2",                                  # Plus8-9
}
U3_BASE = snap((360, 300))
U3_PINS = XIAO("U3", U3_BASE)
for _pad, _net in XIAO_NET.items():
    _pos = U3_PINS[_pad]
    if _net is None:
        NC(_pos)
    elif _net == "GND":
        PWR("GND", _pos)
    else:
        RAIL(_net, _pos, rotation=180)

# Module decoupling: 100nF + 10uF at the 3V3 pin -- standard local bulk+HF
# caps at a module's supply entry (the nRF52840 has its own on-die
# requirements handled internally by Seeed's design).
c10a, c10b = C("C10", "10uF", (415, 235))
RAIL("PLUS3V3", c10a, rotation=90)
RAIL("GND", c10b, rotation=270)
c8p1, c8p2 = C("C8", "100nF", (430, 235))
RAIL("PLUS3V3", c8p1, rotation=90)
RAIL("GND", c8p2, rotation=270)

# Emitter-gate pull-downs: these GPIOs float from power-on until firmware
# init -- 100k holds every emitter bank OFF through the boot/brownout window
# (same defensive pattern used throughout this project's designs).
for _ref, _net, _gx in (("R62", "WALL_EMIT_FRONT", 455),
                         ("R63", "WALL_EMIT_DIAG", 465), ("R64", "WALL_EMIT_SIDE", 475)):
    _p1, _p2 = R(_ref, "100k", (_gx, 330))
    RAIL(_net, _p1, rotation=90)
    RAIL("GND", _p2, rotation=270)

# No USB-C connector, no USB ESD chip, no JTAG header, no external reset
# button, no strapping-pin guard resistors, and no ENC series-guard resistors
# on this design: the XIAO module provides its own native USB-C (flashing +
# CDC console), its own SWD/UF2 reset path, and plain nRF52840 GPIOs have no
# ESP32-style boot-strapping constraints, so none of that ESP32-era support
# circuitry applies here.

TXT("XIAO nRF52840 Sense Plus: 6 wall sensors DIRECT on D0-D5 (the only ADC-capable\n"
    "pins), TB6612 on D6-D9, buzzer on D10, full 4-channel quadrature + 3 emitter gates\n"
    "+ 2 buttons on the 9 Plus GPIO pads (no pre-assigned function on those pads --\n"
    "freely assigned here). Own onboard IMU (LSM6DS3TR-C, internal I2C, no external\n"
    "wiring), RGB LED, USB-C, and reset/UF2-bootloader button -- none needed on this\n"
    "carrier board. D-pin<->physical-pad identity is an ASSUMPTION (see final report):\n"
    "verify against a real board/continuity meter before fab.",
    (300, 368), size=2.0)

# ---------------------------------------------------------------------------
# CONNECTORS / DEBUG SECTION
# ---------------------------------------------------------------------------
TXT("USER INTERFACE  --  2 buttons (A, B)", (600, 230), size=5)

btn1, btn2 = SWPUSH("SW1", (620, 300), value="BTN_A")
rbtn1, rbtn2 = R("R10", "10k", (640, 300))
WIRE(rbtn2, btn1)
RAIL("PLUS3V3", rbtn1, rotation=90)
RAIL("USER_BTN", btn1, rotation=180)
RAIL("GND", btn2, rotation=0)

sw2a, sw2b = SWPUSH("SW2", (620, 330), value="BTN_B")
RAIL("USER_BTN2", sw2a, rotation=180)
RAIL("GND", sw2b, rotation=0)

TXT("Buttons are lettered on the silkscreen: A=SW1, B=SW2. Reset/bootloader is the\n"
    "XIAO module's OWN onboard button -- not present on this carrier board.\n"
    "SW1/A = USER_BTN: external 10k pull-up R10 (active-low).\n"
    "SW2/B = USER_BTN2: active-low, firmware enables the nRF52840's internal\n"
    "pull-up -- no external resistor (matches the esp32/design reference's SW2 style).",
    (600, 260), size=2.0)

# IMU section REMOVED ENTIRELY (XIAO revision): the module's own onboard
# LSM6DS3TR-C IMU is fully internal to the module (its own I2C bus wired
# inside the module, no external pins) -- no U8, no I2C pull-ups, no
# decoupling, no wiring of any kind needed on this carrier board.

# ---------------------------------------------------------------------------
# IR SENSOR ARRAY -- 6 wall sensors ONLY (cost-reduced 2-layer variant): the
# 8-channel LINE array, its read-mux (U4 CD74HC4067) and per-line indicators
# are REMOVED ENTIRELY (schematic definitions + wiring). Wall sensors read
# DIRECTLY on ADC1 IO1-6; battery telemetry (VBAT/VBUS) reads DIRECTLY on
# ADC1 IO7/IO9 -- it never depended on the mux in this design.
TXT("IR SENSOR ARRAY  --  6 wall sensors (direct ADC; line array + mux removed)", (10, 420), size=5)

TXT("Each wall sensor: phototransistor (collector -> 47k pull-up to +3V3 AND to its readout\nnode; emitter -> GND) + IR LED (anode -> current-limit resistor -> +3V3; cathode -> its\nGROUP's low-side switch). Emitters are GANGED: front pair / diagonal pair / side pair,\neach on one BSS138 driven by its own GPIO (IO15/16/17). Firing a wall pair and sampling\nBOTH its ADC pins in the same pulse halves scan time vs a serial mux walk; read bright,\nread ambient (group off), subtract. Current-limit: 33R (~50mA pulsed). UKMARS-practice\ngrouping keeps mutually-staring sensors on different groups.",
    (150, 460), size=2.0)

# Re-seed the ref counters so the sensor loop reproduces exactly Q2..Q7,
# R13..R24, D1..D6 regardless of how many parts the module sections above
# used (build_pcb.py hardcodes these numbers).
_ctr["Q"] = 1
_ctr["R"] = 12
_ctr["D"] = 0

# Names match the 6-signal list order in the final spec: front-L, front-R,
# diag-L, diag-R, side-L, side-R (same physical WALL_GEOM index order 0-5
# used in build_pcb.py -- only the descriptive names changed from the
# generic WALL1-6, the physical placement/grouping is unchanged).
SENSOR_NAMES = ["WALL_FL", "WALL_FR", "WALL_DL", "WALL_DR", "WALL_SL", "WALL_SR"]
SENSOR_X0 = 250
SENSOR_DX = 48
WALL_ROW_Y = 490

for i, name in enumerate(SENSOR_NAMES):
    x = SENSOR_X0 + i * SENSOR_DX
    row_y = WALL_ROW_Y

    # PT334-6B: 5mm filtered (black-lens) phototransistor, stocked by
    # Indian marketplaces (hubtronics/rarecomponents/robu black-lens pack)
    # -- replaces SFH 309 FA (ams-OSRAM Last-Time-Buy 2026-12-01). ASSEMBLY
    # TRAP: PT334's LONG lead is the EMITTER (opposite of the long-lead=anode
    # LED instinct).
    photo_fp = "LED_THT:LED_D5.0mm_IRBlack"
    photo_val = "PT334-6B (5mm filtered PT; LONG LEAD = EMITTER; SFH309 base symbol so ERC checks pins)"
    led_fp = "LED_THT:LED_D5.0mm_IRGrey"
    led_val = "IR333-A (Everlight 5mm 940nm 20deg; LD271 base symbol; TSAL6400 is lifecycle-Obsolete at Lion)"

    # receiver + pull-up: node goes STRAIGHT to a XIAO ADC pin (label only).
    rx_c, rx_e = SFH309(ref("Q"), (x, row_y), footprint=photo_fp, value=photo_val)
    RAIL("GND", rx_e, rotation=270)
    # pull-up x-aligned with the collector pin -> straight vertical wire
    rp1, rp2 = R(ref("R"), "47k", (rx_c[0], row_y + 15))
    WIRE(rp2, rx_c)
    RAIL("PLUS3V3", rp1, rotation=90)
    RAIL(f"{name}_SENSE", rx_c, rotation=0)

    # emitter + current-limit resistor; cathode joins its GROUP's switched
    # net (one BSS138 per group, below) instead of a per-sensor switch.
    # limiter x-aligned with the LED anode pin -> straight vertical wire
    led_k, led_a = LED_SFH4550(ref("D"), (x + 16, row_y), footprint=led_fp, value=led_val)
    lr1, lr2 = R(ref("R"), "33", (led_a[0], row_y + 15))
    RAIL("PLUS3V3", lr1, rotation=90)
    WIRE(lr2, led_a)
    _grp = "EMIT_FRONT_K" if i < 2 else "EMIT_DIAG_K" if i < 4 else "EMIT_SIDE_K"
    RAIL(_grp, led_k, rotation=180)

# Line channels no longer consume Q8-15/D7-14 (single TCRT5000 each, LS1-8).
# Re-seed the counters so every later ref keeps its historical number
# (Q16.. group FETs, Q20.. indicator drivers, D15.. indicator LEDs).
_ctr["Q"] = 15
_ctr["D"] = 14

# Group emitter switches: one BSS138 per group (Q16-Q19), gate driven directly
# by a XIAO GPIO (no demux -- U5 deleted in rev 4). Gate nets idle low.
for _gref, _gate, _knet, _gx in ((None, "WALL_EMIT_FRONT", "EMIT_FRONT_K", 250),
                                  (None, "WALL_EMIT_DIAG", "EMIT_DIAG_K", 320),
                                  (None, "WALL_EMIT_SIDE", "EMIT_SIDE_K", 390)):
    # LINE_EMIT group removed with the line array (2-layer edition).
    _g, _s, _d = QN_BSS138(ref("Q"), (_gx, 620))
    RAIL(_gate, _g, rotation=180)
    RAIL("GND", _s, rotation=270)
    RAIL(_knet, _d, rotation=0)

# LINE-SENSOR INDICATOR LEDs removed with the line array (2-layer edition):
# the 8 D15-D22 / Q20-Q27 / R41-R48 per-line indicators are gone.
#
# WALL-SENSOR INDICATOR LEDs (D23-D28 / their PMOS drivers Q28-33 / resistors
# R49-54) REMOVED ENTIRELY (cost-reduced 2-layer variant, user request:
# "remove indicator LEDs"). The wall sensors themselves are unaffected --
# only their top-side "wall seen" indicator LEDs are gone.

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
# STATUS / POWER LEDs (XIAO revision). Only the two LEDs that need NO GPIO
# are kept -- D30 (power, always-on from +3V3) and D33 (motor-rail present,
# driven straight from VM_6V). The ESP-driven status LED (D31, ex-IO12) and
# the WS2812B RGB LED (D32, ex-IO14) are REMOVED: with the 20-signal/20-pin
# XIAO budget an exact fit, there is no spare GPIO for either, and the
# module's own onboard RGB LED already covers status indication in firmware.
# Added at the END (after the buzzer) using shared net labels instead of
# WIRE() so no dogleg lane counter shifts.
# ---------------------------------------------------------------------------
TXT("STATUS / POWER LEDs", (600, 600), size=5)

# Power LED -- always on from +3V3 (dev-board power-good indicator)
_pr1, _pr2 = R("R82", "1k", (610, 640))
RAIL("PLUS3V3", _pr1, rotation=90)
RAIL("PWRLED_A", _pr2, rotation=270)
_pb = snap((610, 620))
g.add_component("LED", "LD271", "D30", "Power LED 0603 red (JLC good-stock)",
                _pb, {"1": "", "2": ""}, footprint="LED_SMD:LED_0603_1608Metric")
RAIL("PWRLED_A", pin_at(_pb, (2.54, 0)), rotation=0)          # anode
RAIL("GND", pin_at(_pb, (-5.08, 0)), rotation=180)           # cathode

# Status LED (D31/R83, ex-IO12) and RGB WS2812B (D32/C31, ex-IO14) REMOVED --
# no spare GPIO exists on the XIAO's exact 20/20 pin budget, and the module's
# own onboard RGB LED already fills the status-indication role.

# Motor-rail indicator LED (user request): ON whenever VM_6V (the RESTORED
# TPS54302-regulated 6.0V motor rail) is present -- i.e. SW5 AND SW6 both on.
# ~4mA, negligible vs motor current; confirms the switch + reverse-protect
# FET path AND the 6V buck are both live.
_mr1, _mr2 = R("R84", "1k", (740, 640))
RAIL("VM_6V", _mr1, rotation=90)
RAIL("MOTLED_A", _mr2, rotation=270)
_mb = snap((740, 620))
g.add_component("LED", "LD271", "D33", "Motor-power LED 0603 (VM_6V present; JLC good-stock)",
                _mb, {"1": "", "2": ""}, footprint="LED_SMD:LED_0603_1608Metric")
RAIL("MOTLED_A", pin_at(_mb, (2.54, 0)), rotation=0)     # anode
RAIL("GND", pin_at(_mb, (-5.08, 0)), rotation=180)       # cathode

_OUT_SCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "micromouse-pcb-simplified.kicad_sch")
with open(_OUT_SCH, "w", encoding="utf-8", newline="\n") as f:
    f.write(g.render(title="Micromouse PCB"))

print("wrote", len(g.symbol_instances), "components,", len(g.label_instances), "labels,",
      len(g.wires), "wires,", len(g.no_connects), "no-connects,",
      "unique lib symbols:", len(g.lib_symbols_needed))
