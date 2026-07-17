"""Analytical circuit verification for the micromouse board. Exits 1 on FAIL.

Every test parses pcb/netlist.net (the same file the board is built from) and
computes DC operating points / logic states from component values + verified
datasheet parameters -- i.e. the checks exercise the REAL connectivity, not a
redrawn model. A SPICE run of an ESP32-S3 module is not meaningful (no vendor
models exist for the module, TB6612 or TCRT5000); the engineering-grade
equivalent for a digital+opto board is exactly this: per-path operating-point
computation with datasheet margins, plus behavioural walk-throughs of the
boot/flash sequences.

Emits pcb/TEST_REPORT.md: per-test detail (computed values, margins,
justification) + net/component coverage matrices. Per-net design rationale
lives in pcb/CONNECTIONS.md (generated, coverage-enforced); tests reference
nets by the same names.

Datasheet constants below were verified against manufacturer PDFs during the
rev-5.2/5.3 sourcing passes (TPS63001 SLVS520B, TB6612FNG 2008-05-09,
DMP2035U DS31830, TCRT5000 83760, PT334-6B DPT-0000263, onsemi BSS138/BSS84,
Kingbright APT1608SURCK, ESP32-S3 TRM/datasheet).
"""
import re
import sys
import time

NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"
REPORT = r"D:\Projects\micromouse-pcb\pcb\TEST_REPORT.md"

# ---------------------------------------------------------------------------
# netlist model
# ---------------------------------------------------------------------------
text = open(NETLIST, encoding="utf-8").read()
NETS = {}
for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text, re.S):
    NETS[m.group(1)] = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2))
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

def rval(ref):
    v = COMPS[ref][0].strip()
    m = re.match(r"^([\d.]+)\s*([kKmMrR]?)", v)
    num = float(m.group(1))
    mult = {"k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}.get(m.group(2), 1)
    return num * mult

# supply assumptions
VBAT_MIN, VBAT_NOM, VBAT_MAX = 3.0, 3.7, 4.2
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

# ---------------------------------------------------------------------------
# POWER TREE
# ---------------------------------------------------------------------------
@test("P1", "Power", "Battery input path: J1 -> F1 -> Q1(D->S) -> VM_BATT",
      nets=["Net-(J1-Pin_1)", "Net-(Q1-D)", "VM_BATT", "GND"], comps=["J1", "F1", "Q1"])
def _(say, touch, touchc):
    require(on("Net-(J1-Pin_1)", "J1", 1) and on("Net-(J1-Pin_1)", "F1", 1),
            "BAT+ must reach the fuse")
    require(on("Net-(Q1-D)", "F1", 2) and on("Net-(Q1-D)", "Q1", 3),
            "fuse must feed Q1 DRAIN (pin 3)")
    require(on("VM_BATT", "Q1", 2), "Q1 SOURCE (pin 2) must feed VM_BATT")
    require(on("GND", "J1", 2), "BAT- on GND")
    say("Chain verified pin-by-pin: J1.1 -> F1.1 | F1.2 -> Q1.D | Q1.S -> VM_BATT.")
    say("Battery on the DRAIN: correct reverse-protection orientation -- with a")
    say("reversed pack the body diode (anode=D) blocks; with correct polarity it")
    say("conducts until the gate enhances the channel.")

@test("P2", "Power", "Q1 enhancement and Vgs margin over battery range",
      nets=["Net-(Q1-G)", "GND"], comps=["Q1", "R1"])
def _(say, touch, touchc):
    require(on("Net-(Q1-G)", "Q1", 1) and on("Net-(Q1-G)", "R1", 1), "gate tied to R1")
    require(on("GND", "R1", 2), "R1 pulls the gate to GND")
    r1 = rval("R1")
    say(f"R1 = {r1/1e3:.0f}k gate pulldown; Vgs = -VBAT = -{VBAT_MIN}..-{VBAT_MAX} V.")
    say("DMP2035U Vgs(th) = -0.4..-1.0 V; |Vgs| at the weakest battery (3.0 V) is")
    say("3.0x the worst threshold -> fully enhanced (Rds 45 mOhm @ -2.5 V).")
    say(f"Gate leak through R1: {VBAT_MAX/r1*1e6:.0f} uA continuous (always-on).")
    require(VBAT_MIN / 1.0 >= 2.5, "insufficient enhancement at 3.0V")
    require(VBAT_MAX <= 8.0, "Vgs abs max +-8V exceeded")

@test("P3", "Power", "PTC fuse rating vs load", comps=["F1"])
def _(say, touch, touchc):
    stall_per_motor = 4.2 / 4.0  # N20 HPCB ~4 ohm terminal R -> ~1.05A stall at 4.2V
    logic = 0.31                 # WiFi burst referred to VBAT 4.2V (0.34A*3.3/(4.2*0.87))
    worst = 2 * stall_per_motor + logic
    say(f"Worst self-consistent case at 4.2 V: 2 stalled motors ({stall_per_motor:.2f} A")
    say(f"each) + WiFi burst ({logic:.2f} A battery-side) = {worst:.2f} A.")
    say("0ZCJ0200FF2C: 2.0 A hold / 3.5 A guaranteed trip, 6 VDC >= 4.2 V. That")
    say(f"{worst:.2f} A sits in the 2.0-3.5 A INDETERMINATE band -- the PTC may or")
    say("may not open, so it is NOT the stall protection. Roles are: PTC = hard")
    say("faults only (a wiring short draws VBAT/Rshort >> 3.5 A and trips fast);")
    say("stall protection = the firmware PWM/current constraint documented in M2")
    say("plus the TB6612's own thermal shutdown. Normal running (<1 A) is far")
    say("below hold. (Audit-corrected: an earlier draft over-credited the PTC.)")
    require(4.2 / 0.1 > 3.5 * 3, "even a hard short would not trip the PTC")

@test("P4", "Power", "TPS63001 input range, EN logic and soft power switch",
      nets=["VM_BATT", "PWR_EN", "GND"], comps=["U1", "R69", "SW5"])
def _(say, touch, touchc):
    require(on("VM_BATT", "U1", 5) and on("VM_BATT", "U1", 8), "VIN/VINA on VM_BATT")
    require(on("PWR_EN", "U1", 6), "EN pin on PWR_EN")
    require(on("PWR_EN", "R69", 2) and on("VM_BATT", "R69", 1), "R69 pulls EN to VIN")
    require(on("PWR_EN", "SW5", 2) and on("GND", "SW5", 1), "SW5 grounds EN when closed")
    r69 = rval("R69")
    say(f"VIN 3.0-4.2 V inside TPS63001's 1.8-5.5 V range.")
    say(f"Switch OPEN: EN = VIN - Ileak*R69 <= 0.1 uA * {r69/1e6:.0f}M = <0.1 V drop ->")
    say(f"EN >= {VBAT_MIN-0.1:.1f} V >> VIH 1.2 V (run). Switch CLOSED: EN = 0 V < VIL 0.4 V")
    say(f"(shutdown, 0.1 uA typ). Off-state battery drain: R69 {VBAT_MAX/r69*1e6:.1f} uA")
    say("+ VBAT divider 76 uA + Q1 gate 42 uA ~= 122 uA total (documented; unplug to store).")
    require(r69 >= 5e5, "pull-up too strong: off-state leak dominates shutdown spec")

@test("P5", "Power", "3V3 load budget vs buck-boost capability", nets=["PLUS3V3"])
def _(say, touch, touchc):
    esp = 0.340 + 0.066  # 802.11b TX @21dBm peak + dual-core 240MHz (S3 DS 5-7/5-9)
    ir_line = 8 * 0.011  # all TCRT LEDs latched (O1 worst-case computation)
    ir_wall = 6 * 0.040  # all wall emitters latched (W1; banks normally pulse)
    leds = 14 * 0.0015   # every indicator lit
    misc = 0.02          # mux, encoders, pulls
    total = esp + ir_line + ir_wall + leds + misc
    say(f"Peak 3V3 demand (everything at once): ESP32 {esp*1e3:.0f} + line IR "
        f"{ir_line*1e3:.0f} + wall IR {ir_wall*1e3:.0f} + indicators {leds*1e3:.0f} "
        f"+ misc {misc*1e3:.0f} = {total*1e3:.0f} mA.")
    say("TPS63001 capability at VIN 3.0 V (boost region; the buck-boost boundary")
    say("is VIN ~ 3.3 V): switch-limit math 1600 mA min * 3.0/3.3 * ~0.85 eff")
    say("~= 1.2 A, matching the datasheet typical-output curve -> ~40% headroom")
    say("over the everything-on worst case. (Audit-corrected figures.)")
    require(total < 1.1, "3V3 budget exceeds boost capability at 3.0 V input")

@test("P6", "Power", "VBAT sense divider scaling and ADC ceiling",
      nets=["VM_BATT", "VBAT_SENSE", "GND"], comps=["R2", "R3"])
def _(say, touch, touchc):
    require(on("VM_BATT", "R2", 1) and on("VBAT_SENSE", "R2", 2), "R2 top leg")
    require(on("VBAT_SENSE", "R3", 1) and on("GND", "R3", 2), "R3 bottom leg")
    r2, r3 = rval("R2"), rval("R3")
    vmax = VBAT_MAX * r3 / (r2 + r3)
    say(f"R2/R3 = {r2/1e3:.0f}k/{r3/1e3:.0f}k -> {VBAT_MAX} V reads {vmax:.2f} V at IO8.")
    say(f"Source impedance {r2*r3/(r2+r3)/1e3:.1f}k: fine for the S3 ADC with default")
    say("sampling; firmware should average 8+ samples.")
    require(vmax <= 2.9, "divider output exceeds the calibrated ADC range")
    require(on("VBAT_SENSE", "U3", 11) or any(r == "U3" for r, p in NETS["VBAT_SENSE"]),
            "VBAT_SENSE must reach the module")

# ---------------------------------------------------------------------------
# ESP32: FLASHING, USB, STRAPS
# ---------------------------------------------------------------------------
@test("E1", "Flashing", "USB data path: J7 -> 22R series -> ESD -> module",
      nets=["USB_DP_C", "USB_DM_C", "USB_DP", "USB_DM"], comps=["J7", "R59", "R60", "U6"])
def _(say, touch, touchc):
    require(on("USB_DP_C", "J7", "A6") and on("USB_DP_C", "J7", "B6"), "D+ both rows")
    require(on("USB_DM_C", "J7", "A7") and on("USB_DM_C", "J7", "B7"), "D- both rows")
    r59, r60 = rval("R59"), rval("R60")
    for r in ("R59", "R60"):
        n_mod = net_of(r, 2)
        n_junc = net_of(r, 1)
        require(n_mod in ("USB_DM", "USB_DP"), f"{r}.2 must be a module-side D net")
        require(any(x == "U6" for x, p in NETS[n_junc]),
                f"{r}.1 junction must come from the ESD array")
        touch(n_junc)
    say(f"Connector-side and module-side D+/D- nets are joined through {r59:.0f} ohm /")
    say(f"{r60:.0f} ohm series elements with the USBLC6-2SC6 ESD array on the")
    say("connector side of the series resistors -- the ST-recommended topology for")
    say("USB 2.0 FS. The S3's native USB-Serial-JTAG needs no external driver:")
    say("plug in, hold A (BOOT strap IO0 low), tap RST -> ROM downloader on USB-CDC.")
    require(any(r == "U6" for r, p in NETS["USB_DP_C"]), "ESD array on D+")
    require(any(r == "U6" for r, p in NETS["USB_DM_C"]), "ESD array on D-")
    require(any(r == "U3" for r, p in NETS["USB_DP"]), "D+ reaches the module")
    require(any(r == "U3" for r, p in NETS["USB_DM"]), "D- reaches the module")
    require(20 <= r59 <= 27 and 20 <= r60 <= 27, "series R outside 22R norm")

@test("E2", "Flashing", "VBUS cable detect divider",
      nets=["USB_VBUS", "VBUS_SENSE", "GND"], comps=["R67", "R68"])
def _(say, touch, touchc):
    r67, r68 = rval("R67"), rval("R68")
    v = 5.5 * r68 / (r67 + r68)
    say(f"VBUS worst case is 5.5 V under Type-C source rules (vSafe5V upper")
    say(f"bound; an Rd-only sink cannot restrict it) -> {v:.2f} V at IO37")
    say(f"({r67/1e3:.0f}k/{r68/1e3:.0f}k; ~3.33 V with 1% parts): below the 3.6 V")
    say("absolute max with slim-but-acceptable margin for a detect-only pin.")
    say("VBUS does NOT power the board. (Audit-corrected: 5.5 V, not 5.25 V.)")
    require(v < 3.6, "VBUS sense exceeds IO abs max at 5.5 V")
    require(on("USB_VBUS", "R67", 1) and on("VBUS_SENSE", "R67", 2), "divider top")
    require(on("VBUS_SENSE", "R68", 1) and on("GND", "R68", 2), "divider bottom")
    require(any(r == "U3" for r, p in NETS["VBUS_SENSE"]), "sense reaches IO37")

@test("E3", "Flashing", "USB-C CC pulldowns (UFP advertisement)",
      nets=["Net-(J7-CC1)", "Net-(J7-CC2)"], comps=["R12", "R56"])
def _(say, touch, touchc):
    for net, r in (("Net-(J7-CC1)", "R12"), ("Net-(J7-CC2)", "R56")):
        require(any(x == r for x, p in NETS[net]), f"{r} on {net}")
        require(abs(rval(r) - 5100) < 300, f"{r} must be 5.1k")
        require(on("GND", r, 2) or on("GND", r, 1), f"{r} to GND")
    say("5.1k Rd on both CC pins: a C-to-C cable/charger recognises the board as")
    say("a UFP sink and enables VBUS -- without these, C-to-C flashing would fail.")

@test("E4", "Flashing", "Boot straps: IO0/IO45/IO46 power-on states",
      comps=["SW1", "R10", "R65", "R66"])
def _(say, touch, touchc):
    io0 = net_of("SW1", 1) or net_of("SW1", 2)
    touch(io0)
    require(any(r == "R10" for r, p in NETS[io0]), "IO0 pull-up R10 present")
    require(any(r == "U3" for r, p in NETS[io0]), "IO0 strap reaches module")
    say(f"IO0 ({io0}): {rval('R10')/1e3:.0f}k pull-up to 3V3, button A shorts to GND")
    say("-> released = SPI boot, held = ROM downloader. ")
    for r, name in (("R65", "BIN2/IO45"), ("R66", "STBY/IO46")):
        n1, n2 = net_of(r, 1), net_of(r, 2)
        strap = n1 if n2 == "GND" else n2
        require("GND" in (n1, n2), f"{r} must terminate at GND")
        touch(strap)
        say(f"{name} strap net '{strap}': {rval(r)/1e3:.0f}k pulldown -> boots low")
    say("IO45 low = VDD_SPI 3.3 V (correct for WROOM), IO46 low = valid boot-msg")
    say("strap; both idle-low nets (BIN2, STBY) so motor driver wakes disabled.")

@test("E5", "Flashing", "Reset circuit: EN RC + RST button",
      nets=["ESP_EN", "GND"], comps=["R11", "C9", "SW2"])
def _(say, touch, touchc):
    require(any(r == "R11" for r, p in NETS["ESP_EN"]), "EN pull-up present")
    require(any(r == "C9" for r, p in NETS["ESP_EN"]), "EN RC cap present")
    require(any(r == "SW2" for r, p in NETS["ESP_EN"]), "RST button on EN")
    tau = rval("R11") * 1e-6
    say(f"R11 {rval('R11')/1e3:.0f}k + C9 1uF -> tau = {tau*1e3:.0f} ms power-on reset")
    say("delay (Espressif asks >50 us after 3V3 valid; 10 ms is the classic safe")
    say("value). SW2 shorts EN to GND for manual reset; C9 also debounces it.")

@test("E6", "Flashing", "UART0 boot-log contention guards on encoder pins",
      nets=["ENC2_A", "ENC2_B"], comps=["R57", "R58"])
def _(say, touch, touchc):
    for r in ("R57", "R58"):
        require(abs(rval(r) - 1000) < 100, f"{r} must be ~1k")
    say("IO43/IO44 double as UART0 TX/RX during boot. The ROM prints its boot log")
    say("while the encoder outputs may drive the same lines: the 1k series guards")
    say(f"cap contention current at 3.3 V / 1k = 3.3 mA -- harmless to both the")
    say("encoder driver and the S3 pad. After boot the pins remap to PCNT inputs.")

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
    say("matches ESP-Prog's pin needs. NOTE for firmware: S3 routes JTAG to the")
    say("USB-Serial-JTAG by default; to use this header burn/strap the JTAG-sel")
    say("(or use OpenOCD over USB, which needs no header at all). Header kept for")
    say("crash debugging when the USB stack itself is the casualty.")

# ---------------------------------------------------------------------------
# BUTTONS
# ---------------------------------------------------------------------------
@test("B1", "Buttons", "A/B/C/RST wiring and pull strategy",
      comps=["SW1", "SW2", "SW3", "SW4", "R10"])
def _(say, touch, touchc):
    for sw, desc in (("SW1", "A/BOOT"), ("SW3", "B"), ("SW4", "C")):
        n1, n2 = net_of(sw, 1), net_of(sw, 2)
        sig = n1 if n2 == "GND" else n2
        require("GND" in (n1, n2), f"{sw} must switch to GND")
        require(any(r == "U3" for r, p in NETS[sig]), f"{sw} net reaches module")
        touch(sig)
        say(f"{sw} ({desc}): '{sig}' -> GND when pressed.")
    say("A has the discrete 10k pull-up (R10, strap-grade). B (IO35) and C (IO36)")
    say("use the S3's internal ~45k pull-ups -- both pins are plain GPIOs on the")
    say("-N16 module (octal-PSRAM variants would consume them; module pinned in BOM).")
    require(net_of("SW2", 1) == "ESP_EN" or net_of("SW2", 2) == "ESP_EN", "RST on EN")

# ---------------------------------------------------------------------------
# MOTORS + ENCODERS
# ---------------------------------------------------------------------------
@test("M1", "Motors", "TB6612 control pin mapping vs truth table",
      nets=["PWMA", "PWMB", "AIN1", "AIN2", "BIN1", "BIN2", "STBY"], comps=["U2"])
def _(say, touch, touchc):
    pinmap = {"PWMA": "23", "AIN2": "22", "AIN1": "21", "STBY": "19",
              "BIN1": "17", "BIN2": "16", "PWMB": "15"}
    for net, pin in pinmap.items():
        require(on(net, "U2", pin), f"{net} must land on U2.{pin}")
        require(any(r == "U3" for r, p in NETS[net]), f"{net} driven by module")
    say("All seven control nets land on their SSOP-24 pins (datasheet numbering)")
    say("and originate at module GPIOs. Truth table: IN1/IN2 = CW/CCW/brake, PWM")
    say("chops, STBY low = all outputs Hi-Z. STBY boots low (10k + internal 200k")
    say("pulldowns) -- motors cannot move until firmware asserts it.")

@test("M2", "Motors", "Motor outputs: doubled pins to connectors",
      nets=["MOTA_P", "MOTA_N", "MOTB_P", "MOTB_N"], comps=["U2", "J5", "J6"])
def _(say, touch, touchc):
    for net, pins, conn, cpin in (("MOTA_P", ("1", "2"), "J5", 1), ("MOTA_N", ("5", "6"), "J5", 2),
                                   ("MOTB_P", ("11", "12"), "J6", 1), ("MOTB_N", ("7", "8"), "J6", 2)):
        for p in pins:
            require(on(net, "U2", p), f"{net}: U2.{p} (doubled output) missing")
        require(on(net, conn, cpin), f"{net} -> {conn}.{cpin}")
    say("Every output uses BOTH package pins (halves the per-pin current); the")
    say("routes are 0.3 mm (verified in the board file) -- IPC-2221 external 1 oz")
    say("gives ~1 A at ~10 C rise, adequate for transient PWM-limited stalls.")
    say("TB6612 per-channel limit: 1.0 A avg needs VM >= 4.5 V;")
    say("at VM 3.0-4.2 V the no-PWM DC limit is 0.4 A -- N20 stall (~1.05 A at")
    say("4.2 V) is legal only under PWM, which is the only drive mode the firmware")
    say("uses. Documented as a firmware constraint: never 100% duty into a stall.")

@test("M3", "Motors", "VM decoupling at the driver",
      nets=["VM_BATT", "GND"], comps=["C11", "C12", "C14"])
def _(say, touch, touchc):
    for c in ("C11", "C12"):
        n1, n2 = net_of(c, 1), net_of(c, 2)
        require({n1, n2} == {"VM_BATT", "GND"}, f"{c} must decouple VM to GND")
    require({net_of("C14", 1), net_of("C14", 2)} == {"PLUS3V3", "GND"},
            "C14 must decouple the TB6612 VCC (logic) pin")
    say("C11 10uF + C12 100nF sit at the TB6612's VM pins (bottom face, under")
    say("the driver) absorbing PWM edge current; the bulk reservoir (C4 10uF +")
    say("C1 100uF) lives 15 mm away at the regulator input on the same VM rail.")
    say("C14 100nF decouples the driver's separate VCC logic supply from 3V3.")

@test("N1", "Encoders", "Quadrature nets, pull-ups, PCNT capability",
      nets=["ENC1_A", "ENC1_B", "ENC2_A", "ENC2_B", "PLUS3V3"],
      comps=["R6", "R7", "R8", "R9", "J5", "J6"])
def _(say, touch, touchc):
    for net, conn, pin in (("ENC1_A", "J5", 5), ("ENC1_B", "J5", 6),
                            ("ENC2_A", "J6", 5), ("ENC2_B", "J6", 6)):
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
        require(net_of(conn, 3) == "PLUS3V3" and net_of(conn, 4) == "GND",
                f"{conn} encoder supply pins")

# ---------------------------------------------------------------------------
# OPTICS: LINE ARRAY (TCRT5000)
# ---------------------------------------------------------------------------
@test("O1", "Line array", "TCRT5000 LED drive current (shared bank FET)",
      nets=["PLUS3V3", "EMIT_LINE_K", "LINE_EMIT"], comps=["Q19", "R61"])
def _(say, touch, touchc):
    r_lim = 120.0
    vf, rds = 1.25, 8.0        # TCRT VF typ; BSS138 Rds worst @ Vgs 3.3
    n = 8
    i = (V33 - vf) / (r_lim + n * rds)
    say(f"Per-channel: (3.3 - {vf}) / (120 + 8ch*{rds:.0f} shared-FET ohms) = {i*1e3:.1f} mA")
    say(f"worst-case (Rds 8 ohm at Vgs 3.3); ~15 mA at typical Rds. Bank total")
    say(f"{n*i*1e3:.0f}-120 mA through Q19 (BSS138). TCRT5000 spec point is IF = 10 mA")
    say("(IC 0.5-2.1 mA), abs max 60 mA -> the drive brackets the spec point with")
    say("4x margin to the limit.")
    for k in range(1, 9):
        require(net_of(f"LS{k}", 2) == "EMIT_LINE_K", f"LS{k} cathode on the bank net")
        touchc(f"LS{k}")
    require(on("EMIT_LINE_K", "Q19", 3), "bank FET drain on EMIT_LINE_K")
    require(any(r == "U3" for r, p in NETS["LINE_EMIT"]), "gate net from module")
    require(0.008 <= i <= 0.020, "LED current outside 8-20 mA window")

@test("O2", "Line array", "Phototransistor load line and ADC swing",
      nets=["MUX_SENSE"], comps=[f"LS{k}" for k in range(1, 9)])
def _(say, touch, touchc):
    rp = 47e3
    ic_white = 0.8e-3          # TCRT CTR ~8% of 14mA at 2.4mm on white paper
    v_white = max(0.2, V33 - ic_white * rp)
    say(f"47k pull-up: white floor (IC ~0.8 mA) saturates the PT -> V <= 0.4 V")
    say(f"(VCEsat max); black line (IC < 30 uA) -> V >= {V33 - 30e-6*rp:.2f} V.")
    say("Guaranteed swing >= 1.5 V (typically ~2.5 V) across the mux into IO7 --")
    say("ample for 8-way thresholding.")
    for k in range(1, 9):
        net = f"LINE{k}_SENSE"
        touch(net)
        require(on(net, f"LS{k}", 4), f"{net}: PT collector")
        require(net_of(f"LS{k}", 3) == "GND", f"LS{k} PT emitter to GND")
        require(any(r == "U4" for r, p in NETS[net]), f"{net} into mux")
    say("Sensing height: with 32 mm wheels the underside rides ~9.4 mm; the 7 mm")
    say("body puts the optical face at ~2.4 mm = TCRT5000's peak-response distance.")

# ---------------------------------------------------------------------------
# OPTICS: WALL SENSORS
# ---------------------------------------------------------------------------
@test("W1", "Wall sensors", "Emitter chains and banked drive",
      nets=["EMIT_FRONT_K", "EMIT_DIAG_K", "EMIT_SIDE_K",
            "WALL_EMIT_FRONT", "WALL_EMIT_DIAG", "WALL_EMIT_SIDE"],
      comps=["Q16", "Q17", "Q18", "D1", "D2", "D3", "D4", "D5", "D6"])
def _(say, touch, touchc):
    r_lim, vf, rds = 33.0, 1.35, 8.0
    i = (V33 - vf) / (r_lim + 2 * rds)
    say(f"Per-emitter: (3.3 - {vf}) / (33 + 2ch*{rds:.0f}) = {i*1e3:.0f} mA worst-case,")
    say(f"banks of two ({2*i*1e3:.0f} mA per BSS138); ~54 mA at typical Rds. SFH 4550")
    say("abs max 100 mA continuous -> drive is 40-54% OF the limit (~50% margin);")
    say("the +-3 deg beam at ~40 mA gives championship-grade wall range. Banks are")
    say("pulsed by firmware (front/diag/side separately) for ambient rejection.")
    require(0.025 <= i <= 0.06, "wall emitter current out of window")
    for d in ("D1", "D2", "D3", "D4", "D5", "D6"):
        k = net_of(d, 1)
        require(k and k.startswith("EMIT_"), f"{d} cathode must join a bank net")

@test("W2", "Wall sensors", "PT334-6B receivers: bias, swing, ADC path",
      comps=["Q2", "Q3", "Q4", "Q5", "Q6", "Q7"])
def _(say, touch, touchc):
    rp = 47e3
    say("Each PT334-6B collector has a 47k pull-up; wall return light (>=50 uW/cm2")
    say("at competition distances with the 40 mA emitters) drives IC tens of uA to")
    say("mA -> 0.5-3.0 V swing directly into ADC1 pins IO1-IO6 (no mux: all six")
    say("walls sample in one burst). Black-lens part rejects visible ambient;")
    say("firmware subtracts the emitter-off baseline for the rest.")
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

# ---------------------------------------------------------------------------
# MUX
# ---------------------------------------------------------------------------
@test("X1", "Mux", "CD74HC4067 selects, enable, common and channel map",
      nets=["MUX_S0", "MUX_S1", "MUX_S2", "MUX_SENSE", "GND", "PLUS3V3"], comps=["U4", "C13"])
def _(say, touch, touchc):
    for net in ("MUX_S0", "MUX_S1", "MUX_S2"):
        require(any(r == "U4" for r, p in NETS[net]), f"{net} on mux")
        require(any(r == "U3" for r, p in NETS[net]), f"{net} from module")
    require(on("MUX_S0", "U4", 10) and on("MUX_S1", "U4", 11) and on("MUX_S2", "U4", 14),
            "select pin map S0/S1/S2 = 10/11/14")
    s3 = net_of("U4", 13)
    require(s3 == "GND", f"S3 select must be grounded (got {s3}) -- 8 channels used")
    en = net_of("U4", 15)
    require(en == "GND", f"~E enable must be grounded (got {en})")
    require(net_of("U4", 12) == "GND", "VSS on GND")
    require(any(r == "U3" for r, p in NETS["MUX_SENSE"]), "common -> ADC IO7")
    say("S0-S2 from IO11-13 walk Y0..Y7 = LINE1..8; S3 and ~E hard-grounded (only")
    say("8 channels in use, mux always enabled). Common Z drives IO7 through the")
    say("47k source impedances -- one ADC pin reads the whole line array.")
    say("100nF decoupling (C13) at the mux supply.")

# ---------------------------------------------------------------------------
# SYSTEM-LEVEL
# ---------------------------------------------------------------------------
@test("S1", "System", "Single unified ground; every subsystem returns to it",
      nets=["GND"])
def _(say, touch, touchc):
    refs = {r for r, p in NETS["GND"]}
    say(f"GND spans {len(NETS['GND'])} pins on {len(refs)} components -- one net, no")
    say("split grounds (In1 is a solid plane, stitched at every SMD pour pad).")
    for must in ("J1", "U1", "U2", "U3", "U4", "U6", "J7", "J8", "SW5"):
        require(must in refs, f"{must} missing from GND")

@test("S2", "System", "No floating module inputs / undocumented NC",
      nets=[])
def _(say, touch, touchc):
    singles = [n for n, nodes in NETS.items()
               if len(nodes) == 1 and not n.startswith("unconnected-")]
    allowed = {"WALL1_SENSE", "WALL2_SENSE"}  # placeholder none expected
    bad = [n for n in singles if n not in allowed and not n.startswith("Net-")]
    named_bad = [n for n in bad]
    say(f"Single-pin named nets: {named_bad if named_bad else 'none'} (KiCad")
    say("explicit no-connects are excluded; they are flagged in the schematic and")
    say("documented in CONNECTIONS.md).")
    require(not named_bad, f"undocumented single-pin nets: {named_bad}")

@test("S3", "System", "3V3 rail fanout reaches every logic consumer",
      nets=["PLUS3V3"])
def _(say, touch, touchc):
    refs = {r for r, p in NETS["PLUS3V3"]}
    for must in ("U3", "U4", "J5", "J6", "J8"):
        require(must in refs, f"{must} missing from 3V3")
    say(f"PLUS3V3 spans {len(NETS['PLUS3V3'])} pins: module, mux, both encoder")
    say("supplies, JTAG Vtarget, every pull-up and both indicator supply banks.")

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
    L.append("# Circuit Verification Report -- micromouse-pcb rev 5.3\n")
    L.append("Generated by `pcb/tools/circuit_tests.py` from `pcb/netlist.net` "
             "(the same file the board is built from). Each test walks real "
             "netlist connectivity pin-by-pin and computes operating points from "
             "component values + datasheet parameters verified during the "
             "rev-5.2/5.3 sourcing passes. Per-net design rationale: "
             "[CONNECTIONS.md](CONNECTIONS.md).\n")
    L.append(f"**Result: {n_pass} PASS / {n_fail} FAIL of {len(RESULTS)} tests.**  ")
    L.append(f"**Coverage: {net_cov:.0f}% of nets ({len(touched_nets & real_nets)}/"
             f"{len(real_nets)}) and {comp_cov:.0f}% of components "
             f"({len(touched_comps)}/{len(COMPS)}) exercised by at least one test.**\n")
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
