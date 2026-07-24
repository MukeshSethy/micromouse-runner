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
    "U8": ("BMI160", "Bosch Sensortec"),                   # 6-axis accel+gyro IMU, 3.3V native I2C
    "Q1": ("DMP3098L-7", "Diodes Incorporated"),           # -30V/-3.8A/Vgs +/-20V (2S-safe gate)
    # Rev 9 (2026-07-23): restored motor power switch (Q35/R85/SW6, see the
    # POWER section) reuses this EXACT same part -- already vetted for this
    # 2S/8.4V, negative-Vgs-tolerant environment, so no new part-qual risk.
    "Q35": ("DMP3098L-7", "Diodes Incorporated"),          # motor-power high-side switch
    "L1": ("SRP4020TA-4R7M", "Bourns"),
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
    # Cost-reduced 2-layer variant: J8 (JTAG header) is gone, but the plain
    # power/status/motor-rail indicator LEDs (D30/D31/D33) are KEPT -- only
    # the PER-WALL-SENSOR indicator LEDs (D23-D28) were removed (user
    # clarification: "remove indicator LEDs" meant those, not these three).
    # WS2812B addressable RGB (D32) is KEPT per user request.
    # Rev 8 (2026-07-21): genuine Worldsemi WS2812B not stocked at Lion
    # Circuits at all -- swapped to XL-5050RGBC-WS2812B (Xinglight), same
    # 5050 PLCC4 footprint, WS2812B-protocol-compatible, in stock at both
    # LCSC/JLCPCB (C2843785) and Lion Circuits.
    "D32": ("XL-5050RGBC-WS2812B", "Xinglight"),
    "J7": ("USB4105-GF-A", "GCT"),
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
    "SW4": ("KMR221NGLFS", "C&K"),
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
# POWER SECTION -- cost-reduced 2-layer variant: 2S LiPo -> AP63203 (3V3,
# 2A) logic rail ONLY. The 6V motor buck (TPS54302/U7) is REMOVED -- motors
# run off VM_MOTOR, a P-MOSFET-switched copy of VM_BATT (the raw, fused,
# reverse-protected battery voltage), through the TB6612. Two slide
# switches: SW5 enables everything (3V3 buck EN); SW6 (rev 9, 2026-07-23:
# RESTORED per user request) separately gates motor power via Q35/R85 (see
# below) so logic+sensors can run with the motors off -- a real safety/UX
# feature, not the old SW6's direct 6V-buck-EN gating (that regulator no
# longer exists). No onboard charger: a 2S pack charges on an external
# balance charger; J9 receives the pack's balance plug for per-cell
# monitoring while driving.
# ---------------------------------------------------------------------------
TXT("POWER  --  2S LiPo -> AP63203 3V3 (2A) logic rail; motors run off VM_MOTOR (switched); SW5=all power, SW6=motors", (10, 190), size=5)

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
# connector, no BAT_MID divider. Battery monitoring is PACK-LEVEL only via
# VBAT_SENSE (IO7); the 2S pack floor (6.6V) guards the pack adequately and a
# 2S LiPo charged on a balance charger stays matched. Frees the motor-bay area.

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
# everything (logic side) off. The old SW6/MOT_EN divider (R70/R71) that
# used to gate the 6V buck's EN pin is gone with that regulator -- SW6's
# restored job (below) is different: it gates a series FET, not a buck EN.
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

# --- Motor power switch (rev 9, 2026-07-23; user request): restore a
# SEPARATE motor on/off control. The original board's SW6 gated the 6V
# TPS54302 buck's EN pin directly -- a microamp-level logic signal, safe for
# a small slide switch. That buck is gone (motors run off the battery rail
# directly), so a plain PCM12SMTR slide (~0.3A rated) must NOT carry the
# TB6612's real supply current (low amps under stall) -- unsafe/out of spec.
# Fix: Q35, a P-MOSFET HIGH-SIDE SWITCH in series between VM_BATT and the
# TB6612's VM pins (net VM_MOTOR, wired at U2 below), using the EXACT SAME
# part as Q1 (DMP3098L-7 -- already vetted for this 2S/8.4V, negative-Vgs-
# tolerant environment; no new part-qualification risk). Wiring mirrors the
# Q1/R1 reverse-guard pattern: source=VM_BATT, drain=VM_MOTOR, gate pulled
# to VM_BATT through R85 (100k, matches R1) -- SW6 pulls the gate to GND in
# its "on" position (Vgs goes strongly negative = FET on = motors powered),
# and leaves it floating/pulled-high in its other position (Vgs ~0 = motors
# off). SW6 only ever switches R85's microamp-level gate current, never the
# motor supply itself. This lets logic+sensors (SW5) power up independently
# of the motors (SW6) -- a real safety/UX feature, not cosmetic.
q35D, q35G, q35S = QPMOS("Q35", "Q_PMOS motor-power switch (DMP3098L-7, same part as Q1)", (155, 115))
RAIL("VM_BATT", q35S, rotation=90)
RAIL("VM_MOTOR", q35D, rotation=270)
PWR("PWR_FLAG", q35D)   # VM_MOTOR is a genuine power net (drives U2's VM pins) --
                        # same PWR_FLAG pattern as VM_BATT (Q1/qS) and PLUS3V3 (U1
                        # FB), needed so ERC doesn't flag U2's VM pins as undriven.
r85a, r85b = R("R85", "100k", (185, 115))
RAIL("VM_BATT", r85a, rotation=90)
RAIL("MOT_EN", r85b, rotation=270)
RAIL("MOT_EN", q35G, rotation=180)
SW6_BASE = snap((200, 128))
g.add_component("Switch", "SW_SPDT", "SW6",
                 "PWR MOTORS (PCM12SMTR slide; slide-to-GND = motors ON)", SW6_BASE,
                 {"1": "", "2": "", "3": ""},
                 footprint="Button_Switch_SMD:SW_SPDT_PCM12")
RAIL("GND", pin_at(SW6_BASE, (5.08, 2.54)), rotation=0)      # throw A -> GND (motors ON)
RAIL("MOT_EN", pin_at(SW6_BASE, (-5.08, 0)), rotation=180)   # common -> gate node
NC(pin_at(SW6_BASE, (5.08, -2.54)))                          # throw B unused

TXT("+3V3 is the regulated logic rail: ESP32-S3, IMU, encoder VCC, PT pull-ups,\nindicator drivers and IR LED current. VM_MOTOR feeds the TB6612 VM pins -- a\nP-MOSFET-switched (Q35/SW6) copy of VM_BATT (6V motor buck removed; motors run off\nthe fused, reverse-protected battery through the switch, not straight off it).",
    (200, 100), size=2.2)

# 6V MOTOR BUCK REMOVED (cost-reduced 2-layer variant, user request): U7
# (TPS54302), L2, its FB divider (R73/R74), supporting caps (C15/C16/C17/
# C18) and the old MOT_EN divider (R70/R71) that gated it are all gone.
# Motors now run off VM_MOTOR -- a Q35/SW6-switched copy of VM_BATT -- through
# the TB6612 (see the motor driver section below, where VM1/VM2/VM3 +
# C30/C11/C12 are wired to VM_MOTOR instead of VM_BATT or the old VM_6V).

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

# BAT_MID divider (R75/R76/C19) removed with J9 -- no per-cell monitoring.

TXT("VBAT_SENSE = pack (0-8.4V) x 39/139 <= 2.36V on ADC1 IO7 (direct).\nVBUS_SENSE = 5V x 15/25 <= 3.15V on IO9. PACK-LEVEL monitoring only\n(per-cell/balance removed). Firmware cutoff: 6.6V pack floor (3.3V/cell avg);\nthe 6V motor rail stays in regulation across the 6.6-8.4V window.",
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
RAIL("VM_MOTOR", U2["VM1"], rotation=90)
RAIL("VM_MOTOR", U2["VM2"], rotation=90)
RAIL("VM_MOTOR", U2["VM3"], rotation=90)
RAIL("PLUS3V3", U2["VCC"], rotation=90)
RAIL("GND", U2["GND"], rotation=270)
RAIL("GND", U2["PGND1"], rotation=270)
RAIL("GND", U2["PGND2"], rotation=270)
# Rev 6 IN/IN PWM mode: PWMA/PWMB tied HIGH (permanent), the four IN pins
# carry LEDC PWM (Toshiba-documented drive mode; frees two GPIOs for I2C).
# STBY tied HIGH through R55 (a soft/logic-level kill, unchanged): the
# HARDWARE motor kill is SW6 (rev 9: restored -- cuts VM_MOTOR via Q35) and
# SW5 (cuts all power, logic included); TB6612's IN pins also have internal
# pull-downs, so a held-in-reset MCU leaves the outputs off. IO46 (the old
# STBY strap risk) is freed to a clean no-connect.
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

# VM decoupling for 2S/direct-battery: C30 220uF/16V alu bulk (hot-loop,
# standards item) + 10uF/25V + 100nF ceramics at the pins. Rev 9: moved onto
# VM_MOTOR (the switched rail actually present at U2's VM pins now) instead
# of VM_BATT -- this is where the TB6612's own decoupling needs to sit.
c30a, c30b = C("C30", "220uF/16V", (118, 335), footprint="Capacitor_SMD:CP_Elec_6.3x7.7")
RAIL("VM_MOTOR", c30a, rotation=90)
RAIL("GND", c30b, rotation=270)
c11a, c11b = C("C11", "10uF/25V", (130, 335), footprint="Capacitor_SMD:C_1210_3225Metric")
RAIL("VM_MOTOR", c11a, rotation=90)
RAIL("GND", c11b, rotation=270)
c12a, c12b = C("C12", "100nF", (142, 335))
RAIL("VM_MOTOR", c12a, rotation=90)
RAIL("GND", c12b, rotation=270)
c14a, c14b = C("C14", "100nF", (154, 335))
RAIL("PLUS3V3", c14a, rotation=90)
RAIL("GND", c14b, rotation=270)

TXT("Bare TB6612FNG (U2, SSOP-24) in IN/IN PWM mode: PWMA/PWMB tied 3V3, AIN/BIN = LEDC\n(IN1=PWM,IN2=0 fwd-coast; IN1=PWM,IN2=1 rev-brake). VM = VM_MOTOR (Q35/SW6-switched copy\nof the raw, fused, reverse-protected battery -- 6V motor buck removed); STBY pulled high\n(R55) -- hardware motor kill = SW6 (rev 9: restored) + SW5 + IN pins' internal pull-downs.\nDecoupling: C30 220uF/16V alu + C11 10uF/25V + C12 100nF on VM, C14 on VCC.",
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
# so all 6 wall sensors read DIRECTLY; plus a rear USB-C for flashing/debug
# (native USB-Serial-JTAG, no separate JTAG header) and 2 user buttons
# (button C/SW3 removed, cost-reduced variant).
#
# LOCKED PIN MAP rev 6 (ADC1 = IO1..IO10 is the only WiFi-safe ADC):
#   IO1-6  WALL1-6_SENSE   IO7 MUX_SENSE (line array + battery telemetry)
#   IO8 MUX_S3 (4067 high select -- VBAT/BAT_MID/VBUS moved onto mux Y8/9/10)
#   IO9/10 AIN1/AIN2 (LEDC PWM, IN/IN mode)   IO11-13 MUX_S0-2
#   IO14 LINE_EMIT   IO15-17 WALL_EMIT_FRONT/DIAG/SIDE
#   IO18 I2C_SDA / IO21 I2C_SCL (I2C to BMI160; freed by IN/IN motor mode)
#   IO37 unused (BMI160 has no INT wired)   IO38 BIN1
#   IO45 BIN2 -- STRAPPING pin as motor output: safe ONLY because it idles
#     LOW and carries only R65's pull-DOWN (IO45 high at reset selects 1.8V
#     flash supply = brick; never add a pull-up to this net)
#   IO46 BUZZ_CTRL (rev 7.2: buzzer driver -- the ONLY free GPIO; strap-safe:
#     the NPN base + 220R load only ever pulls it toward GND = boot default)
#   IO39-42 unused (ex-JTAG; J8 removed, debug via native USB-C JTAG)
#   IO43(TXD0)/IO44(RXD0) ENC2_B/ENC2_A   IO47/48 ENC1_A/B  (console = USB-CDC)
#   IO0 BTN1/BOOT   IO35 BTN2 (internal pull-up; button C/SW3 + its IO36 net
#     removed, cost-reduced variant)
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
    "7": "VBAT_SENSE", "12": None,                                      # IO7 ADC1 (pack); IO8 free (per-cell removed)
    "17": "VBUS_SENSE", "18": "AIN2",                                   # IO9 ADC1 (VBUS) / IO10 LEDC PWM
    "19": "AIN1", "20": "STATUS_LED", "21": None,                      # IO11 LEDC PWM; IO12 status LED (D31); IO13 spare
    "22": "RGB_DATA",                                                   # IO14 -> WS2812B addressable RGB
    "8": "WALL_EMIT_FRONT", "9": "WALL_EMIT_DIAG", "10": "WALL_EMIT_SIDE",  # IO15-17
    "11": "I2C_SDA", "23": "I2C_SCL",                                    # IO18/IO21 (I2C, BMI160)
    "28": "USER_BTN2", "29": None, "30": None,          # IO35 button B; IO36 button C removed w/ SW3; IO37 unused (BMI160 INT not wired)
    "31": "BIN1",                                                        # IO38
    "32": None, "33": None, "34": None, "35": None,   # IO39-42 ex-JTAG (J8 removed; debug via native USB-C JTAG)
    "36": "ENC2_A_S3", "37": "ENC2_B_S3",   # IO44(RXD0)/IO43(TXD0) via 1k guards
    "26": "BIN2", "16": "BUZZ_CTRL",   # IO45 strap (idle-low output); IO46 -> buzzer driver (rev 7.2; strap-safe: Q34's B-E junction + R81 only ever pull the pin LOW, its required boot state)
    "24": "ENC1_A", "25": "ENC1_B",                                      # IO47/IO48
    "27": "USER_BTN",                                                    # IO0 (BOOT strap)
    "13": "USB_DM_C", "14": "USB_DP_C",   # USB D-/D+ DIRECT to J7 (USB ESD chip U6 removed)
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
# 1uF RC delay + reset button (SW4). Hold SW1 (IO0) + tap SW4 = ROM download.
# (Rev 8: renumbered so SW1-3 are the three user buttons and SW4 is RESET --
# was SW2; purely a designator rename, net names below are unchanged.)
r11a, r11b = R("R11", "10k", (415, 258))
RAIL("PLUS3V3", r11a, rotation=90)
RAIL("ESP_EN", r11b, rotation=270)
c9a, c9b = C("C9", "1uF", (430, 258))
RAIL("ESP_EN", c9a, rotation=90)
RAIL("GND", c9b, rotation=270)
sw4a, sw4b = SWPUSH("SW4", (447, 265), value="RESET")
RAIL("ESP_EN", sw4a, rotation=180)
RAIL("GND", sw4b, rotation=0)

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


# USB ESD chip (U6, USBLC6-2SC6) REMOVED (cost-reduced 2-layer variant, user
# request): D+/D- run DIRECT from the ESP32-S3 module (U3 pads 13/14) to the
# USB-C connector J7, on shared net labels USB_DM_C/USB_DP_C (see U3_NET
# above and the J7 wiring below) -- no series resistors either, same
# accepted trade as the from-scratch simplified draft: the S3's native FS
# PHY meets the USB driver-impedance window on its own.

# JTAG header J8 REMOVED (2-layer edition, user request): debugging uses the
# ESP32-S3 native USB-Serial-JTAG over the rear USB-C (J7). The dedicated JTAG
# GPIOs IO39-42 are freed and no-connected in the pin map above.

TXT("ESP32-S3-WROOM-1 on FreeRTOS: 6 wall sensors DIRECT on ADC1 IO1-IO6 (a fired pair is\n"
    "sampled in parallel), battery IO7, TB6612 on IO9/10/38/45, buzzer IO46 (straps 45/46 =\n"
    "idle-low outputs ONLY -- never add pull-ups), encoders IO43/44/47/48 (PCNT hardware\n"
    "quadrature via GPIO matrix), IO39-42 unused (ex-JTAG; J8 removed, debug via native\n"
    "USB-Serial-JTAG over USB-C). Buttons: SW1=IO0 (start/BOOT), SW2=IO35 (internal pull-up;\n"
    "button C/SW3 removed). USB-C (rear) on the native USB pads = flash + console; UART0\n"
    "pins repurposed as encoder inputs. Every analog net sits on ADC1 (IO1-IO7).",
    (300, 368), size=2.0)

# ---------------------------------------------------------------------------
# CONNECTORS / DEBUG SECTION
# ---------------------------------------------------------------------------
TXT("USER INTERFACE  --  2 buttons (button C removed, cost-reduced variant)", (600, 230), size=5)

btn1, btn2 = SWPUSH("SW1", (620, 300), value="BTN_A (start / BOOT)")
rbtn1, rbtn2 = R("R10", "10k", (640, 300))
WIRE(rbtn2, btn1)
RAIL("PLUS3V3", rbtn1, rotation=90)
RAIL("USER_BTN", btn1, rotation=180)
RAIL("GND", btn2, rotation=0)

sw2a, sw2b = SWPUSH("SW2", (620, 330), value="BTN_B")
RAIL("USER_BTN2", sw2a, rotation=180)
RAIL("GND", sw2b, rotation=0)

# SW3 (button C) REMOVED (cost-reduced 2-layer variant, user request).

TXT("Buttons are lettered on the silkscreen: A=SW1, B=SW2, RST=SW4 (C/SW3 removed).\n"
    "SW1/A = USER_BTN on IO0: start-run button AND the BOOT strap (hold A, tap RST\n"
    "-> ROM download mode). External 10k pull-up R10 keeps the strap solid.\n"
    "SW2 = USER_BTN2 on IO35 (menu/select UX): active-low, firmware enables the internal\n"
    "pull-up -- no external resistor. NOTE: on octal-PSRAM (-R8) modules IO35 does not\n"
    "exist; button 2 is the sacrificial feature (control is unaffected).\n"
    "SW4 (reset) lives in the controller section on ESP_EN.",
    (600, 260), size=2.0)

# ---------------------------------------------------------------------------
# IMU -- BMI160 6-axis (accel+gyro, NO on-chip fusion), replacing the BNO055
# (cost-reduced 2-layer variant, user request): fewer pins (14-pin LGA vs.
# 28), plain I2C, lower cost. 3.3V-native (VDD/VDDIO both 3V3). Pinout +
# wiring verified directly against KiCad's own Sensor_Motion.kicad_sym
# library (footprint Package_LGA:Bosch_LGA-14_3x2.5mm_P0.5mm). I2C mode:
# CSB tied HIGH (I2C select); SDO tied LOW -> address 0x68. INT1/INT2 and
# the auxiliary-magnetometer/OIS-SPI pins (ASDx/ASCx/OCSB/OSDO) are unused
# and no-connected -- firmware polls over I2C, no interrupt wired.
# ---------------------------------------------------------------------------
TXT("IMU  --  BMI160 6-axis (accel+gyro) on I2C (IO18=SDA, IO21=SCL), addr 0x68", (600, 420), size=5)
U8_BASE = snap((650, 480))
g.add_component("Sensor_Motion", "BMI160", "U8",
                 "BMI160 (6-axis accel+gyro; 3.3V native; I2C 0x68)",
                 U8_BASE, {str(n): "" for n in range(1, 15)},
                 footprint="Package_LGA:Bosch_LGA-14_3x2.5mm_P0.5mm",
                 datasheet="https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi160-ds000.pdf")
RAIL("GND", pin_at(U8_BASE, (0, -12.7)), rotation=270)          # GND
RAIL("PLUS3V3", pin_at(U8_BASE, (0, 10.16)), rotation=90)       # VDD
RAIL("PLUS3V3", pin_at(U8_BASE, (-2.54, 10.16)), rotation=90)   # VDDIO
RAIL("GND", pin_at(U8_BASE, (-2.54, -12.7)), rotation=270)      # GNDIO
RAIL("PLUS3V3", pin_at(U8_BASE, (-12.7, -2.54)), rotation=180)  # CSB -> I2C mode
RAIL("GND", pin_at(U8_BASE, (-12.7, 5.08)), rotation=180)       # SDO -> addr 0x68
RAIL("I2C_SCL", pin_at(U8_BASE, (-12.7, 0)), rotation=180)      # SCx
RAIL("I2C_SDA", pin_at(U8_BASE, (-12.7, 2.54)), rotation=180)   # SDx
NC(pin_at(U8_BASE, (-12.7, -5.08)))    # INT1 unused
NC(pin_at(U8_BASE, (-12.7, -7.62)))    # INT2 unused
NC(pin_at(U8_BASE, (10.16, 2.54)))     # ASDx (aux mag/OIS SPI) unused
NC(pin_at(U8_BASE, (10.16, 0)))        # ASCx unused
NC(pin_at(U8_BASE, (10.16, -2.54)))    # OCSB unused
NC(pin_at(U8_BASE, (10.16, -5.08)))    # OSDO unused

# I2C pull-ups (4.7k, 400kHz) -- fresh refs (R79/R80: R82-84 went back to the
# restored plain power/status/motor-rail indicator LEDs' resistors, so the
# pull-ups moved to genuinely-unused numbers in the same R70-84 recycled
# range); placed in the same spot the old R77/R78 SDA/SCL pull-ups used.
r79a, r79b = R("R79", "4.7k", (585, 500))
RAIL("PLUS3V3", r79a, rotation=90)
RAIL("I2C_SDA", r79b, rotation=270)
r80a, r80b = R("R80", "4.7k", (572, 500))
RAIL("PLUS3V3", r80a, rotation=90)
RAIL("I2C_SCL", r80b, rotation=270)

# VDD/VDDIO decoupling (100nF each, fresh refs) -- BMI160 needs far less
# support than the 28-pin BNO055 (no nBOOT/nRESET/CAP pins to bias).
c32a, c32b = C("C32", "100nF", (640, 445))
RAIL("PLUS3V3", c32a, rotation=90)
RAIL("GND", c32b, rotation=270)
c33a, c33b = C("C33", "100nF", (652, 445))
RAIL("PLUS3V3", c33a, rotation=90)
RAIL("GND", c33b, rotation=270)

TXT("BMI160 mid-line placement (user requirement): geometric center of rotation sensing.\nNo on-chip fusion (6-axis only, unlike the BNO055 it replaces) -- firmware runs its own\ncomplementary/Kalman filter on gyro+accel; the yaw-rate loop uses the gyro directly.\nI2C address 0x68 (SDO tied low); CSB tied high selects I2C mode.",
    (600, 560), size=2.0)

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

SENSOR_NAMES = ["WALL1", "WALL2", "WALL3", "WALL4", "WALL5", "WALL6"]
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

    # receiver + pull-up: node goes STRAIGHT to an ESP32 ADC1 pin (label only).
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
# STATUS / POWER / MOTOR-RAIL / RGB LEDs (2-layer edition, user request).
# RESTORED verbatim from the original board's build_schematic.py (D30/D31/D33
# + their resistors R82/R83/R84) -- only the per-WALL-SENSOR indicator LEDs
# (D23-D28) are removed in this cost-reduced variant, not these three. Added
# at the END (after the buzzer) using shared net labels instead of WIRE() so
# no dogleg lane counter shifts. All good-stock JLC parts.
# ---------------------------------------------------------------------------
TXT("STATUS / POWER / RGB LEDs", (600, 600), size=5)

# Power LED -- always on from +3V3 (dev-board power-good indicator)
_pr1, _pr2 = R("R82", "1k", (610, 640))
RAIL("PLUS3V3", _pr1, rotation=90)
RAIL("PWRLED_A", _pr2, rotation=270)
_pb = snap((610, 620))
g.add_component("LED", "LD271", "D30", "Power LED 0603 red (JLC good-stock)",
                _pb, {"1": "", "2": ""}, footprint="LED_SMD:LED_0603_1608Metric")
RAIL("PWRLED_A", pin_at(_pb, (2.54, 0)), rotation=0)          # anode
RAIL("GND", pin_at(_pb, (-5.08, 0)), rotation=180)           # cathode

# Status LED -- ESP-driven on IO12 (flashing/status, dev-board style)
_sr1, _sr2 = R("R83", "1k", (660, 640))
RAIL("STATUS_LED", _sr1, rotation=90)
RAIL("STATLED_A", _sr2, rotation=270)
_sb = snap((660, 620))
g.add_component("LED", "LD271", "D31", "Status LED 0603 red (JLC good-stock)",
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

# Motor-rail indicator LED (user request): ON whenever VM_MOTOR (rev 9: the
# Q35/SW6-switched copy of the fused, reverse-protected battery rail) is
# present -- i.e. SW5 AND SW6 both on. Matches the original board's D33
# (ON when its SW6-gated VM_6V rail was up); this variant has no 6V buck, so
# the equivalent "motor supply is actually live" net is VM_MOTOR, not the
# unswitched VM_BATT. ~4mA, negligible vs motor current; confirms the switch
# + reverse-protect FET path AND the motor-power switch are both live.
_mr1, _mr2 = R("R84", "1k", (740, 640))
RAIL("VM_MOTOR", _mr1, rotation=90)
RAIL("MOTLED_A", _mr2, rotation=270)
_mb = snap((740, 620))
g.add_component("LED", "LD271", "D33", "Motor-power LED 0603 (VM_MOTOR present; JLC good-stock)",
                _mb, {"1": "", "2": ""}, footprint="LED_SMD:LED_0603_1608Metric")
RAIL("MOTLED_A", pin_at(_mb, (2.54, 0)), rotation=0)     # anode
RAIL("GND", pin_at(_mb, (-5.08, 0)), rotation=180)       # cathode

_OUT_SCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "micromouse-pcb-simplified.kicad_sch")
with open(_OUT_SCH, "w", encoding="utf-8", newline="\n") as f:
    f.write(g.render(title="Micromouse PCB"))

print("wrote", len(g.symbol_instances), "components,", len(g.label_instances), "labels,",
      len(g.wires), "wires,", len(g.no_connects), "no-connects,",
      "unique lib symbols:", len(g.lib_symbols_needed))
