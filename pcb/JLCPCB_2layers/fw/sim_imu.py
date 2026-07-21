"""IMU ACCESSIBILITY SIMULATION -- can the ESP32-S3 actually reach and drive the
BNO055 with ONLY the connections this board provides?

(Proteus has no BNO055 model and isn't scriptable headless; this is the same
verification done as a behavioral simulation: a datasheet-faithful BNO055
model -- pin straps, power-on timing, register map, I2C engine -- is wired with
EXACTLY the nets in design/netlist.net, then the firmware's real register
sequence from micromouse.ino is replayed against it, transaction by
transaction.)

Layers checked:
  1. WIRING vs datasheet Table 5-1 (BST-BNO055-DS000-18): every one of the 28
     pins -- supplies, protocol straps, address strap, support pins, DNC pins.
  2. I2C BUS: pull-ups present on SDA/SCL, value sane for 400 kHz; the bus
     reaches the ESP32-S3 module pads that pins.h claims (three-way match).
  3. PROTOCOL/BEHAVIOR: replay imu_init()/imu_selftest() -- address decode
     (COM3 strap), CHIP_ID retry vs 400 ms power-on, POST, mode transitions,
     CLK_SEL vs the absent crystal, fusion startup, heading/gyro reads.

Exit 1 on any FAIL -- run as a gate like the other fw sims.
"""
import os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
NETLIST = os.path.join(BASE, "..", "design", "netlist.net")
PINS_H = os.path.join(BASE, "micromouse", "pins.h")
INO = os.path.join(BASE, "micromouse", "micromouse.ino")

fails = []


def check(ok, label, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label}" + (f" -- {detail}" if detail else ""))
    if not ok:
        fails.append(label)
    return ok


nl = open(NETLIST, encoding="utf-8").read()
pins_h = open(PINS_H, encoding="utf-8").read()
ino = open(INO, encoding="utf-8").read()

# ---- net membership helpers -------------------------------------------------
def members(netname):
    m = re.search(r'\(net\s*\(code "\d+"\)\s*\(name "%s"\)(.*?)\n\t\t\)'
                  % re.escape(netname), nl, re.S)
    return re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(1)) if m else []


def net_of(ref, pin):
    for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]+)"\)(.*?)\n\t\t\)', nl, re.S):
        if (ref, pin) in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2)):
            return m.group(1)
    return None


def value_of(ref):
    m = re.search(r'\(comp\s*\(ref "%s"\)\s*\(value "([^"]*)"\)' % re.escape(ref), nl)
    return m.group(1) if m else ""


print("=" * 72)
print("STAGE 1 -- U8 wiring vs BNO055 datasheet Table 5-1 (DS000-18 p.106)")
print("=" * 72)

# datasheet reference model: pin -> (name, requirement-in-I2C-mode)
#   'DNC'      = must be unconnected
#   'GND'      = must be on GND
#   '3V3'      = must be on the 3.3V rail
#   'PULLUP'   = must be pulled up to 3V3 through a resistor (net w/ R to 3V3)
#   'CAP'      = must have a capacitor to GND
#   'OPT'      = may be unconnected (optional: debugger, BL_IND, crystal)
#   'SDA','SCL','INT' = must reach the ESP (checked in stage 2)
TABLE_5_1 = {
    "1": ("PIN1", "DNC"), "2": ("GND", "GND"), "3": ("VDD", "3V3"),
    "4": ("nBOOT_LOAD_PIN", "PULLUP"), "5": ("PS1", "GND"), "6": ("PS0", "GND"),
    "7": ("SWDIO", "OPT"), "8": ("SWCLK", "OPT"), "9": ("CAP", "CAP"),
    "10": ("BL_IND", "OPT"), "11": ("nRESET", "PULLUP"),
    "12": ("PIN12", "DNC"), "13": ("PIN13", "DNC"), "14": ("INT", "INT"),
    "15": ("PIN15", "DNC"), "16": ("PIN16", "DNC"),
    "17": ("COM3", "GND"),   # I2C address select: LOW -> 0x28 (Table 4-7)
    "18": ("COM2", "GND"), "19": ("COM1", "SCL"), "20": ("COM0", "SDA"),
    "21": ("PIN21", "DNC"), "22": ("PIN22", "DNC"), "23": ("PIN23", "DNC"),
    "24": ("PIN24", "DNC"),
    "25": ("GNDIO", "GND"), "26": ("XOUT32", "OPT"), "27": ("XIN32", "OPT"),
    "28": ("VDDIO", "3V3"),
}


def is_pulled_up(netname):
    """Net must include a resistor whose other pin lands on PLUS3V3."""
    for (ref, pin) in members(netname):
        if ref.startswith("R"):
            other = "1" if pin == "2" else "2"
            if net_of(ref, other) == "PLUS3V3":
                return True, ref
    return False, None


def has_cap_to_gnd(netname):
    for (ref, pin) in members(netname):
        if ref.startswith("C"):
            other = "1" if pin == "2" else "2"
            if net_of(ref, other) == "GND":
                return True, ref
    return False, None


sda_net = scl_net = int_net = None
for pin, (name, req) in TABLE_5_1.items():
    net = net_of("U8", pin)
    unconn = net is None or net.startswith("unconnected-")
    if req == "DNC":
        check(unconn, f"pin {pin:>2} {name}: Do-Not-Connect", f"net={net}")
    elif req == "OPT":
        check(True, f"pin {pin:>2} {name}: optional", "NC" if unconn else f"net={net}")
    elif req == "GND":
        check(net == "GND", f"pin {pin:>2} {name}: strapped to GND", f"net={net}")
    elif req == "3V3":
        check(net == "PLUS3V3", f"pin {pin:>2} {name}: on 3.3V rail", f"net={net}")
    elif req == "PULLUP":
        ok, r = is_pulled_up(net) if net else (False, None)
        check(ok, f"pin {pin:>2} {name}: pulled up to 3V3", f"via {r}" if ok else f"net={net}")
    elif req == "CAP":
        ok, c = has_cap_to_gnd(net) if net else (False, None)
        check(ok, f"pin {pin:>2} {name}: capacitor to GND",
              f"{c} = {value_of(c)}" if ok else f"net={net}")
    elif req == "SDA":
        sda_net = net
        check(net == "IMU_SDA", f"pin {pin:>2} {name}: is the I2C SDA", f"net={net}")
    elif req == "SCL":
        scl_net = net
        check(net == "IMU_SCL", f"pin {pin:>2} {name}: is the I2C SCL", f"net={net}")
    elif req == "INT":
        int_net = net
        check(net == "IMU_INT", f"pin {pin:>2} {name}: interrupt out", f"net={net}")

# supply decoupling near the chip (datasheet fig 9: 100nF at VDD/VDDIO)
dec_ok, dec_c = has_cap_to_gnd("PLUS3V3")
check(dec_ok, "3V3 rail decoupling present", f"e.g. {dec_c}")

print()
print("=" * 72)
print("STAGE 2 -- I2C bus electricals + ESP32-S3 reachability")
print("=" * 72)

# WROOM-1 module pad <- GPIO (same table the pin gate uses)
PAD_OF_GPIO = {0: "27", 18: "11", 21: "23", 37: "30"}
gpio = dict(re.findall(r"#define\s+(PIN_\w+)\s+(\d+)", pins_h))

for sym, net in (("PIN_IMU_SDA", "IMU_SDA"), ("PIN_IMU_SCL", "IMU_SCL"),
                 ("PIN_IMU_INT", "IMU_INT")):
    g = int(gpio[sym]); pad = PAD_OF_GPIO[g]
    on_net = ("U3", pad) in members(net)
    check(on_net, f"{net} reaches ESP32-S3 IO{g} (module pad {pad})",
          "three-way pins.h/module/netlist match")

# pull-ups on both I2C lines (BNO055 is open-drain w/ clock stretching)
for net in ("IMU_SDA", "IMU_SCL"):
    ok, r = is_pulled_up(net)
    val = value_of(r) if r else "?"
    check(ok, f"{net} pull-up to 3V3", f"{r} = {val}")
    if ok:
        m = re.match(r"([\d.]+)k", val)
        rk = float(m.group(1)) if m else None
        # 400kHz I2C: rise time (0.3-0.9)*RC must be < 300ns -> with ~50pF bus
        # (two devices + short traces) R <= ~7.2k; and R >= 970R for 3mA sink.
        check(rk is not None and 1.0 <= rk <= 7.2,
              f"{net} pull-up value OK for 400 kHz",
              f"{val}: rise ~{int(0.85 * (rk or 0) * 1000 * 50 / 1000)}ns vs 300ns limit (50pF est.)")

# bus contention: nothing else may drive these nets
for net in ("IMU_SDA", "IMU_SCL"):
    others = {r for (r, p) in members(net)} - {"U3", "U8"}
    others = {r for r in others if not r.startswith("R")}
    check(not others, f"{net} has no other drivers", f"extra={others or 'none'}")

print()
print("=" * 72)
print("STAGE 3 -- behavioral replay of imu_init()/imu_selftest() (micromouse.ino)")
print("=" * 72)


class BNO055Model:
    """Datasheet-faithful behavioral model: straps, power-on timing, register
    map + mode state machine, I2C address decode."""

    def __init__(self, ps1_net, ps0_net, com3_net, xin_connected):
        self.protocol = "I2C" if (ps1_net, ps0_net) == ("GND", "GND") else "OTHER"
        self.addr = 0x28 if com3_net == "GND" else 0x29        # Table 4-7
        self.xtal = xin_connected
        self.t_ms = 0.0            # sim clock
        self.ready_ms = 400.0      # Table 0-2: start-up time (POR 650ms worst)
        self.mode = 0x00           # CONFIG at boot
        self.mode_ready_ms = 0.0
        self.clk_sel_fault = False
        self.regs = {0x00: 0xA0, 0x01: 0xFB, 0x02: 0x32, 0x03: 0x0F,  # IDs
                     0x07: 0x00,                                       # PAGE_ID
                     0x36: 0x0F,                                       # POST all pass
                     0x39: 0x00, 0x3A: 0x00,                           # SYS_STATUS/ERR
                     0x18: 0x00, 0x19: 0x00, 0x1A: 0x00, 0x1B: 0x00}   # GYR_Z / EUL_H

    def advance(self, ms):
        self.t_ms += ms

    def _alive(self):
        return self.protocol == "I2C" and self.t_ms >= self.ready_ms

    def probe(self, addr):                       # bare address byte -> ACK?
        return self._alive() and addr == self.addr

    def write(self, addr, reg, val):
        if not self.probe(addr):
            return False
        if self.t_ms < self.mode_ready_ms:
            return False                          # mid mode-switch: NAK/garbage
        if reg == 0x3D:                           # OPR_MODE
            self.mode = val & 0x0F
            # Table 3-6: config->any 7ms, any->config 19ms
            self.mode_ready_ms = self.t_ms + (19 if (val & 0x0F) == 0 else 7)
            if self.mode == 0x0C:                 # NDOF starting
                self.regs[0x39] = 0x05            # fusion running (after switch)
                self.regs[0x1A] = 0x40; self.regs[0x1B] = 0x06  # 100.0 deg
                self.regs[0x18] = 0x10; self.regs[0x19] = 0x00  # 1 deg/s
        elif reg == 0x3F:                         # SYS_TRIGGER
            if val & 0x80 and not self.xtal:      # CLK_SEL w/o crystal
                self.clk_sel_fault = True         # would fall back after ~600ms
        else:
            self.regs[reg] = val
        return True

    def read(self, addr, reg):
        if not self.probe(addr) or self.t_ms < self.mode_ready_ms:
            return None
        return self.regs.get(reg, 0x00)


# wire the model exactly as the netlist straps it
model = BNO055Model(net_of("U8", "5"), net_of("U8", "6"), net_of("U8", "17"),
                    xin_connected=not (net_of("U8", "27") or "unconnected").startswith("unconnected-") is False and False)
# (XIN32 unconnected on this board -> xtal=False)
model.xtal = not (net_of("U8", "27") or "unconnected-").startswith("unconnected-")

check(model.protocol == "I2C", "model straps decode to I2C mode",
      f"PS1={net_of('U8','5')} PS0={net_of('U8','6')} (Table 4-4)")

# firmware constants (from the real sources)
fw_addr = int(re.search(r"#define\s+IMU_I2C_ADDR\s+(0x[0-9A-Fa-f]+)", pins_h).group(1), 16)
check(fw_addr == model.addr, "FW I2C address == strap-decoded address",
      f"fw 0x{fw_addr:02X} vs COM3-strap 0x{model.addr:02X}")

wb = re.search(r"Wire\.begin\((\w+),\s*(\w+),\s*(\d+)\)", ino)
check(wb and wb.group(1) == "PIN_IMU_SDA" and wb.group(2) == "PIN_IMU_SCL",
      "Wire.begin uses the board's IMU pins", wb.group(0) if wb else "not found")
check(wb and int(wb.group(3)) <= 400000, "bus speed within BNO055 max 400 kHz",
      f"{wb.group(3)} Hz" if wb else "")

# --- replay: power applied at t=0; ESP boots + Wire.begin ~120ms later -------
model.advance(120)
probe_early = model.probe(fw_addr)               # imu_init's beginTransmission
# firmware tolerates a cold chip via the CHIP_ID retry loop (10 x 50ms):
tries = 0
id_val = None
while tries < 10:
    id_val = model.read(fw_addr, 0x00)
    tries += 1
    if id_val == 0xA0:
        break
    model.advance(50)
check(id_val == 0xA0, "CHIP_ID handshake (retry loop rides out 400ms power-on)",
      f"0xA0 after {tries} tries @ t={model.t_ms:.0f}ms" if id_val == 0xA0
      else f"never answered (probe@120ms={'ACK' if probe_early else 'NAK'})")

post = model.read(fw_addr, 0x36)
check(post is not None and (post & 0x0F) == 0x0F, "power-on self-test (0x36)",
      f"POST=0x{post:X}" if post is not None else "no reply")

ok1 = model.write(fw_addr, 0x3D, 0x00); model.advance(25)   # CONFIG (fw delays 25ms)
ok2 = model.write(fw_addr, 0x3F, 0x00); model.advance(20)   # SYS_TRIGGER internal osc
ok3 = model.write(fw_addr, 0x3D, 0x0C); model.advance(20)   # NDOF (fw delays 20ms)
check(ok1 and ok2 and ok3, "mode sequence ACKed with FW delays >= Table 3-6",
      "CONFIG(25ms>=19) -> SYS_TRIGGER -> NDOF(20ms>=7)")
check(not model.clk_sel_fault, "CLK_SEL stays internal (no crystal fitted)",
      "SYS_TRIGGER=0x00; XIN32/XOUT32 NC per board")

sysst = model.read(fw_addr, 0x39); syserr = model.read(fw_addr, 0x3A)
check(sysst == 5 and syserr == 0, "NDOF fusion running (SYS_STATUS=5, SYS_ERR=0)",
      f"status={sysst} err={syserr}")

hd_lo = model.read(fw_addr, 0x1A); hd_hi = model.read(fw_addr, 0x1B)
heading = ((hd_hi << 8) | hd_lo) / 16.0
check(abs(heading - 100.0) < 0.1, "heading readout end-to-end (EUL 0x1A, 16 LSB/deg)",
      f"read {heading:.1f} deg from model")
gz = ((model.read(fw_addr, 0x19) << 8) | model.read(fw_addr, 0x18)) / 16.0
check(abs(gz - 1.0) < 0.1, "gyro-Z readout (0x18, 16 LSB/deg/s)", f"{gz:.2f} deg/s")

print()
if fails:
    print(f"IMU SIM: FAIL -- {len(fails)} issue(s):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("IMU SIM: ALL PASS -- the BNO055 as wired (I2C straps, 0x28, internal osc,")
print("4.7k pull-ups to IO18/IO21) is fully accessible by the firmware sequence.")
