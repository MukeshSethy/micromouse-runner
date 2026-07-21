"""Design-MPN -> JLCPCB/LCSC part mapping for the SMD rev-7.2 board.

Each entry:
  "<design MPN>": dict(
      lcsc  = "Cxxxxxx",       # LCSC part number JLCPCB orders (or "" if none)
      part  = "<orderable MPN>",  # == design MPN, or the substitute's MPN
      tier  = "BASIC"|"EXTENDED",
      smt   = True|False,      # True: JLC SMT line places it; False: THT (hand)
      note  = "",              # 'SUB: <why>' when substituted / other caveat
  )

Filled from live JLCPCB/LCSC research (2026-07-20), every C-number taken from a
real LCSC/JLCPCB page and cross-checked. Substitutes are FOOTPRINT-COMPATIBLE
only, so the rev-7.2 gerbers + placement stay valid.

Tier note: none of these MPNs are in JLC's "Basic" library, so all read
EXTENDED -- BUT every one is flagged "Economic and Standard" PCBA, i.e. a
preferred/economic extended part that currently carries NO per-part setup fee.
Practical setup-fee impact is ~zero; strict tier is EXTENDED.
"""

def _e(lcsc, part, smt=True, note="", tier="EXTENDED"):
    return dict(lcsc=lcsc, part=part, tier=tier, smt=smt, note=note)

LCSC_MAP = {
    # ---- module + ICs (SMD, JLC SMT line places all) ------------------------
    "ESP32-S3-WROOM-1-N8R2": _e("C2913204", "ESP32-S3-WROOM-1-N8R2"),
    "TB6612FNG,C,8,EL":      _e("C141517",  "TB6612FNG,C,8,EL"),
    "AP63203WU-7":           _e("C780769",  "AP63203WU-7"),
    "TPS54302DDCR":          _e("C311983",  "TPS54302DDCR"),
    "CD74HC4067M96":         _e("C496123",  "CD74HC4067M96"),
    "USBLC6-2SC6":           _e("C7519",    "USBLC6-2SC6"),
    "BNO055":                _e("C93216",   "BNO055",
                                note="AT-RISK: LCSC retail down to 2 units (re-verified 2026-07-21); JLC "
                                     "assembly pool was ~505 on 07-20 and draining. No pin/protocol "
                                     "drop-in (BNO085 is NOT a sub). RESERVE at checkout or source "
                                     "the part yourself BEFORE ordering assembly"),

    # ---- discretes (SMD) ----------------------------------------------------
    "DMP3098L-7":            _e("C150492",  "DMP3098L-7"),
    "BSS138LT1G":            _e("C82045",   "BSS138LT1G"),
    "BSS84LT1G":             _e("C82079",   "BSS84LT1G"),
    "MMBT2222A-7-F":         _e("C94515",   "MMBT2222A-7-F"),
    "1N4148W-7-F":           _e("C83528",   "1N4148W-7-F"),

    # ---- power passives (SMD) ----------------------------------------------
    "SRP4020TA-4R7M":        _e("C2041623", "SRP4020TA-4R7M", note="low stock (~806) -- order early or sub SRP4020 4R7"),
    "EEE-FT1C221AP":         _e("C178588",  "EEE-FT1C221AP"),
    "MINISMDC350F/16-2":     _e("C883162",  "BSMD1812-300-16V (BHFUSE)",
                                note="SUB: exact Littelfuse MPN not on LCSC; 1812 PPTC 3.0A-hold/16V "
                                     "(design intent 2.6A hold) -- same footprint, verify trip current"),

    # ---- opto (5mm THT emitters/detectors + SMD indicator LEDs) -------------
    "TCRT5000":              _e("C2984661", "TCRT5000",  smt=False, note="THT reflective sensor (hand-solder)"),
    "IR333-A":               _e("C264290",  "IR333-A",   smt=False, note="THT 5mm IR emitter (hand-solder)"),
    "PT334-6B":              _e("C369188",  "PT334-6B",  smt=False, note="THT 5mm phototransistor (hand-solder)"),
    "APT1608SURCK":          _e("C5875723", "APT1608SURCK"),   # 0603 SMD indicator
    "WS2812B":               _e("C2761795", "WS2812B-B/T (Worldsemi)",
                                note="addressable RGB, SMD5050-4P = LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm; "
                                     "good stock ~414k (alt C114586 ~500k) -- verified 2026-07-20"),

    # ---- buzzer (SMD) -------------------------------------------------------
    "CMT-8504-100-SMT-TR":   _e("C3811795", "CMT-8504-100-SMT-TR"),

    # ---- connectors (THT / hand-solder) -------------------------------------
    "USB4105-GF-A":          _e("C3020560", "USB4105-GF-A", smt=False, note="USB-C (SMD shell + THT pegs; hand-solder recommended)"),
    "B2B-XH-A":              _e("C158012",  "B2B-XH-A",  smt=False, note="THT JST-XH 2P (hand-solder)"),
    "B3B-XH-A(LF)(SN)":      _e("C144394",  "B3B-XH-A(LF)(SN)", smt=False, note="THT JST-XH 3P (hand-solder)"),
    "B6B-ZR(LF)(SN)":        _e("C157984",  "B6B-ZR(LF)(SN)",   smt=False, note="THT JST-ZH 6P (hand-solder)"),
    "XT60-M":                _e("C98733",   "XT60-M",    smt=False, note="THT XT60 male (hand-solder)"),
    "61300611121":           _e("C124380",  "1x6 2.54mm male header",
                                smt=False, note="SUB: Wurth MPN not on LCSC; generic 1x6/2.54mm THT header (JTAG)"),

    # ---- switches (THT tact + SMD slide) ------------------------------------
    "PTS645VL582LFS":        _e("C285524",  "PTS645VL582LFS", smt=False, note="THT 6mm tact (hand-solder); JLC lib also C221892"),
    "PCM12SMTR":             _e("C221841",  "PCM12SMTR"),   # SMD slide switch

    # ---- passives: 0805 resistors (design=Yageo RC0805 1%) ------------------
    #      Mapped to JLCPCB BASIC parts (UNI-ROYAL 0805W8F, value/size/1% tol
    #      identical -> board unchanged, no per-part setup fee). Exceptions
    #      noted where the Basic value was OOS.
    "RC0805FR-07100KL": _e("C96346",  "RC0805FR-07100KL (Yageo)", note="exact design part; Basic C17407 went short -- reverted to Yageo 100k (in stock)"),
    "RC0805FR-0739KL":  _e("C113306", "RC0805FR-0739KL (Yageo)",       note="exact MPN (Basic 39k was OOS); in stock"),
    "RC0805FR-0710KL":  _e("C17414",  "0805W8F1002T5E", tier="BASIC", note="JLC-Basic equiv 10k 0805 1%"),
    "RC0805FR-075K1L":  _e("C27834",  "0805W8F5101T5E", tier="BASIC", note="JLC-Basic equiv 5.1k 0805 1%"),
    "RC0805FR-0747KL":  _e("C17713",  "0805W8F4702T5E", tier="BASIC", note="JLC-Basic equiv 47k 0805 1%"),
    "RC0805FR-0733RL":  _e("C17634",  "0805W8F330LT5E", tier="BASIC", note="JLC-Basic equiv 33R 0805 1%"),
    "RC0805FR-07120RL": _e("C17437",  "0805W8F1200T5E", tier="BASIC", note="JLC-Basic equiv 120R 0805 1%"),
    "RC0805FR-071KL":   _e("C17513",  "0805W8F1001T5E", tier="BASIC", note="JLC-Basic equiv 1k 0805 1%"),
    "RC0805FR-0715KL":  _e("C17475",  "0805W8F1502T5E", tier="BASIC", note="JLC-Basic equiv 15k 0805 1%"),
    "RC0805FR-07220KL": _e("C17556",  "0805W8F2203T5E", tier="BASIC", note="JLC-Basic equiv 220k 0805 1%"),
    "RC0805FR-07110KL": _e("C2907221", "FRC0805F1103TS (FOJAN)",
                            note="SUB: prior C17422 (0805W8F1103T5E) went OOS at JLC; FOJAN 110k 0805 "
                                 "1% same footprint, good stock ~28.2k -- verified 2026-07-20"),
    "RC0805FR-0711KL":  _e("C17429",  "0805W8F1102T5E", tier="BASIC", note="JLC-Basic equiv 11k 0805 1%"),
    "RC0805FR-074K7L":  _e("C17673",  "0805W8F4701T5E", tier="BASIC", note="JLC-Basic equiv 4.7k 0805 1%"),
    "RC0805FR-07220RL": _e("C17557",  "0805W8F2200T5E", tier="BASIC", note="JLC-Basic equiv 220R 0805 1%"),

    # ---- caps: 0805 + 1210 (design=Samsung CL21/CL32) -----------------------
    #      0805 values map to JLC BASIC MLCC; 1210 25V values have no Basic
    #      part, so real Extended 1210 MLCC (same footprint, >=25V). All
    #      voltage ratings preserved or higher.
    "CL32B106KBJNNNE": _e("C39232",  "10uF 25V 1210 X7R", note="1210 equiv (no Basic 1210); >=25V"),
    "CL21B104KBCNNNC": _e("C49678",  "100nF 50V 0805 X7R", tier="BASIC", note="JLC-Basic equiv 100nF"),
    "CL21A226KPCLRNC": _e("C45783",  "22uF 10V 0805 X5R",  tier="BASIC", note="JLC-Basic equiv 22uF 0805"),
    "CL21B105KAFNNNE": _e("C28323",  "1uF 25V 0805 X7R",   tier="BASIC", note="JLC-Basic equiv 1uF"),
    "CL21A106KPFNNNE": _e("C15850",  "10uF 10V 0805 X5R",  tier="BASIC", note="JLC-Basic equiv 10uF 0805"),
    "CL32A226KAJNNNE": _e("C52306",  "CL32A226KAJNNNE (Samsung)", note="exact design part 1210 22uF 25V; generic C307586 went short -- reverted to Samsung (in stock)"),
}
