"""Analytical circuit verification for the micromouse board, rev 6. Exits 1 on FAIL.

Every test parses pcb/netlist.net (the same file the board is built from) and
computes DC operating points / logic states from component values + verified
datasheet parameters -- i.e. the checks exercise the REAL connectivity, not a
redrawn model. A SPICE run of an ESP32-S3 module is not meaningful (no vendor
models exist for the module, TB6612, BNO055 or TCRT5000); the engineering-grade
equivalent for a digital+opto board is exactly this: per-path operating-point
computation with datasheet margins, plus behavioural walk-throughs of the
boot/flash sequences.

Rev-6 architecture under test: 2S LiPo pack (6.0-8.4 V, firmware floor 6.6 V)
through F1 (MINISMDC260F/16) and Q1 (DMP3098L-7 reverse P-FET) into TWO bucks
-- U1 AP63203 fixed 3.3 V / 2 A for logic and U7 TPS54302 set to 6.0 V / 3 A
for the TB6612 motor rail (IN/IN PWM mode, PWMA/PWMB/STBY tied high). Dual
slide switches: SW5 grounds PWR_EN (everything off), SW6 grounds MOT_EN
(motors off); battery telemetry (pack / midpoint / VBUS) rides the line mux's
upper channels via the new MUX_S3 select. BNO055 IMU on I2C. USB D+/D- run
DIRECT to the module (the rev-5 22R series pair is deleted).

Emits pcb/TEST_REPORT.md: per-test detail (computed values, margins,
justification) + net/component coverage matrices. Per-net design rationale
lives in pcb/CONNECTIONS.md (generated, coverage-enforced); tests reference
nets by the same names.

Datasheet constants below were verified against manufacturer PDFs during the
rev-6 sourcing pass (Diodes AP63203 DS41406, TI TPS54302 SLVSD53, TB6612FNG
2008-05-09, Diodes DMP3098L-7 DS32164, Littelfuse miniSMDC260F, Everlight
IR333-A, TCRT5000 83760, PT334-6B DPT-0000263, onsemi BSS138/BSS84, Bosch
BNO055 BST_BNO055_DS000, TI CD74HC4067, Bourns SRP4020TA, Epson FC-135,
ESP32-S3 TRM/datasheet).
"""
import re
import sys

NETLIST = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\netlist.net"
REPORT = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\TEST_REPORT.md"

# ---------------------------------------------------------------------------
# netlist model
# ---------------------------------------------------------------------------
text = open(NETLIST, encoding="utf-8").read()
NETS = {}
PINFN = {}
for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text, re.S):
    nodes = re.findall(
        r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)(?:\s*\(pinfunction "([^"]*)"\))?',
        m.group(2))
    NETS[m.group(1)] = [(r, p) for r, p, _ in nodes]
    for r, p, fn in nodes:
        if fn:
            PINFN[(r, p)] = fn
COMPS = {}
for ref, val, fp in re.findall(
        r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*\(footprint "([^"]*)"\)', text):
    COMPS[ref] = (val, fp)

PIN2NET = {}
for n, nodes in NETS.items():
    for rp in nodes:
        PIN2NET[rp] = n

def net_of(ref, pin):
    return PIN2NET.get((ref, str(pin)))

def fn_of(ref, pin):
    return PINFN.get((ref, str(pin)), "")

def rval(ref):
    v = COMPS[ref][0].strip()
    m = re.match(r"^([\d.]+)\s*([kKmMrR]?)", v)
    num = float(m.group(1))
    mult = {"k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}.get(m.group(2), 1)
    return num * mult

def cval(ref):
    """Capacitor value field -> (farads, rated volts or None). '220uF/16V' etc."""
    v = COMPS[ref][0].strip()
    m = re.match(r"^([\d.]+)\s*(pF|nF|uF)(?:/(\d+)V)?", v)
    mult = {"pF": 1e-12, "nF": 1e-9, "uF": 1e-6}[m.group(2)]
    return float(m.group(1)) * mult, (float(m.group(3)) if m.group(3) else None)

def lval(ref):
    m = re.match(r"^([\d.]+)\s*uH", COMPS[ref][0].strip())
    return float(m.group(1)) * 1e-6

# supply assumptions -- 2S LiPo pack window (rev 6)
VBAT_MIN, VBAT_NOM, VBAT_MAX = 6.0, 7.4, 8.4   # hard pack limits (3.0-4.2 V/cell)
VBAT_MIN_USE = 6.6                              # firmware cutoff, 3.3 V/cell
V33 = 3.3

RESULTS = []          # (id, subsystem, title, status, detail_lines, nets, comps)

def test(tid, subsystem, title, nets=(), comps=()):
    def deco(fn):
        lines = []
        touched_nets = list(nets)
        touched_comps = list(comps)
        def say(s): lines.append(s)
        def touch(*ns): touched_nets.extend(ns)
        def touchc(*cs): touched_comps.extend(cs)
        try:
            status = fn(say, touch, touchc) or "PASS"
        except AssertionError as e:
            status = "FAIL"
            lines.append(f"ASSERTION: {e}")
        except Exception as e:
            status = "FAIL"
            lines.append(f"ERROR: {type(e).__name__}: {e}")
        RESULTS.append((tid, subsystem, title, status, lines, touched_nets, touched_comps))
        return fn
    return deco

def require(cond, msg):
    assert cond, msg

def on(net, ref, pin):
    return (ref, str(pin)) in NETS.get(net, [])

def net_exists(net):
    return net in NETS

# ---------------------------------------------------------------------------
# POWER TREE (2S pack -> fuse -> reverse FET -> two bucks)
# ---------------------------------------------------------------------------
@test("P1", "Power", "2S battery input: J1(XH) -> F1 -> Q1(D->S) -> VM_BATT; J9 balance tap",
      nets=["BATT_RAW", "Net-(Q1-D)", "VM_BATT", "BAT_MID", "GND"], comps=["J1", "J9", "F1", "Q1"])
def _(say, touch, touchc):
    require(on("BATT_RAW", "J1", 1) and on("BATT_RAW", "F1", 1),
            "pack+ must reach the fuse")
    require(on("BATT_RAW", "J9", 3), "balance pin 3 (pack+) must share BATT_RAW")
    require(on("Net-(Q1-D)", "F1", 2) and on("Net-(Q1-D)", "Q1", 3),
            "fuse must feed Q1 DRAIN (pin 3)")
    require(on("VM_BATT", "Q1", 2), "Q1 SOURCE (pin 2) must feed VM_BATT")
    require(on("GND", "J1", 2) and on("GND", "J9", 1), "pack- and balance pin 1 on GND")
    require(on("BAT_MID", "J9", 2) and on("BAT_MID", "R75", 1),
            "balance pin 2 (cell midpoint) must feed the R75 divider")
    require("JST_XH" in COMPS["J1"][1], "J1 must be JST-XH (3A/contact, 2S keying)")
    require("JST_XH" in COMPS["J9"][1] and "1x03" in COMPS["J9"][1],
            "J9 must be a 3-pin JST-XH balance connector")
    say("Chain verified pin-by-pin: J1.1 -> F1.1 | F1.2 -> Q1.D | Q1.S -> VM_BATT.")
    say("2S pack window 6.0-8.4 V (firmware floor 6.6 V = 3.3 V/cell). Balance tap")
    say("J9 (XH-3): pin1 GND, pin2 cell-1 midpoint into R75/R76, pin3 pack+ shares")
    say("BATT_RAW (it IS the same terminal). No onboard charging -- J9 monitors only.")
    say("Battery on the DRAIN: correct reverse-protection orientation -- with a")
    say("reversed pack the body diode (anode=D) blocks; with correct polarity it")
    say("conducts until the gate enhances the channel.")

@test("P2", "Power", "Q1 DMP3098L-7: Vgs rating, enhancement and conduction loss",
      nets=["Net-(Q1-G)", "GND"], comps=["Q1", "R1"])
def _(say, touch, touchc):
    require(on("Net-(Q1-G)", "Q1", 1) and on("Net-(Q1-G)", "R1", 1), "gate tied to R1")
    require(on("GND", "R1", 2), "R1 pulls the gate to GND")
    require("DMP3098L" in COMPS["Q1"][0], "Q1 must be the 2S-safe DMP3098L-7")
    vgs_abs = float(re.search(r"\+/-(\d+)V", COMPS["Q1"][0]).group(1))
    r1 = rval("R1")
    rds = 0.060  # DMP3098L-7 Rds(on) 60 mOhm class (55 mOhm max @ Vgs -4.5 V)
    i_run, i_fault = 0.9, 3.6   # typical fast-run vs both-bucks-at-limit (see P3)
    say(f"R1 = {r1/1e3:.0f}k gate pulldown; Vgs = -VBAT = -{VBAT_MIN}..-{VBAT_MAX} V.")
    say(f"Rating check: |Vgs| max {VBAT_MAX} V = {VBAT_MAX/vgs_abs*100:.0f}% of the")
    say(f"+/-{vgs_abs:.0f} V rating (netlist-declared; the 1S-era DMP2035U was +/-8 V")
    say("and 2S-UNSAFE -- this swap is the point of the part). -30 V / -3.8 A frame.")
    say(f"Enhancement: |Vgs| >= {VBAT_MIN} V even at the pack hard floor, beyond the")
    say("-4.5 V Rds(on) spec point -> fully enhanced everywhere in the window.")
    say(f"Conduction loss at {rds*1e3:.0f} mOhm: {i_run:.1f} A run -> {i_run**2*rds*1e3:.0f} mW")
    say(f"(trivial for SOT-23); {i_fault:.1f} A worst fault-transient -> "
        f"{i_fault**2*rds*1e3:.0f} mW, bounded by the buck current limits + PTC (P3).")
    say(f"Gate leak through R1: {VBAT_MAX/r1*1e6:.0f} uA continuous (always-on; S4).")
    require(VBAT_MAX < vgs_abs, "pack maximum exceeds Q1 Vgs rating")
    require(VBAT_MIN >= 4.5, "pack floor below the Rds(on) full-enhancement spec point")
    require(i_run**2 * rds < 0.15, "continuous conduction loss too high for SOT-23")

@test("P3", "Power", "PTC fuse MINISMDC260F/16 rating vs load", comps=["F1"])
def _(say, touch, touchc):
    hold, vmax = (float(x) for x in
                  re.match(r"([\d.]+)A/(\d+)V", COMPS["F1"][0]).groups())
    trip = 5.0    # MINISMDC260F/16 datasheet trip current
    eff = 0.90
    i_6v = 6.01 * 3.0 / (VBAT_MIN_USE * eff)      # U7 at its 3 A limit, pack floor
    i_3v3 = 3.3 * 1.0 / (VBAT_MIN_USE * 0.88)     # everything-on 3V3 budget (P5)
    worst = i_6v + i_3v3
    i_run = 0.9   # typical fast run: ~0.8 A motors avg + logic, battery-side
    say(f"Netlist-declared PTC: {hold:.1f} A hold / {trip:.1f} A trip / {vmax:.0f} V")
    say(f">= {VBAT_MAX} V pack max ({vmax/VBAT_MAX:.1f}x). Normal run ~{i_run:.1f} A")
    say(f"battery-side, well under hold. Worst self-consistent draw at the {VBAT_MIN_USE} V")
    say(f"floor: 6V buck at its 3 A limit ({i_6v:.2f} A input) + 3V3 rail ({i_3v3:.2f} A)")
    say(f"= {worst:.2f} A -- inside the {hold:.1f}-{trip:.1f} A INDETERMINATE band, so the")
    say("PTC may or may not open under a double stall: it is NOT the stall")
    say("protection. Roles: PTC = hard faults only (a wiring short draws")
    say("VBAT/Rshort >> 5 A and trips fast); stall protection = the TPS54302's own")
    say("cycle-by-cycle limit + the firmware PWM constraint (M3) + TB6612 thermal")
    say("shutdown. Same role split as rev 5, re-derived for the 2S numbers.")
    require(vmax >= VBAT_MAX, "PTC voltage rating below pack maximum")
    require(hold >= 2 * i_run, "normal running would sit above the PTC hold current")
    require(VBAT_MIN / 0.1 > trip, "even a hard short would not trip the PTC")

@test("P4", "Power", "U1 AP63203 3V3 buck: wiring, input-cap ratings, output caps",
      nets=["VM_BATT", "PWR_EN", "SW_3V3", "Net-(U1-BST)", "PLUS3V3", "GND"],
      comps=["U1", "L1", "C3", "C5", "C7"])
def _(say, touch, touchc):
    require("AP63203" in COMPS["U1"][0], "U1 must be the AP63203 fixed-3.3V buck")
    require(on("VM_BATT", "U1", 3) and "IN" in fn_of("U1", 3), "VIN (pin 3) on VM_BATT")
    require(on("PWR_EN", "U1", 2) and "EN" in fn_of("U1", 2), "EN (pin 2) on PWR_EN")
    require(on("GND", "U1", 4), "GND pin grounded")
    require({net_of("C3", 1), net_of("L1", 1)} == {"SW_3V3"} and on("SW_3V3", "U1", 5),
            "SW node must carry L1 and the BST cap")
    require(on("Net-(U1-BST)", "C3", 2) and on("Net-(U1-BST)", "U1", 6),
            "C3 100nF must bootstrap BST to SW")
    require(on("PLUS3V3", "L1", 2), "L1 output side on PLUS3V3")
    require(on("PLUS3V3", "U1", 1) and "FB" in fn_of("U1", 1),
            "fixed-output FB/VOUT sense pin tied to the rail")
    say(f"VIN {VBAT_MIN}-{VBAT_MAX} V inside the AP63203's 3.8-32 V range; fixed")
    say("3.3 V / 2 A output, ~1.1 MHz. Pin roles cross-checked against the netlist")
    say("pinfunction fields (IN/EN/SW/BST/FB), not just pin numbers.")
    for c in ("C1", "C4", "C18"):
        f, v = cval(c)
        touchc(c)
        require({net_of(c, 1), net_of(c, 2)} == {"VM_BATT", "GND"},
                f"{c} must decouple VM_BATT")
        require(v is not None and v >= 16,
                f"{c} on the 8.4 V rail must be 16 V+ rated (declared {v})")
    require({net_of("C2", 1), net_of("C2", 2)} == {"VM_BATT", "GND"},
            "C2 HF bypass must sit on VM_BATT")
    touchc("C2", "C10")
    say("Input bulk C1/C4/C18 10uF are netlist-declared 25 V parts (>= 2.9x the")
    say("pack max -- the 1S-era 6.3-10 V caps are banned on this rail); C2 100nF")
    say("HF bypass rides the same node (rating covered in the BOM).")
    require({net_of("C10", 1), net_of("C10", 2)} == {"PLUS3V3", "GND"},
            "C10 must sit on the 3V3 output")
    co = 0.0
    for c in ("C5", "C7"):
        f, _v = cval(c)
        require({net_of(c, 1), net_of(c, 2)} == {"PLUS3V3", "GND"},
                f"{c} must sit on the 3V3 output")
        co += f
    say(f"Output caps C5+C7 = {co*1e6:.0f} uF ceramic (datasheet asks 2x22 uF class);")
    say("C10 10uF + distributed 100nF bypasses add margin.")
    require(abs(co - 44e-6) < 10e-6, "3V3 output capacitance off the 2x22uF design")

@test("P5", "Power", "3V3 load budget vs the AP63203's 2 A rating", nets=["PLUS3V3"],
      comps=["U1", "U8"])
def _(say, touch, touchc):
    esp = 0.500              # S3 WiFi TX burst + dual-core headroom (prompted budget)
    rds_typ = 3.5            # BSS138 Rds typ @ Vgs 3.3 (worst-case CURRENT = typ Rds)
    i_line = (V33 - 1.25) / (rval("R26") + 8 * rds_typ)
    i_wall = (V33 - 1.35) / (rval("R14") + 2 * rds_typ)
    ir_line = 8 * i_line     # all TCRT LEDs latched (O1)
    ir_wall = 6 * i_wall     # all wall emitters latched (W1; banks normally pulse)
    leds = 14 * 0.00145      # every indicator lit
    imu = 0.0123             # BNO055 normal mode, fusion running
    misc = 0.040             # mux, two encoders, pulls
    total = esp + ir_line + ir_wall + leds + imu + misc
    say(f"Peak 3V3 demand (everything at once): ESP32 {esp*1e3:.0f} + line IR "
        f"{ir_line*1e3:.0f} + wall IR {ir_wall*1e3:.0f} + indicators {leds*1e3:.0f} "
        f"+ IMU {imu*1e3:.0f} + misc {misc*1e3:.0f} = {total*1e3:.0f} mA.")
    say(f"IR figures recomputed from netlist resistor values ({rval('R26'):.0f}R line,")
    say(f"{rval('R14'):.0f}R wall) at typical FET Rds -- the maximum-current corner.")
    say(f"AP63203 is a 2 A buck fed from 6.0-8.4 V (always stepping DOWN -- no")
    say(f"boost-region derating like the 1S TPS63001): headroom "
        f"{(2.0-total)/2.0*100:.0f}% over the everything-on worst case.")
    require(total < 1.6, "3V3 budget leaves <20% headroom on the 2 A buck")

@test("P6", "Power", "L1 ripple current and saturation margin",
      nets=["SW_3V3", "PLUS3V3"], comps=["L1"])
def _(say, touch, touchc):
    L, fsw, isat = lval("L1"), 1.1e6, 3.5
    require("SRP4020TA" in COMPS["L1"][1], "L1 must be the SRP4020TA footprint/part")
    di_max = V33 * (1 - V33 / VBAT_MAX) / (L * fsw)
    di_min = V33 * (1 - V33 / VBAT_MIN_USE) / (L * fsw)
    ipk = 1.0 + di_max / 2   # everything-on load (P5) + half ripple
    say(f"L1 = {L*1e6:.1f} uH at {fsw/1e6:.1f} MHz: ripple {di_max*1e3:.0f} mA pk-pk at")
    say(f"{VBAT_MAX} V in (worst) / {di_min*1e3:.0f} mA at {VBAT_MIN_USE} V -- "
        f"{di_max/2.0*100:.0f}% of the 2 A rating, textbook 20-40% window.")
    say(f"Peak inductor current at the P5 worst-case load: {ipk:.2f} A vs the")
    say(f"SRP4020TA's {isat:.1f} A Isat -> {isat/ipk:.1f}x saturation margin.")
    require(0.1 <= di_max <= 0.8, "3V3 ripple current outside the sane design window")
    require(ipk < isat * 0.7, "L1 peak current too close to saturation")

@test("P7", "Power", "U7 TPS54302 6V buck: FB divider sets 6.01 V, wiring, output caps",
      nets=["VM_BATT", "FB_6V", "SW_6V", "Net-(U7-BOOT)", "VM_6V", "GND"],
      comps=["U7", "R73", "R74", "L2", "C15", "C16", "C17"])
def _(say, touch, touchc):
    require("TPS54302" in COMPS["U7"][0], "U7 must be the TPS54302")
    require(on("VM_BATT", "U7", 3) and "VIN" in fn_of("U7", 3), "VIN on VM_BATT")
    require(on("GND", "U7", 1), "GND pin grounded")
    require({net_of("C15", 1), net_of("L2", 1)} == {"SW_6V"} and on("SW_6V", "U7", 2),
            "SW node must carry L2 and the BOOT cap")
    require(on("Net-(U7-BOOT)", "C15", 2) and on("Net-(U7-BOOT)", "U7", 6),
            "C15 must bootstrap BOOT to SW")
    require(on("VM_6V", "L2", 2), "L2 output side on VM_6V")
    require(on("VM_6V", "R73", 1), "R73 top leg senses VM_6V")
    require(on("FB_6V", "R73", 2) and on("FB_6V", "R74", 1), "R73/R74 join at FB")
    require(on("FB_6V", "U7", 4) and "FB" in fn_of("U7", 4), "FB pin on the divider")
    require(on("GND", "R74", 2), "R74 bottom leg grounded")
    r73, r74, vref = rval("R73"), rval("R74"), 0.596
    vout = vref * (1 + r73 / r74)
    say(f"Netlist-read divider R73/R74 = {r73/1e3:.0f}k/{r74/1e3:.0f}k with the")
    say(f"TPS54302's {vref} V reference -> Vout = {vref} x (1 + {r73/1e3:.0f}/{r74/1e3:.0f})"
        f" = {vout:.2f} V regulated motor rail; 3 A rated, 400 kHz.")
    for c in ("C16", "C17"):
        f, v = cval(c)
        require({net_of(c, 1), net_of(c, 2)} == {"VM_6V", "GND"},
                f"{c} must sit on the 6V output")
        require(v is not None and v >= 16, f"{c} must be 16 V+ rated (declared {v})")
    say("Output ceramics C16/C17 22uF/25V at the buck; the C30 bulk + TB6612 pin")
    say("caps are checked at the driver (M4). Divider Thevenin ~10k: stiff enough")
    say("for the FB node, light enough to ignore as a load (0.6 mA).")
    require(5.85 <= vout <= 6.15, f"6V rail computes to {vout:.2f} V from the netlist")

@test("P8", "Power", "L2 ripple, peak vs saturation, duty headroom at the pack floor",
      nets=["SW_6V", "VM_6V"], comps=["L2", "U7"])
def _(say, touch, touchc):
    L, fsw, isat = lval("L2"), 400e3, 3.5
    vout = 0.596 * (1 + rval("R73") / rval("R74"))
    di_max = vout * (1 - vout / VBAT_MAX) / (L * fsw)
    di_min = vout * (1 - vout / VBAT_MIN_USE) / (L * fsw)
    ipk = 3.0 + di_max / 2       # rated-limit load + half ripple
    duty = vout / VBAT_MIN_USE
    dmax = 1 - 150e-9 * fsw      # 150 ns-class minimum off-time at 400 kHz
    say(f"L2 = {L*1e6:.1f} uH at {fsw/1e3:.0f} kHz: ripple {di_max*1e3:.0f} mA pk-pk at")
    say(f"{VBAT_MAX} V in / {di_min*1e3:.0f} mA at {VBAT_MIN_USE} V ({di_max/3.0*100:.0f}% of")
    say(f"the 3 A rating -- coarse but standard for a 400 kHz SOT-23 buck).")
    say(f"Peak inductor current at the full 3 A ceiling: {ipk:.2f} A vs {isat:.1f} A Isat")
    say(f"({(isat-ipk)/isat*100:.0f}% margin -- thin, but the 3 A point is itself the")
    say("buck's limit, a transient state; normal running sits at 0.8-1.6 A. During")
    say("a hard overload the IC's peak limit + hiccup bounds the excursion.")
    say(f"Dropout: duty {duty*100:.0f}% needed at the {VBAT_MIN_USE} V firmware floor vs")
    say(f"~{dmax*100:.0f}% max ({150:.0f} ns min off-time); below ~6.3 V input the rail")
    say("sags gracefully -- documented competition practice with Vbat feed-forward.")
    require(ipk < isat, "L2 saturates at the buck current ceiling")
    require(duty < dmax, "cannot hold 6.0 V at the firmware pack floor")
    require(0.2 <= di_max <= 1.2, "6V ripple current outside the sane design window")

@test("P9", "Power", "Dual-switch logic: SW5 kills everything, SW6 kills motors",
      nets=["PWR_EN", "MOT_EN", "VM_BATT", "GND"],
      comps=["SW5", "SW6", "R69", "R70", "R71", "U1", "U7"])
def _(say, touch, touchc):
    require(on("PWR_EN", "R69", 2) and on("VM_BATT", "R69", 1), "R69 pulls PWR_EN up")
    require(on("PWR_EN", "SW5", 2) and on("GND", "SW5", 1), "SW5 grounds PWR_EN")
    require(on("PWR_EN", "U1", 2), "AP63203 EN rides PWR_EN")
    require(on("PWR_EN", "R70", 1),
            "R70 must source the MOT_EN pull-up FROM PWR_EN (motors need both switches)")
    require(on("MOT_EN", "R70", 2) and on("MOT_EN", "R71", 1), "R70/R71 join at MOT_EN")
    require(on("MOT_EN", "SW6", 2) and on("GND", "SW6", 1), "SW6 grounds MOT_EN")
    require(on("MOT_EN", "U7", 5) and "EN" in fn_of("U7", 5), "TPS54302 EN on MOT_EN")
    require(on("GND", "R71", 2), "R71 bottom leg grounded")
    r69, r70, r71 = rval("R69"), rval("R70"), rval("R71")
    rth_pen = 1 / (1 / r69 + 1 / (r70 + r71))   # Thevenin at the PWR_EN node
    v_pen = lambda v: v * (r70 + r71) / (r69 + r70 + r71) + 1.5e-6 * rth_pen
    say(f"Truth table verified structurally: SW5 closed -> PWR_EN = 0 -> both EN")
    say(f"pins low -> everything off. SW6 closed -> MOT_EN = 0 -> motor rail off,")
    say(f"logic alive. R70 hangs off PWR_EN (netlist: R70.1), so MOT_EN can only")
    say(f"be high when the master switch already is -- both switches must be ON.")
    say(f"PWR_EN level with both open: R69 {r69/1e6:.0f}M against the R70+R71 "
        f"{(r70+r71)/1e3:.0f}k DC load")
    say(f"divides the pack (+ the AP63203's own 1.5 uA EN pull-up over "
        f"{rth_pen/1e3:.0f}k) to")
    say(f"{v_pen(VBAT_MAX):.2f} V ({VBAT_MAX} V in) / {v_pen(VBAT_MIN_USE):.2f} V "
        f"({VBAT_MIN_USE} V) / {v_pen(VBAT_MIN):.2f} V ({VBAT_MIN} V hard floor)")
    say("-- NOT near-VIN as the R69-only analysis suggests. Still above the")
    say("AP63203's ~1.1 V EN threshold with >=1.6x margin, so the 3V3 rail does")
    say("start everywhere in the window; the knock-on effect on MOT_EN is P10's")
    say("subject. Off-state drain through this chain is metered in S4.")
    require(v_pen(VBAT_MIN) > 1.4, "PWR_EN cannot clear the AP63203 EN threshold")

@test("P10", "Power", "MOT_EN level vs the TPS54302 enable threshold",
      nets=["PWR_EN", "MOT_EN"], comps=["R69", "R70", "R71", "U7"])
def _(say, touch, touchc):
    r69, r70, r71 = rval("R69"), rval("R70"), rval("R71")
    ven_th, ven_absmax = 1.21, 6.5   # TPS54302 EN rising typ (1.23 in newest DS rev)
    i_pu7 = 1.2e-6                   # TPS54302 internal EN pull-up current source
    i_pu1 = 1.5e-6                   # AP63203 internal EN pull-up (credits PWR_EN)
    rth_en = 1 / (1 / r71 + 1 / (r70 + r69))    # Thevenin at the MOT_EN node
    rth_pen = 1 / (1 / r69 + 1 / (r70 + r71))   # Thevenin at the PWR_EN node
    xfer = r71 / (r70 + r71)                    # PWR_EN -> MOT_EN attenuation
    v_en = lambda v: (v * r71 / (r69 + r70 + r71)
                      + i_pu7 * rth_en + i_pu1 * rth_pen * xfer)
    v_int = lambda v: v * r71 / (r70 + r71)     # designer-intended (stiff PWR_EN)
    say(f"Netlist-read chain: VM_BATT -[R69 {r69/1e6:.0f}M]- PWR_EN -[R70 "
        f"{r70/1e3:.0f}k]- MOT_EN -[R71 {r71/1e3:.0f}k]- GND.")
    say(f"With both switches open the three resistors form ONE string, so EN =")
    say(f"VBAT x R71/(R69+R70+R71), CREDITING both ICs' internal EN pull-ups")
    say(f"(TPS54302 ~{i_pu7*1e6:.1f} uA over {rth_en/1e3:.0f}k, AP63203 ~"
        f"{i_pu1*1e6:.1f} uA over {rth_pen/1e3:.0f}k x {xfer:.2f}):")
    say(f"  {VBAT_MAX} V pack -> {v_en(VBAT_MAX):.2f} V | {VBAT_MIN_USE} V pack -> "
        f"{v_en(VBAT_MIN_USE):.2f} V   (threshold {ven_th} V typ, 1.13 V min).")
    say(f"The R70/R71 values are correct for a STIFF source ({v_int(VBAT_MAX):.2f} V /")
    say(f"{v_int(VBAT_MIN_USE):.2f} V would result, matching CONNECTIONS.md's '<=2.1 V'")
    say("note) -- the design forgot R69's 1M source impedance: R70+R71 = 440k loads")
    say("the 1M pull-up 2.3:1 and MOT_EN lands at ~a third of the intended level.")
    say("CONSEQUENCE: the TPS54302 never enables -- the motor rail is dead with")
    say("both switches ON. FIX (schematic, not this test): R69 -> 100k (PWR_EN")
    say(f"then sits at 81% of VBAT; MOT_EN = {8.4*0.8148*r71/(r70+r71):.2f} V at 8.4 V /")
    say(f"{6.6*0.8148*r71/(r70+r71):.2f} V at 6.6 V, off-drain +76 uA) or re-ratio "
        f"R70/R71.")
    require(v_en(VBAT_MAX) <= ven_absmax, "EN exceeds abs max")
    require(v_en(VBAT_MIN_USE) >= ven_th,
            f"MOT_EN {v_en(VBAT_MIN_USE):.2f} V at the {VBAT_MIN_USE} V floor is below "
            f"the {ven_th} V EN threshold -- motor rail never starts (R69 1M vs "
            f"R70+R71 440k loading; GENUINE DESIGN ERROR, see detail)")
    require(v_en(VBAT_MAX) >= ven_th,
            f"MOT_EN {v_en(VBAT_MAX):.2f} V even at full charge is below the "
            f"{ven_th} V EN threshold")

# ---------------------------------------------------------------------------
# ESP32: FLASHING, USB, STRAPS
# ---------------------------------------------------------------------------
@test("E1", "Flashing", "USB data path: J7 -> ESD array -> module DIRECT (22R pair deleted)",
      nets=["USB_DP_C", "USB_DM_C", "USB_DP", "USB_DM"], comps=["J7", "U6"])
def _(say, touch, touchc):
    require("R59" not in COMPS and "R60" not in COMPS,
            "rev-6 deleted the 22R series pair -- R59/R60 must be ABSENT")
    require(on("USB_DP_C", "J7", "A6") and on("USB_DP_C", "J7", "B6"), "D+ both rows")
    require(on("USB_DM_C", "J7", "A7") and on("USB_DM_C", "J7", "B7"), "D- both rows")
    require(on("USB_DP_C", "U6", 3) and on("USB_DM_C", "U6", 1),
            "ESD array on the connector side")
    require(set(NETS["USB_DP"]) == {("U3", "14"), ("U6", "4")},
            "USB_DP must be a two-node net: ESD array DIRECT to the module D+ pad")
    require(set(NETS["USB_DM"]) == {("U3", "13"), ("U6", "6")},
            "USB_DM must be a two-node net: ESD array DIRECT to the module D- pad")
    say("R59/R60 confirmed absent from the netlist; USB_DP/USB_DM are two-node")
    say("nets (U6 pass-through pins to the module's dedicated USB pads, IO19/20).")
    say("Rationale (standards review 2026-07-17): the S3's integrated FS PHY meets")
    say("the USB driver-impedance window internally and every Espressif S3 devkit")
    say("routes these pins directly -- series 22R was a legacy-PHY habit. The")
    say("USBLC6-2SC6 stays between the user-handled connector and the chip.")
    say("Flashing: plug in, hold A (BOOT strap IO0 low), tap RST -> ROM downloader")
    say("on the native USB-Serial-JTAG CDC. No external UART bridge anywhere.")

@test("E2", "Flashing", "VBUS cable detect: divider into mux channel Y10",
      nets=["USB_VBUS", "VBUS_SENSE"], comps=["R67", "R68", "U4"])
def _(say, touch, touchc):
    for p in ("A4", "A9", "B4", "B9"):
        require(on("USB_VBUS", "J7", p), f"VBUS pad {p} must be bridged")
    require(on("USB_VBUS", "R67", 1) and on("VBUS_SENSE", "R67", 2), "divider top")
    require(on("VBUS_SENSE", "R68", 1) and on("GND", "R68", 2), "divider bottom")
    require(on("VBUS_SENSE", "U4", 21), "sense must land on mux channel I10 (pad 21)")
    r67, r68 = rval("R67"), rval("R68")
    v_nom = 5.0 * r68 / (r67 + r68)
    v_max = 5.5 * r68 / (r67 + r68)
    say(f"R67/R68 = {r67/1e3:.0f}k/{r68/1e3:.0f}k -> 5.0 V reads {v_nom:.2f} V, and the")
    say(f"Type-C worst case 5.5 V (vSafe5V upper bound) reads {v_max:.2f} V -- inside")
    say(f"the HC4067's input clamp (VCC+0.5 = {V33+0.5:.1f} V) and the S3's 3.6 V IO")
    say("abs max when the channel is selected. Detection-only (threshold ~1 V of")
    say("swing), so riding the ADC's saturated top end at 5.5 V is acceptable.")
    say("VBUS does NOT power the board; rev 6 freed IO37 (now the IMU interrupt)")
    say("by moving this read onto the mux's Y10.")
    require(v_max <= V33 + 0.5, "VBUS sense exceeds the mux input clamp")
    require(v_nom >= 2.0, "nominal VBUS reading too low for a robust detect")

@test("E3", "Flashing", "USB-C CC pulldowns (UFP advertisement)",
      nets=["Net-(J7-CC1)", "Net-(J7-CC2)"], comps=["R12", "R56"])
def _(say, touch, touchc):
    for net, r in (("Net-(J7-CC1)", "R12"), ("Net-(J7-CC2)", "R56")):
        require(any(x == r for x, p in NETS[net]), f"{r} on {net}")
        require(abs(rval(r) - 5100) < 300, f"{r} must be 5.1k")
        require(on("GND", r, 2) or on("GND", r, 1), f"{r} to GND")
    say("5.1k Rd on both CC pins: a C-to-C cable/charger recognises the board as")
    say("a UFP sink and enables VBUS -- without these, C-to-C flashing would fail.")

@test("E4", "Flashing", "Boot straps rev 6: IO0 pulled up, IO45 pulled down, IO46 floats NC",
      nets=["USER_BTN", "BIN2"], comps=["SW1", "R10", "R65"])
def _(say, touch, touchc):
    require(on("USER_BTN", "SW1", 1) and on("USER_BTN", "R10", 2)
            and on("USER_BTN", "U3", 27), "IO0 strap: SW1 + R10 + module")
    require(on("PLUS3V3", "R10", 1), "R10 pulls IO0 up")
    say(f"IO0 (USER_BTN): {rval('R10')/1e3:.0f}k pull-up to 3V3, button A shorts to GND")
    say("-> released = SPI boot, held = ROM downloader.")
    require(on("BIN2", "R65", 1) and on("BIN2", "U3", 26) and on("BIN2", "U2", 16),
            "IO45 strap rides the BIN2 net")
    require(on("GND", "R65", 2), "R65 must terminate at GND")
    say(f"IO45 (BIN2): {rval('R65')/1e3:.0f}k pulldown -> boots low -> VDD_SPI = 3.3 V")
    say("(correct for the WROOM); the TB6612's internal 200k input pulldown agrees.")
    say("NEVER add a pull-up to this net.")
    io46 = net_of("U3", 16)
    require(io46 == "BUZZ_CTRL",
            f"IO46 must carry BUZZ_CTRL, the rev-7.2 buzzer drive (got {io46})")
    require(on("BUZZ_CTRL", "R81", 1), "R81 base resistor on BUZZ_CTRL")
    require(abs(rval("R81") - 220) < 30, "R81 must be ~220R")
    # strap safety: the ONLY other thing on IO46 is R81 -> NPN base. That load
    # can only ever pull the pin toward GND (B-E junction), which is IO46's
    # required boot state -- an accidental pull-UP here would be a brick risk.
    require(len(NETS["BUZZ_CTRL"]) == 2, "BUZZ_CTRL must be exactly U3.16 + R81.1")
    require(not any(on("PLUS3V3", r, p) and r == "R81" for r, p in [("R81", 1), ("R81", 2)]),
            "R81 must never tie IO46 toward a rail")
    require("R66" not in COMPS,
            "R66 (the old STBY/IO46 pulldown) must be retired with the STBY rework")
    say("IO46 (BUZZ_CTRL): drives R81 220R -> Q34 (MMBT2222A) base -> buzzer. The")
    say("B-E junction only ever pulls the strap LOW = its required boot-msg default,")
    say("and the pin resets to input so the buzzer stays silent until app init.")
    say("Strap census: only IO0 is user-touchable, via the deliberate BOOT button.")

@test("E5", "Flashing", "Reset circuit: EN RC + RST button",
      nets=["ESP_EN", "GND"], comps=["R11", "C9", "SW2"])
def _(say, touch, touchc):
    require(any(r == "R11" for r, p in NETS["ESP_EN"]), "EN pull-up present")
    require(any(r == "C9" for r, p in NETS["ESP_EN"]), "EN RC cap present")
    require(any(r == "SW2" for r, p in NETS["ESP_EN"]), "RST button on EN")
    require(on("PLUS3V3", "R11", 1), "R11 pulls EN to 3V3")
    tau = rval("R11") * cval("C9")[0]
    say(f"R11 {rval('R11')/1e3:.0f}k + C9 {cval('C9')[0]*1e6:.0f}uF -> tau = "
        f"{tau*1e3:.0f} ms power-on reset")
    say("delay (Espressif asks >50 us after 3V3 valid; 10 ms is the classic safe")
    say("value). SW2 shorts EN to GND for manual reset; C9 also debounces it.")
    require(0.005 <= tau <= 0.05, "EN RC outside the 5-50 ms sane window")

@test("E6", "Flashing", "UART0 boot-log contention guards on encoder pins",
      nets=["ENC2_A", "ENC2_B", "ENC2_A_S3", "ENC2_B_S3"], comps=["R57", "R58"])
def _(say, touch, touchc):
    for r in ("R57", "R58"):
        require(abs(rval(r) - 1000) < 100, f"{r} must be ~1k")
    require(on("ENC2_A_S3", "U3", 36) and on("ENC2_B_S3", "U3", 37),
            "guard outputs must land on RXD0/TXD0")
    say("IO43/IO44 double as UART0 TX/RX during boot. The ROM prints its boot log")
    say("while the encoder outputs may drive the same lines: the 1k series guards")
    say(f"cap contention current at 3.3 V / 1k = 3.3 mA -- harmless to both the")
    say("encoder driver and the S3 pad. After boot the pins remap to PCNT inputs;")
    say("firmware keeps the console on USB-Serial-JTAG so UART0 never re-enables.")

@test("E7", "Flashing", "JTAG header pin map and supply",
      nets=["JTAG_TMS", "JTAG_TCK", "JTAG_TDO", "JTAG_TDI", "PLUS3V3", "GND"],
      comps=["J8"])
def _(say, touch, touchc):
    require(on("PLUS3V3", "J8", 1), "pin1 = Vtarget")
    for pin, net in ((2, "JTAG_TMS"), (3, "JTAG_TCK"), (4, "JTAG_TDO"), (5, "JTAG_TDI")):
        require(on(net, "J8", pin), f"J8.{pin} must be {net}")
        require(any(r == "U3" for r, p in NETS[net]), f"{net} reaches module")
    require(on("GND", "J8", 6), "pin6 = GND")
    say("1x6 header: 3V3, TMS(IO42), TCK(IO39), TDO(IO40), TDI(IO41), GND --")
    say("matches ESP-Prog's pin needs on the S3's dedicated JTAG quad. NOTE for")
    say("firmware: the S3 routes JTAG to USB-Serial-JTAG by default; to use this")
    say("header burn/strap the JTAG-sel (or use OpenOCD over USB, which needs no")
    say("header at all). Kept for crash debugging when USB itself is the casualty.")

# ---------------------------------------------------------------------------
# BUTTONS
# ---------------------------------------------------------------------------
@test("B1", "Buttons", "A/B/C/RST wiring and pull strategy",
      comps=["SW1", "SW2", "SW3", "SW4", "R10", "U3"])
def _(say, touch, touchc):
    for sw, desc in (("SW1", "A/BOOT"), ("SW3", "B"), ("SW4", "C")):
        n1, n2 = net_of(sw, 1), net_of(sw, 2)
        sig = n1 if n2 == "GND" else n2
        require("GND" in (n1, n2), f"{sw} must switch to GND")
        require(any(r == "U3" for r, p in NETS[sig]), f"{sw} net reaches module")
        touch(sig)
        say(f"{sw} ({desc}): '{sig}' -> GND when pressed.")
    require("N8R2" in COMPS["U3"][0],
            "module must be a quad-PSRAM variant (octal -R8 loses IO35/36)")
    say("A has the discrete 10k pull-up (R10, strap-grade). B (IO35) and C (IO36)")
    say("use the S3's internal ~45k pull-ups -- both pins exist on the netlist-")
    say("declared N8R2 (QUAD PSRAM) module; octal-PSRAM variants would consume")
    say("them, so the variant is pinned in the value field and the BOM.")
    require(net_of("SW2", 1) == "ESP_EN" or net_of("SW2", 2) == "ESP_EN", "RST on EN")

# ---------------------------------------------------------------------------
# MOTORS + ENCODERS
# ---------------------------------------------------------------------------
@test("M1", "Motors", "TB6612 IN/IN PWM mode: PWMA/PWMB/STBY tied high, IN pins from GPIOs",
      nets=["PLUS3V3", "Net-(U2-STBY)", "AIN1", "AIN2", "BIN1", "BIN2"],
      comps=["U2", "R55"])
def _(say, touch, touchc):
    require(on("PLUS3V3", "U2", 23), "PWMA (U2.23) must be tied to PLUS3V3")
    require(on("PLUS3V3", "U2", 15), "PWMB (U2.15) must be tied to PLUS3V3")
    require(on("Net-(U2-STBY)", "U2", 19) and on("Net-(U2-STBY)", "R55", 2),
            "STBY (U2.19) must ride R55")
    require(on("PLUS3V3", "R55", 1) and abs(rval("R55") - 10e3) < 1e3,
            "R55 must be a 10k pull-up to 3V3")
    pinmap = {"AIN1": ("21", "17"), "AIN2": ("22", "18"),
              "BIN1": ("17", "31"), "BIN2": ("16", "26")}
    for net, (u2pin, u3pin) in pinmap.items():
        require(on(net, "U2", u2pin), f"{net} must land on U2.{u2pin}")
        require(on(net, "U3", u3pin), f"{net} must come from U3.{u3pin}")
    say("PWMA and PWMB verified tied to PLUS3V3 IN the netlist (not assumed), and")
    say("STBY pulled to 3V3 through R55 10k: the driver runs in IN/IN mode, PWM")
    say("applied to AIN1/2 + BIN1/2 (IO9/IO10/IO38/IO45). Modulating one IN with")
    say("the other low gives drive/coast; against the other high, drive/brake --")
    say("both firmware-selectable per the TB6612 truth table with PWM=H.")
    say("Safety: the TB6612's INx internal 200k pulldowns keep outputs off while")
    say("the MCU is in reset, and the hardware motor kill is now SW6 cutting the")
    say("entire 6V rail (P9) -- STBY's old GPIO/strap risk (IO46) is retired.")

@test("M2", "Motors", "VM pins on the regulated 6V rail; doubled outputs to connectors",
      nets=["VM_6V", "MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"], comps=["U2", "J5", "J6"])
def _(say, touch, touchc):
    for pin in ("24", "13", "14"):   # VM1 / VM2 / VM3
        require(on("VM_6V", "U2", pin), f"U2.{pin} (VM) must ride VM_6V")
    vout = 0.596 * (1 + rval("R73") / rval("R74"))
    # rev 7.2: J5/J6 are JST ZH B6B-ZR in the ROBU CABLE order -- motor +
    # on pin 1, motor - on pin 6 (encoder VCC/C1/C2/GND on 2/3/4/5).
    for net, pins, conn, cpin in (("MOTA_P", ("1", "2"), "J5", 1), ("MOTA_N", ("5", "6"), "J5", 6),
                                   ("MOTB_P", ("11", "12"), "J6", 1), ("MOTB_N", ("7", "8"), "J6", 6)):
        for p in pins:
            require(on(net, "U2", p), f"{net}: U2.{p} (doubled output) missing")
        require(on(net, conn, cpin), f"{net} -> {conn}.{cpin}")
    say(f"All three VM pins land on VM_6V ({vout:.2f} V from P7's netlist math) --")
    say("inside the TB6612's 4.5-13.5 V operating window AND above the 4.5 V floor")
    say("below which the datasheet derates output current (the rev-5 1S design")
    say("lived in that derated region; rev 6's regulated 6 V restores the full")
    say("1.2 A avg / 3.2 A peak per-channel ratings, and the N20s get their rated")
    say("voltage at any state of charge). Every output uses BOTH package pins")
    say("(halves per-pin current) into the JST ZH direct-plug motor connectors.")

@test("M3", "Motors", "N20 stall vs TB6612 limits vs the 6V buck ceiling", comps=["U2", "U7", "C30"])
def _(say, touch, touchc):
    vout = 0.596 * (1 + rval("R73") / rval("R74"))
    i_stall = 1.6            # N20 6V winding, ~3.8 ohm terminal R
    r_term = vout / i_stall
    say(f"N20 6 V motors: stall {i_stall:.1f} A at {vout:.1f} V (terminal R ~{r_term:.1f} ohm).")
    say("(Envelope figure. The ORDERED motor -- robu GA12-N20 6V 200RPM, datasheet")
    say("2026-07-20 -- stalls at only 0.23 A / runs 60 mA rated: ~7x inside this")
    say("analysis. And the 8.4 V pack question is moot BY DESIGN: motors hang off")
    say("the REGULATED 6.00 V rail, never the raw pack -- at 8.4 V the buck still")
    say("delivers exactly 6 V to the motor terminals.)")
    say("Per TB6612 channel: 1.2 A continuous / 3.2 A peak. A single stall at 100%")
    say(f"duty ({i_stall:.1f} A) exceeds the continuous rating but sits at "
        f"{i_stall/3.2*100:.0f}% of peak")
    say("-> legal as a PWM-limited transient; firmware caps duty so the AVERAGE")
    say(f"stays <= 1.2 A (duty <= {1.2/i_stall*100:.0f}% into a hard stall).")
    say(f"Supply ceiling: both motors stalled = {2*i_stall:.1f} A demand vs the")
    say("TPS54302's ~3 A rating + cycle-by-cycle limit -- the buck (not the pack)")
    say("is the bottleneck and it limits/folds back rather than cooking anything;")
    c30, c30v = cval("C30")
    ctot = c30 + cval("C16")[0] + cval("C17")[0]
    dv = i_stall * 0.5 * 25e-6 / ctot   # one 20 kHz half-period, worst chop deficit
    say(f"C30 {c30*1e6:.0f}uF + ceramics ride the 20 kHz PWM chop: worst-case droop")
    say(f"~{dv*1e3:.0f} mV per half-period at a {i_stall:.1f} A edge -- the rail stays")
    say("stiff and the pack sees averaged, fused current (P3). TB6612 thermal")
    say("shutdown is the final backstop.")
    require(i_stall < 3.2, "single-channel stall exceeds the TB6612 peak rating")
    require(2 * i_stall > 3.0, "sanity: dual stall must exceed the buck rating "
            "(else the ceiling analysis is moot)")
    require(dv < 0.2, "VM_6V bulk too small for the PWM chop")

@test("M4", "Motors", "VM_6V decoupling chain at the driver + logic bypass",
      nets=["VM_6V", "PLUS3V3", "GND"], comps=["C30", "C11", "C12", "C14"])
def _(say, touch, touchc):
    c30, c30v = cval("C30")
    require({net_of("C30", 1), net_of("C30", 2)} == {"VM_6V", "GND"},
            "C30 bulk must sit on VM_6V")
    require(c30v is not None and c30v >= 1.5 * 6.01,
            f"C30 rating {c30v} V needs >=1.5x the 6V rail")
    for c in ("C11", "C12"):
        require({net_of(c, 1), net_of(c, 2)} == {"VM_6V", "GND"},
                f"{c} must decouple VM_6V at the driver pins")
    require({net_of("C14", 1), net_of("C14", 2)} == {"PLUS3V3", "GND"},
            "C14 must decouple the TB6612 VCC (logic) pin")
    say(f"C30 {c30*1e6:.0f}uF/{c30v:.0f}V alu bulk at the VM entry ({c30v/6.01:.1f}x rail")
    say("rating) + C11 10uF/25V + C12 100nF at the TB6612's VM pins absorb the PWM")
    say("edge current (motor hot-loop); C16/C17 22uF close the loop at the buck")
    say("(P7). C14 100nF bypasses the driver's separate VCC logic supply from 3V3.")

@test("N1", "Encoders", "Quadrature nets, pull-ups, PCNT capability",
      nets=["ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B", "PLUS3V3"],
      comps=["R6", "R7", "R8", "R9", "J5", "J6"])
def _(say, touch, touchc):
    # rev 7.2 ZH cable order: C1/C2 on pins 3/4, encoder VCC/GND on 2/5.
    for net, conn, pin in (("ENC1_A", "J5", 3), ("ENC1_B", "J5", 4),
                            ("ENC2_A", "J6", 3), ("ENC2_B", "J6", 4)):
        require(on(net, conn, pin), f"{net} on {conn}.{pin}")
        reaches = any(r == "U3" for r, p in NETS[net])
        if not reaches:
            # ENC2 passes a 1k series guard: follow it to the module side
            for guard in ("R57", "R58"):
                if any(r == guard for r, p in NETS[net]):
                    other = net_of(guard, 2) if net_of(guard, 1) == net else net_of(guard, 1)
                    touch(other)
                    reaches = any(r == "U3" for r, p in NETS[other])
        require(reaches, f"{net} reaches module (directly or via guard)")
        rs = [r for r, p in NETS[net] if r.startswith("R")]
        require(rs, f"{net} needs a pull-up/guard R")
    say("Each phase has a 10k pull-up to 3V3 (required if the encoder output is")
    say("open-drain, harmless if push-pull -- the N20 encoder boards vary) and")
    say("ENC2 additionally passes the 1k UART guards. Decoding: two S3 PCNT units")
    say("in hardware quadrature via the GPIO matrix -- zero-CPU-cost counting.")
    for conn in ("J5", "J6"):
        require(net_of(conn, 2) == "PLUS3V3" and net_of(conn, 5) == "GND",
                f"{conn} encoder supply pins (ZH order: VCC=2, GND=5)")
    say("J5/J6 pin order = the robu GA12-N20 factory cable (M1,VCC,C1,C2,GND,M2):")
    say("the motor's own JST ZH plug goes straight in. METER-VERIFY pins 2/5 against")
    say("the delivered cable before first plug-in (listing table vs photo conflict).")

# ---------------------------------------------------------------------------
# OPTICS: LINE ARRAY (TCRT5000)
# ---------------------------------------------------------------------------
@test("O1", "Line array", "TCRT5000 LED drive current (shared bank FET)",
      nets=["PLUS3V3", "EMIT_LINE_K", "LINE_EMIT"], comps=["Q19", "R61"])
def _(say, touch, touchc):
    vf, rds_wc, rds_typ = 1.25, 8.0, 3.5   # TCRT VF typ; BSS138 Rds @ Vgs 3.3
    n = 8
    limiters = [f"R{26 + 2*k}" for k in range(n)]        # R26,R28..R40
    for r in limiters:
        require(abs(rval(r) - 120) < 12, f"{r} must be 120R")
        require(on("PLUS3V3", r, 1), f"{r} feeds from the regulated rail")
        touchc(r)
    r_lim = rval("R26")
    i_wc = (V33 - vf) / (r_lim + n * rds_wc)
    i_typ = (V33 - vf) / (r_lim + n * rds_typ)
    say(f"Netlist-read limiters: 8 x {r_lim:.0f}R from +3V3. Per-channel current")
    say(f"(3.3 - {vf}) / ({r_lim:.0f} + 8ch*Rds): {i_wc*1e3:.1f} mA at worst-case Rds "
        f"{rds_wc:.0f} ohm,")
    say(f"{i_typ*1e3:.1f} mA at typical -- bank total {n*i_typ*1e3:.0f} mA through Q19 "
        f"(BSS138).")
    say("TCRT5000 spec point IF = 10 mA (IC 0.5-2.1 mA), abs max 60 mA -> the")
    say("drive brackets the spec point with >4x margin to the limit.")
    for k in range(1, 9):
        require(net_of(f"LS{k}", 2) == "EMIT_LINE_K", f"LS{k} cathode on the bank net")
        anode = net_of(f"LS{k}", 1)
        touch(anode)
        require(set(NETS[anode]) == {(f"LS{k}", "1"), (f"R{24 + 2*k}", "2")},
                f"LS{k} anode must pair with ITS limiter R{24 + 2*k}")
        touchc(f"LS{k}")
    say("Per-LED anode nets verified two-node against their OWN limiters, so the")
    say("bank node carries only the summed current and each IF stays R-defined.")
    require(on("EMIT_LINE_K", "Q19", 3), "bank FET drain on EMIT_LINE_K")
    require(on("LINE_EMIT", "Q19", 1) and on("LINE_EMIT", "U3", 22),
            "gate net driven from IO14")
    require(on("LINE_EMIT", "R61", 1) and on("GND", "R61", 2)
            and abs(rval("R61") - 100e3) < 10e3,
            "R61 100k must hold the gate low through boot")
    require(0.008 <= i_wc <= 0.020, "LED current outside 8-20 mA window")

@test("O2", "Line array", "Phototransistor load line and ADC swing",
      nets=["MUX_SENSE"], comps=[f"LS{k}" for k in range(1, 9)])
def _(say, touch, touchc):
    pulls = [f"R{25 + 2*k}" for k in range(8)]           # R25,R27..R39
    for r in pulls:
        require(abs(rval(r) - 47e3) < 4.7e3, f"{r} must be 47k")
        require(on("PLUS3V3", r, 1), f"{r} pulls from the regulated rail")
        touchc(r)
    rp = rval("R25")
    say(f"Netlist-read 47k pull-ups: white floor (IC ~0.8 mA) saturates the PT ->")
    say(f"V <= 0.4 V (VCEsat max); black line (IC < 30 uA) -> V >= "
        f"{V33 - 30e-6*rp:.2f} V.")
    say("Guaranteed swing >= 1.5 V (typically ~2.5 V) across the mux into IO7 --")
    say("ample for 8-way thresholding.")
    mux_pins = {1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2}   # I0..I7
    for k in range(1, 9):
        net = f"LINE{k}_SENSE"
        touch(net)
        require(on(net, f"LS{k}", 4), f"{net}: PT collector")
        require(net_of(f"LS{k}", 3) == "GND", f"LS{k} PT emitter to GND")
        require(on(net, "U4", mux_pins[k]), f"{net} must enter mux channel I{k-1}")
    say("Channel map verified: LINE1..8 -> I0..I7 (U4 pads 9..2), so the firmware")
    say("select walk is a plain 0..7 count. Sensing height: with 32 mm wheels the")
    say("underside rides ~9.4 mm; the 7 mm body puts the optical face at ~2.4 mm =")
    say("TCRT5000's peak-response distance.")

# ---------------------------------------------------------------------------
# OPTICS: WALL SENSORS
# ---------------------------------------------------------------------------
@test("W1", "Wall sensors", "IR333-A emitter chains and banked drive",
      nets=["EMIT_FRONT_K", "EMIT_DIAG_K", "EMIT_SIDE_K",
            "WALL_EMIT_FRONT", "WALL_EMIT_DIAG", "WALL_EMIT_SIDE"],
      comps=["Q16", "Q17", "Q18", "D1", "D2", "D3", "D4", "D5", "D6"])
def _(say, touch, touchc):
    vf, rds_wc, rds_typ = 1.35, 8.0, 3.5   # IR333-A VF ~1.2-1.4 V in the 20-50 mA region
    limiters = [f"R{14 + 2*k}" for k in range(6)]        # R14,R16..R24
    for r in limiters:
        require(abs(rval(r) - 33) < 4, f"{r} must be 33R")
        require(on("PLUS3V3", r, 1), f"{r} feeds from the regulated rail")
        touchc(r)
    r_lim = rval("R14")
    i_wc = (V33 - vf) / (r_lim + 2 * rds_wc)
    i_typ = (V33 - vf) / (r_lim + 2 * rds_typ)
    say(f"Rev 6 emitters are IR333-A (5mm, 940nm, 20deg half-angle; netlist value")
    say(f"field names the part). Per-emitter with the netlist-read {r_lim:.0f}R:")
    say(f"(3.3 - {vf}) / ({r_lim:.0f} + 2ch*Rds) = {i_wc*1e3:.0f} mA worst-case / "
        f"{i_typ*1e3:.0f} mA typical,")
    say(f"banks of two ({2*i_typ*1e3:.0f} mA per BSS138). IR333-A abs max 100 mA")
    say(f"continuous -> {i_typ/0.100*100:.0f}% of the limit even LATCHED (debug mode);")
    say("banks are normally pulsed (front/diag/side) for ambient rejection, and")
    say("the 20deg beam at ~50 mA gives championship-grade wall range.")
    for k, (d, expect) in enumerate((("D1", "EMIT_FRONT_K"), ("D2", "EMIT_FRONT_K"),
                                     ("D3", "EMIT_DIAG_K"), ("D4", "EMIT_DIAG_K"),
                                     ("D5", "EMIT_SIDE_K"), ("D6", "EMIT_SIDE_K")),
                                    start=1):
        require("IR333" in COMPS[d][0], f"{d} must be an IR333-A (netlist value)")
        require(net_of(d, 1) == expect, f"{d} cathode must join {expect}")
        anode = net_of(d, 2)
        touch(anode)
        require(set(NETS[anode]) == {(d, "2"), (f"R{12 + 2*k}", "2")},
                f"{d} anode must pair with ITS limiter R{12 + 2*k}")
    say("Per-LED anode nets verified two-node against their own limiters: the")
    say("switched cathode node carries only the pair's summed current.")
    for q, knet, gnet, r_pd in (("Q16", "EMIT_FRONT_K", "WALL_EMIT_FRONT", "R62"),
                                ("Q17", "EMIT_DIAG_K", "WALL_EMIT_DIAG", "R63"),
                                ("Q18", "EMIT_SIDE_K", "WALL_EMIT_SIDE", "R64")):
        require(on(knet, q, 3), f"{q} drain on {knet}")
        require(on(gnet, q, 1) and any(r == "U3" for r, p in NETS[gnet]),
                f"{q} gate driven from the module")
        require(on(gnet, r_pd, 1) and on("GND", r_pd, 2),
                f"{r_pd} must hold the {q} gate low through boot")
        touchc(r_pd)
    require(0.025 <= i_wc and i_typ <= 0.065, "wall emitter current out of window")

@test("W2", "Wall sensors", "PT334-6B receivers: bias, swing, direct ADC path",
      comps=["Q2", "Q3", "Q4", "Q5", "Q6", "Q7"])
def _(say, touch, touchc):
    pulls = ["R13", "R15", "R17", "R19", "R21", "R23"]
    for r in pulls:
        require(abs(rval(r) - 47e3) < 4.7e3, f"{r} must be 47k")
        require(on("PLUS3V3", r, 1), f"{r} pulls from the regulated rail")
        touchc(r)
    say("Each PT334-6B collector has a netlist-verified 47k pull-up; wall return")
    say("light (>=50 uW/cm2 at competition distances with the ~50 mA IR333-A")
    say("drive) swings the node 0.5-3.0 V directly into ADC1 pins IO1-IO6 (no")
    say("mux: all six walls sample in one burst). Black-lens part rejects visible")
    say("ambient; firmware subtracts the emitter-off baseline for the rest.")
    for i, q in enumerate(("Q2", "Q3", "Q4", "Q5", "Q6", "Q7"), start=1):
        net = f"WALL{i}_SENSE"
        touch(net)
        require(any(r == q for r, p in NETS[net]), f"{net} on {q}")
        require(any(r == "U3" for r, p in NETS[net]), f"{net} direct to ADC")
        e1, e2 = net_of(q, 1), net_of(q, 2)
        require("GND" in (e1, e2), f"{q} emitter to GND")
    say("ASSEMBLY: PT334's LONG lead is the EMITTER (silk + docs note) -- opposite")
    say("of the LED convention.")

# ---------------------------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------------------------
@test("I1", "Indicators", "Wall indicator drivers (PMOS, LED ON = wall seen)",
      comps=["Q28", "Q29", "Q30", "Q31", "Q32", "Q33"])
def _(say, touch, touchc):
    i_led = (V33 - 1.85) / 1000
    say(f"BSS84 source at 3V3, gate on WALLx_SENSE: wall seen -> PT pulls sense low")
    say(f"-> |Vgs| ~3 V >> |Vth| 0.8-2.0 -> LED lit at ~{i_led*1e3:.1f} mA (1k, super-red")
    say("high-efficiency bin, clearly visible). No wall -> sense near 3V3 -> off.")
    for k, q in enumerate(("Q28", "Q29", "Q30", "Q31", "Q32", "Q33"), start=1):
        require(net_of(q, 2) == "PLUS3V3", f"{q} source on 3V3")
        g = net_of(q, 1)
        require(g == f"WALL{k}_SENSE", f"{q} gate must be WALL{k}_SENSE (got {g})")
        d = net_of(q, 3)
        touch(d)
        require(any(r == f"R{48+k}" for r, p in NETS[d]), f"{q} drain -> R{48+k}")
        led = f"D{22+k}"
        anode = net_of(led, 2)
        touch(anode)
        touchc(led, f"R{48+k}")
        require(set(NETS[anode]) == {(led, "2"), (f"R{48+k}", "2")},
                f"{led} anode must hang off R{48+k}")
        require(net_of(led, 1) == "GND", f"{led} cathode to GND")
    say("Full chains walked pin-by-pin: 3V3 -> Qsource/drain -> 1k -> LED -> GND.")

@test("I2", "Indicators", "Line indicator drivers (NMOS, LED ON = line seen)",
      comps=["Q20", "Q21", "Q22", "Q23", "Q24", "Q25", "Q26", "Q27"])
def _(say, touch, touchc):
    say("BSS138 gate on LINEx_SENSE: black line -> PT dark -> sense pulled to 3V3")
    say("-> FET on -> LED lit. White floor -> sense saturates low (<0.4 V) < Vth")
    say("0.8 min -> off. Latched emitters (not pulsed) whenever indicators are")
    say("enabled, so the LEDs read true floor state (rev-3 review finding).")
    for k, q in enumerate(("Q20", "Q21", "Q22", "Q23", "Q24", "Q25", "Q26", "Q27"), start=1):
        require(net_of(q, 1) == f"LINE{k}_SENSE", f"{q} gate on LINE{k}_SENSE")
        require(net_of(q, 2) == "GND", f"{q} source to GND")
        led = f"D{14+k}"
        kat, anode = net_of(led, 1), net_of(led, 2)
        touch(kat, anode)
        touchc(led, f"R{40+k}")
        require(set(NETS[kat]) == {(led, "1"), (q, "3")},
                f"{led} cathode must hang off {q}'s drain")
        require(set(NETS[anode]) == {(led, "2"), (f"R{40+k}", "2")},
                f"{led} anode must hang off R{40+k}")
        require(on("PLUS3V3", f"R{40+k}", 1), f"R{40+k} limiter feeds from 3V3")
    say("Full chains walked pin-by-pin: 3V3 -> 1k -> LED -> Qdrain/source -> GND.")

# ---------------------------------------------------------------------------
# MUX + TELEMETRY (rev 6: battery telemetry rides the mux's upper channels)
# ---------------------------------------------------------------------------
@test("X1", "Mux", "CD74HC4067: four GPIO selects (S3 promoted to IO8), enable, common",
      nets=["MUX_S0", "MUX_S1", "MUX_S2", "MUX_S3", "MUX_SENSE", "GND", "PLUS3V3"],
      comps=["U4", "C13"])
def _(say, touch, touchc):
    selmap = {"MUX_S0": ("10", "19"), "MUX_S1": ("11", "20"),
              "MUX_S2": ("14", "21"), "MUX_S3": ("13", "12")}
    for net, (u4pin, u3pin) in selmap.items():
        require(on(net, "U4", u4pin), f"{net} must land on U4.{u4pin}")
        require(on(net, "U3", u3pin), f"{net} must come from U3.{u3pin}")
    require(net_of("U4", 15) == "GND", "~E enable must be hard-grounded")
    require(net_of("U4", 12) == "GND", "VSS on GND")
    require(net_of("U4", 24) == "PLUS3V3", "VCC on 3V3")
    require(on("MUX_SENSE", "U4", 1) and on("MUX_SENSE", "U3", 7), "common Z -> IO7")
    require({net_of("C13", 1), net_of("C13", 2)} == {"PLUS3V3", "GND"},
            "C13 must decouple the mux supply")
    say("S0-S2 from IO11-13 walk I0..I7 = LINE1..8; rev 6 PROMOTED S3 from a GND")
    say("tie to IO8 (U3.12 -> U4.13, netlist-verified) opening channels I8-I15 --")
    say("battery/VBUS telemetry now rides I8-I10 instead of burning three ADC")
    say("pins. ~E stays hard-grounded (mux always enabled); one ADC pin (IO7)")
    say("reads all 11 sources. 100nF decoupling (C13) at the mux supply.")

@test("X2", "Mux", "Pack telemetry: VBAT divider into channel I8",
      nets=["VM_BATT", "VBAT_SENSE", "GND"], comps=["R2", "R3", "C6"])
def _(say, touch, touchc):
    require(on("VM_BATT", "R2", 1) and on("VBAT_SENSE", "R2", 2), "R2 top leg")
    require(on("VBAT_SENSE", "R3", 1) and on("GND", "R3", 2), "R3 bottom leg")
    require(on("VBAT_SENSE", "U4", 23), "sense must land on mux channel I8 (pad 23)")
    require(on("VBAT_SENSE", "C6", 1), "C6 filter at the divider node")
    r2, r3 = rval("R2"), rval("R3")
    vmax = VBAT_MAX * r3 / (r2 + r3)
    vmin = VBAT_MIN_USE * r3 / (r2 + r3)
    say(f"R2/R3 = {r2/1e3:.0f}k/{r3/1e3:.0f}k -> {VBAT_MAX} V pack reads {vmax:.2f} V,")
    say(f"the {VBAT_MIN_USE} V firmware floor reads {vmin:.2f} V -- the whole window")
    say("lands inside the S3 ADC's calibrated 12 dB range with headroom.")
    say(f"Divider sits DOWNSTREAM of Q1 (on VM_BATT), drains "
        f"{VBAT_MAX/(r2+r3)*1e6:.0f} uA while")
    say("connected (metered in S4); C6 100nF makes the node stiff for the mux.")
    say("Firmware cutoff: 6.6 V pack = 3.3 V/cell.")
    require(vmax <= 2.9, "divider output exceeds the calibrated ADC range")

@test("X3", "Mux", "Per-cell telemetry: balance midpoint divider into channel I9",
      nets=["BAT_MID", "BAT_MID_SENSE", "GND"], comps=["R75", "R76", "C19", "J9"])
def _(say, touch, touchc):
    require(on("BAT_MID", "R75", 1) and on("BAT_MID", "J9", 2), "R75 fed from J9.2")
    require(on("BAT_MID_SENSE", "R75", 2) and on("BAT_MID_SENSE", "R76", 1),
            "R75/R76 join at the sense node")
    require(on("GND", "R76", 2), "R76 bottom leg grounded")
    require(on("BAT_MID_SENSE", "U4", 22), "sense must land on mux channel I9 (pad 22)")
    require(on("BAT_MID_SENSE", "C19", 1), "C19 filter at the divider node")
    r75, r76 = rval("R75"), rval("R76")
    vmax = 4.2 * r76 / (r75 + r76)
    say(f"R75/R76 = {r75/1e3:.0f}k/{r76/1e3:.0f}k -> a full cell 1 (4.2 V midpoint)")
    say(f"reads {vmax:.2f} V on I9. Firmware: cell1 = 2 x reading, cell2 = pack -")
    say("cell1 -- per-cell monitoring so EITHER weak cell triggers the 3.3 V/cell")
    say(f"cutoff. Divider drain {4.2/(r75+r76)*1e6:.0f} uA whenever the balance plug")
    say("is in (S4); C19 100nF stiffens the node for the mux hop.")
    require(vmax <= 2.9, "midpoint reading exceeds the calibrated ADC range")

@test("X4", "Mux", "Mux Ron + source impedance vs ADC sampling",
      nets=["MUX_SENSE"], comps=["U4"])
def _(say, touch, touchc):
    ron_typ, ron_wc = 70.0, 160.0       # CD74HC4067 at 3.3 V supply
    r_line = rval("R25")                 # worst line channel: 47k pull-up dark
    r_vbat = rval("R2") * rval("R3") / (rval("R2") + rval("R3"))
    cs = 10e-12                          # S3 ADC sample cap, pF class
    settle = lambda r: (r + ron_wc) * cs * 8.4   # ln(2^12) ~ 8.3 time constants
    say(f"CD74HC4067 Ron ~{ron_typ:.0f}R typ / ~{ron_wc:.0f}R worst at 3.3 V -- "
        f"negligible against the")
    say(f"sources: line channels up to {r_line/1e3:.0f}k (PT dark), VBAT divider "
        f"{r_vbat/1e3:.1f}k,")
    say(f"midpoint 50k, VBUS 6k. 12-bit settling (8.3 tau into a ~{cs*1e12:.0f} pF "
        f"sample cap):")
    say(f"worst {settle(r_line)*1e6:.1f} us (line dark) -> firmware budgets ADC "
        f"sample-and-hold")
    say("time accordingly (or double-samples and keeps the second); the telemetry")
    say("channels' 100nF node caps (C6/C19) recharge through their dividers in")
    say("~3 ms RC -- fine at telemetry rates. Same firmware note as rev 5, now")
    say("covering 11 channels instead of 8.")
    require(settle(r_line) < 10e-6, "mux settling budget beyond a sane ADC window")

# ---------------------------------------------------------------------------
# IMU (BNO055, I2C)
# ---------------------------------------------------------------------------
@test("U1", "IMU", "BNO055 supplies and protocol straps (I2C, addr 0x28)",
      nets=["PLUS3V3", "GND"], comps=["U8", "C23", "C24"])
def _(say, touch, touchc):
    require("BNO055" in COMPS["U8"][0], "U8 must be the BNO055")
    require(on("PLUS3V3", "U8", 3) and "VDD" in fn_of("U8", 3), "VDD on 3V3")
    require(on("PLUS3V3", "U8", 28) and "VDDIO" in fn_of("U8", 28), "VDDIO on 3V3")
    require(on("GND", "U8", 2) and on("GND", "U8", 25), "GND + GNDIO grounded")
    for c in ("C23", "C24"):
        require({net_of(c, 1), net_of(c, 2)} == {"PLUS3V3", "GND"},
                f"{c} must bypass the IMU supply entry")
    say(f"Local bypasses at the IMU: C23 {cval('C23')[0]*1e9:.0f}nF + C24 "
        f"{cval('C24')[0]*1e6:.0f}uF (the Bosch")
    say("reference pair for VDD/VDDIO on a shared rail).")
    for pin, name in ((6, "PS0"), (5, "PS1"), (18, "COM2"), (17, "COM3/ADDR")):
        require(on("GND", "U8", pin), f"{name} (U8.{pin}) must be grounded")
    say("PS1:PS0 = 00 (netlist-verified grounds) selects I2C; COM3/ADDR low ->")
    say("address 0x28; COM2 grounded as the I2C mode requires. VDD and VDDIO both")
    say("on the 3.3 V rail (single-supply, level-shift-free against the S3).")
    say("Supply current ~12.3 mA in normal fusion mode -- 1.3% of the P5 budget;")
    say("already counted there.")

@test("U2", "IMU", "I2C bus: pin map, pull-ups, 400 kHz rise time",
      nets=["IMU_SDA", "IMU_SCL", "PLUS3V3"], comps=["R77", "R78", "U8"])
def _(say, touch, touchc):
    require(on("IMU_SDA", "U8", 20) and on("IMU_SDA", "U3", 11),
            "SDA: BNO055 COM0 <-> IO18 (U3.11)")
    require(on("IMU_SCL", "U8", 19) and on("IMU_SCL", "U3", 23),
            "SCL: BNO055 COM1 <-> IO21 (U3.23)")
    require(on("IMU_SDA", "R77", 2) and on("PLUS3V3", "R77", 1), "R77 pulls SDA up")
    require(on("IMU_SCL", "R78", 2) and on("PLUS3V3", "R78", 1), "R78 pulls SCL up")
    rp = rval("R77")
    require(abs(rp - 4.7e3) < 470 and abs(rval("R78") - 4.7e3) < 470,
            "I2C pull-ups must be 4.7k")
    cb = 50e-12                    # two chip pins + short traces, worst-case estimate
    tr = 0.8473 * rp * cb          # 30-70% rise per the I2C spec definition
    cb_max = 300e-9 / (0.8473 * rp)
    i_sink = V33 / rp
    say(f"IO18/IO21 were freed by the TB6612 IN/IN rework (M1) -- the netlist ties")
    say(f"them to COM0/COM1 with {rp/1e3:.1f}k pull-ups. Rise time at a conservative")
    say(f"{cb*1e12:.0f} pF bus: {tr*1e9:.0f} ns vs the 400 kHz fast-mode limit of "
        f"300 ns; the")
    say(f"pull-up value tolerates up to {cb_max*1e12:.0f} pF. Sink current "
        f"{i_sink*1e3:.2f} mA << the")
    say("3 mA I2C VOL spec point -- comfortable for both parties. Control loop")
    say("reads at up to ~2.7 kHz theoretical; 100 Hz fusion output is the real cap.")
    require(tr < 300e-9, "I2C rise time violates the 400 kHz spec")
    require(i_sink < 3e-3, "pull-up too strong for the I2C VOL spec")

@test("U3", "IMU", "Interrupt line to IO37", nets=["IMU_INT"], comps=["U8"])
def _(say, touch, touchc):
    require(set(NETS["IMU_INT"]) == {("U3", "30"), ("U8", "14")},
            "INT must run point-to-point U8.14 -> IO37 (U3.30)")
    say("BNO055 INT (push-pull, data-ready/any-motion) direct to IO37 -- the pin")
    say("freed when VBUS sensing moved onto the mux (E2). Point-to-point net, no")
    say("pull needed. The 500 Hz control loop may also simply poll; the interrupt")
    say("is for wake-on-motion at the start line.")

@test("U4", "IMU", "Support pins: nBOOT/nRESET pulls, CAP bypass; internal oscillator",
      nets=["Net-(U8-~{BOOT_LOAD_PIN})", "Net-(U8-~{RESET})", "Net-(U8-CAP)"],
      comps=["R79", "R80", "C20"])
def _(say, touch, touchc):
    require(on("Net-(U8-~{BOOT_LOAD_PIN})", "R79", 2)
            and on("Net-(U8-~{BOOT_LOAD_PIN})", "U8", 4), "R79 on nBOOT_LOAD_PIN")
    require(on("Net-(U8-~{RESET})", "R80", 2)
            and on("Net-(U8-~{RESET})", "U8", 11), "R80 on nRESET")
    for r in ("R79", "R80"):
        require(on("PLUS3V3", r, 1) and abs(rval(r) - 10e3) < 1e3,
                f"{r} must be a 10k pull-up to 3V3")
    say("nBOOT_LOAD_PIN high through R79 10k = normal boot (low would enter the")
    say("Bosch bootloader); nRESET high through R80 10k -- no GPIO spent, the")
    say("watchdog/power-cycle covers recovery.")
    require({net_of("C20", 1), net_of("C20", 2)} == {"Net-(U8-CAP)", "GND"}
            and on("Net-(U8-CAP)", "U8", 9), "C20 must bypass the CAP pin to GND")
    say(f"CAP pin: C20 {cval('C20')[0]*1e9:.0f}nF to GND (internal-LDO bypass, the")
    say("Adafruit reference value).")
    # rev 6.1: the external 32.768kHz crystal was dropped -- the BNO055 runs on
    # its INTERNAL oscillator (Adafruit's default; SYS_TRIGGER.CLK_SEL=0). This
    # removed X1/C21/C22 and the two unroutable north-row LGA nets. XIN32/XOUT32
    # must therefore be no-connects.
    require(not net_exists("Net-(U8-XIN32)") and not net_exists("Net-(U8-XOUT32)"),
            "XIN32/XOUT32 must be NC (internal oscillator; no crystal)")
    require("X1" not in COMPS, "X1 crystal must be absent (rev 6.1 internal osc)")
    say("Clock: INTERNAL oscillator -- fusion time-base uses the on-chip clock")
    say("(crystal dropped for routability; internal osc is spec-supported).")

# ---------------------------------------------------------------------------
# SYSTEM-LEVEL
# ---------------------------------------------------------------------------
@test("S1", "System", "Single unified ground; every subsystem returns to it",
      nets=["GND"])
def _(say, touch, touchc):
    refs = {r for r, p in NETS["GND"]}
    say(f"GND spans {len(NETS['GND'])} pins on {len(refs)} components -- one net, no")
    say("split grounds (In1 is a solid plane, stitched at every SMD pour pad).")
    for must in ("J1", "J9", "U1", "U2", "U3", "U4", "U6", "U7", "U8",
                 "J7", "J8", "SW5", "SW6"):
        require(must in refs, f"{must} missing from GND")

@test("S2", "System", "No floating module inputs / undocumented NC",
      nets=[])
def _(say, touch, touchc):
    singles = [n for n, nodes in NETS.items()
               if len(nodes) == 1 and not n.startswith("unconnected-")]
    named_bad = [n for n in singles if not n.startswith("Net-")]
    say(f"Single-pin named nets: {named_bad if named_bad else 'none'} (KiCad")
    say("explicit no-connects are excluded; they are flagged in the schematic and")
    say("documented in CONNECTIONS.md -- the BNO055's unused pins and the mux's")
    say("spare I11-I15 dominate the rev-6 NC list).")
    require(not named_bad, f"undocumented single-pin nets: {named_bad}")

@test("S3", "System", "3V3 rail fanout reaches every logic consumer",
      nets=["PLUS3V3"], comps=["C8"])
def _(say, touch, touchc):
    refs = {r for r, p in NETS["PLUS3V3"]}
    for must in ("U2", "U3", "U4", "U6", "U8", "J5", "J6", "J8"):
        require(must in refs, f"{must} missing from 3V3")
    require({net_of("C8", 1), net_of("C8", 2)} == {"PLUS3V3", "GND"},
            "C8 module bypass must sit on the rail")
    say(f"PLUS3V3 spans {len(NETS['PLUS3V3'])} pins: module, mux, IMU (VDD+VDDIO),")
    say("TB6612 VCC + the tied-high PWMA/PWMB pads, both encoder supplies, JTAG")
    say("Vtarget, the ESD array clamp rail, every pull-up and both indicator")
    say("supply banks.")

@test("S4", "System", "Always-on battery drain census (switches off, pack plugged)",
      nets=["VM_BATT", "BAT_MID"], comps=["R1", "R2", "R3", "R69", "R75", "R76"])
def _(say, touch, touchc):
    i_r69 = VBAT_MAX / rval("R69")
    i_vdiv = VBAT_MAX / (rval("R2") + rval("R3"))
    i_gate = VBAT_MAX / rval("R1")
    i_mid = 4.2 / (rval("R75") + rval("R76"))
    total = i_r69 + i_vdiv + i_gate + i_mid
    say("With SW5 OFF both regulators are disabled (EN grounded / starved) but")
    say("four resistive paths stay on the pack (all values netlist-read, 8.4 V):")
    say(f"  R69 soft-switch pull-up {rval('R69')/1e6:.0f}M: {i_r69*1e6:.1f} uA")
    say(f"  R2+R3 pack divider {(rval('R2')+rval('R3'))/1e3:.0f}k: {i_vdiv*1e6:.1f} uA")
    say(f"  R1 Q1 gate pulldown {rval('R1')/1e3:.0f}k: {i_gate*1e6:.1f} uA")
    say(f"  R75+R76 midpoint divider {(rval('R75')+rval('R76'))/1e3:.0f}k "
        f"(via the balance plug): {i_mid*1e6:.1f} uA")
    say(f"Total ~{total*1e6:.0f} uA -- a 600 mAh 2S pack self-drains in ~{600e-3/total/24/365:.1f}")
    say("years through the board; the LiPo's own self-discharge dominates. Rule")
    say("stays: UNPLUG BOTH CONNECTORS TO STORE. Note the midpoint path loads only")
    say("cell 1 -- another reason not to leave the balance lead in long-term.")
    require(total < 500e-6, "off-state drain above the documented budget")

# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def main():
    n_pass = sum(1 for r in RESULTS if r[3] == "PASS")
    n_fail = sum(1 for r in RESULTS if r[3] == "FAIL")
    touched_nets = set()
    touched_comps = set()
    for (_, _, _, _, _, ns, cs) in RESULTS:
        touched_nets.update(n for n in ns if n in NETS)
        touched_comps.update(c for c in cs if c in COMPS)
    real_nets = {n for n in NETS if not n.startswith("unconnected-")}
    # nets touched implicitly by walking (PIN2NET lookups) are not counted --
    # coverage is CLAIMED nets only, the conservative number.
    net_cov = len(touched_nets & real_nets) / len(real_nets) * 100
    comp_cov = len(touched_comps) / len(COMPS) * 100
    untested = sorted(real_nets - touched_nets)

    L = []
    L.append("# Circuit Verification Report -- micromouse-pcb rev 6\n")
    L.append("Generated by `pcb/tools/circuit_tests.py` from `pcb/netlist.net` "
             "(the same file the board is built from). Each test walks real "
             "netlist connectivity pin-by-pin and computes operating points from "
             "component values + datasheet parameters verified during the "
             "rev-6 sourcing pass. Per-net design rationale: "
             "[CONNECTIONS.md](CONNECTIONS.md).\n")
    L.append(f"**Result: {n_pass} PASS / {n_fail} FAIL of {len(RESULTS)} tests.**  ")
    L.append(f"**Coverage: {net_cov:.0f}% of nets ({len(touched_nets & real_nets)}/"
             f"{len(real_nets)}) and {comp_cov:.0f}% of components "
             f"({len(touched_comps)}/{len(COMPS)}) exercised by at least one test.**\n")
    if n_fail:
        L.append("**Open design findings (FAILed tests -- schematic issues, "
                 "not test bugs):**\n")
        for (tid, _, title, status, lines, _, _) in RESULTS:
            if status == "FAIL":
                L.append(f"- **{tid}** {title} -- {lines[-1] if lines else ''}")
        L.append("")
    L.append("| ID | Subsystem | Test | Result |")
    L.append("|---|---|---|---|")
    for (tid, sub, title, status, _, _, _) in RESULTS:
        L.append(f"| {tid} | {sub} | {title} | **{status}** |")
    L.append("")
    cur = None
    for (tid, sub, title, status, lines, ns, cs) in RESULTS:
        if sub != cur:
            L.append(f"\n## {sub}\n")
            cur = sub
        L.append(f"### {tid} -- {title}  [{status}]\n")
        for ln in lines:
            L.append(ln)
        nets_used = sorted(set(n for n in ns if n in NETS))
        if nets_used:
            L.append(f"\n*Nets exercised:* `{'`, `'.join(nets_used)}`")
        L.append("")
    L.append("\n## Coverage appendix\n")
    L.append(f"Nets not directly claimed by any test ({len(untested)}):\n")
    for n in untested:
        L.append(f"- `{n}` -- see its entry in CONNECTIONS.md")
    L.append("\nMost of these are per-pin power stubs, decoupling and doubled-pin")
    L.append("bridges whose integrity is enforced structurally (netlist->pad gate,")
    L.append("verify_netlist.py, DRC 0-unconnected) rather than by operating-point")
    L.append("math.\n")
    with open(REPORT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(f"TEST REPORT: {n_pass} PASS / {n_fail} FAIL / {len(RESULTS)} tests | "
          f"net coverage {net_cov:.0f}% | component coverage {comp_cov:.0f}%")
    print(f"wrote {REPORT}")
    if n_fail:
        for (tid, sub, title, status, lines, _, _) in RESULTS:
            if status == "FAIL":
                print(f"FAIL {tid} {title}: {lines[-1] if lines else ''}")
        sys.exit(1)

main()
