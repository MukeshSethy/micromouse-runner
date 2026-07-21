"""PRE-ORDER FLIGHT CHECKS: the specific first-board killers for flashing,
sensors and motors, verified from the real netlist + firmware sources.

  F1  ESD array channel pairing (USBLC6-2SC6 pass-through 1<->6, 3<->4 --
      crossing channels is a classic dead-USB wiring bug)
  F2  USB data nets have NO stubs/branches (exact expected node sets)
  F3  VBUS sense divider lands inside the ADC range (5V -> <=3.3V)
  S1  every ANALOG input is on ADC1 (GPIO1-10) -- ADC2 is unusable with
      WiFi active on the ESP32-S3; an ADC2 sensor pin dies the moment
      telemetry starts
  S2  mux settling: source impedance x ADC sample cap << firmware scan slot
  M1  LEDC PWM frequency within the TB6612 spec (<=100 kHz)
  M2  TB6612 channel rating vs N20 stall: 1.6A stall < 3.2A peak, but
      > 1.2A continuous -> the firmware MUST carry a stall guard; assert
      the encoder-stall watchdog exists in micromouse.ino
  M3  encoder inputs have pull-up/guard networks on their nets

Exit 1 on any failure.  Run:  python fw/sim_preflight.py
"""
import os
import re
import sys

FW = os.path.dirname(os.path.abspath(__file__))
NET = open(os.path.join(FW, "..", "design", "netlist.net"), encoding="utf-8").read()
PINS = open(os.path.join(FW, "micromouse", "pins.h"), encoding="utf-8").read()
INO = open(os.path.join(FW, "micromouse", "micromouse.ino"), encoding="utf-8").read()
FAILS = []


def nodes(name):
    m = re.search(r'\(net\s*\(code "\d+"\)\s*\(name "%s"\)(.*?)(?=\(net\s*\(code|\Z)'
                  % re.escape(name), NET, re.S)
    if not m:
        return set()
    return {f"{r}.{p}" for r, p in
            re.findall(r'\(node\s*\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(1))}


def check(cond, what, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {what}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILS.append(what)


print("PRE-ORDER FLIGHT CHECKS (flashing / sensors / motors)")
print("=" * 70)

print("F1 ESD array channel pairing (USBLC6-2SC6)")
check(nodes("USB_DM_C") >= {"U6.1"} and nodes("USB_DM") >= {"U6.6"},
      "D- uses channel 1 straight through", "in pin 1 -> out pin 6")
check(nodes("USB_DP_C") >= {"U6.3"} and nodes("USB_DP") >= {"U6.4"},
      "D+ uses channel 2 straight through", "in pin 3 -> out pin 4")

print("F2 USB data nets: exact topology, no stubs")
check(nodes("USB_DM_C") == {"J7.A7", "J7.B7", "U6.1"}, "USB_DM_C = J7(A7,B7)+U6.1 only")
check(nodes("USB_DP_C") == {"J7.A6", "J7.B6", "U6.3"}, "USB_DP_C = J7(A6,B6)+U6.3 only")
check(nodes("USB_DM") == {"U6.6", "U3.13"}, "USB_DM = U6.6+module only")
check(nodes("USB_DP") == {"U6.4", "U3.14"}, "USB_DP = U6.4+module only")

print("F3 VBUS sense divider")
vals = dict(re.findall(r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)', NET))
r67 = float(vals["R67"].rstrip("k")) * 1e3
r68 = float(vals["R68"].rstrip("k")) * 1e3
vs = 5.25 * r68 / (r67 + r68)
check(vs <= 3.3, "worst-case VBUS (5.25V) sense within ADC range",
      f"{r67/1e3:.0f}k/{r68/1e3:.0f}k -> {vs:.2f} V")

print("S1 all analog inputs on ADC1 (GPIO1-10; ADC2 dies with WiFi)")
# 2-layer: 6 wall channels + 2 DIRECT-ADC telemetry taps (per-cell removed).
analog = ["PIN_WALL1_SENSE", "PIN_WALL2_SENSE", "PIN_WALL3_SENSE",
          "PIN_WALL4_SENSE", "PIN_WALL5_SENSE", "PIN_WALL6_SENSE",
          "PIN_VBAT_SENSE", "PIN_VBUS_SENSE"]
declared = dict(re.findall(r"#define\s+(PIN_\w+)\s+(\d+)", PINS))
bad = [(a, declared.get(a)) for a in analog
       if not (declared.get(a) and 1 <= int(declared[a]) <= 10)]
check(not bad, "8 analog channels all on ADC1",
      "WALL1-6 + VBAT/VBUS on GPIO " + ",".join(declared[a] for a in analog))

print("S2 telemetry-divider settling vs ADC sample slot")
# 2-layer: no mux. Worst source impedance is the VBAT divider 100k||39k ~= 28k
# into the S3 ADC sampling cap (~10 pF): tau ~ 0.28 us; 5-tau settle ~ 1.4 us,
# far inside any read cadence -- and the fw reads telemetry at <=10 Hz.
r_src = 100e3 * 39e3 / (100e3 + 39e3)
tau_us = (r_src + 125) * 10e-12 * 1e6
slot_us = 1e6 / 500 / 2            # 500 Hz loop, conservative half-slot per read
check(5 * tau_us < slot_us, "5-tau divider settle fits the ADC slot",
      f"{5*tau_us:.1f} us << {slot_us:.0f} us (source ~{r_src/1e3:.0f}k)")

print("M1 PWM frequency vs TB6612")
m = re.search(r"PWM_FREQ\s*=\s*(\d+)", INO)
check(m and int(m.group(1)) <= 100000, "LEDC within TB6612 100 kHz max",
      f"{m.group(1)} Hz" if m else "PWM_FREQ not found")

print("M2 TB6612 channel rating vs N20 stall")
check(1.6 < 3.2, "stall 1.6A < 3.2A per-channel PEAK", "transients OK")
guard = "stall_check" in INO and "STALL_MS" in INO and "stall_latched" in INO
check(guard, "encoder-stall watchdog present in firmware",
      "stall 1.6A > 1.2A CONTINUOUS rating -> watchdog cuts drive after 800ms")

print("M3 encoder input networks")
for net_, need in (("ENC1_A", "R6"), ("ENC1_B", "R7")):
    check(any(x.startswith(need + ".") for x in nodes(net_)),
          f"{net_} carries its pull-up {need}")
for net_ in ("ENC2_A", "ENC2_B"):
    ns = nodes(net_)
    check(len(ns) >= 3, f"{net_} has pull-up + series guard", str(sorted(ns)))

print("I1 IMU I2C bus: exact topology + pull-ups + Fast-mode rise time")
check(nodes("IMU_SDA") == {"R77.2", "U3.11", "U8.20"}, "IMU_SDA = pull-up + IO18 + COM0 only")
check(nodes("IMU_SCL") == {"R78.2", "U3.23", "U8.19"}, "IMU_SCL = pull-up + IO21 + COM1 only")
check({"R77.1", "R78.1"} <= nodes("PLUS3V3"), "both I2C pull-ups tied to 3V3")
r_pu = float(vals["R77"].rstrip("k")) * 1e3
# bus is two 15mm traces + 3 pins: ~30pF worst case; I2C Fast-mode needs
# rise time (0.8473*R*C) < 300ns at 400kHz
t_rise = 0.8473 * r_pu * 30e-12
check(t_rise < 300e-9, "400kHz Fast-mode rise time with the board pull-ups",
      f"{r_pu/1e3:.1f}k x 30pF -> {t_rise*1e9:.0f} ns < 300 ns")

print("I2 IMU protocol/address straps (BNO055 in I2C mode at 0x28)")
gnd = nodes("GND")
for pin, what in (("U8.5", "PS1"), ("U8.6", "PS0"), ("U8.17", "COM3/addr"), ("U8.18", "COM2")):
    check(pin in gnd, f"{what} strapped to GND", f"{pin}")
# PS1=PS0=0 -> I2C; COM3=0 -> address 0x28 (matches fw IMU_I2C_ADDR)
check(re.search(r"#define\s+IMU_I2C_ADDR\s+0x28", PINS) is not None,
      "fw IMU_I2C_ADDR matches the COM3 strap (0x28)")

print("I3 IMU boot/reset pull-ups (a floating nRESET = dead-flaky IMU)")
check(nodes("Net-(U8-~{BOOT_LOAD_PIN})") == {"R79.2", "U8.4"} and "R79.1" in nodes("PLUS3V3"),
      "nBOOT_LOAD_PIN held high by R79", "low would trap the bootloader")
check(nodes("Net-(U8-~{RESET})") == {"R80.2", "U8.11"} and "R80.1" in nodes("PLUS3V3"),
      "nRESET held high by R80")

print("I4 IMU supplies + CAP bypass")
check({"U8.3", "U8.28"} <= nodes("PLUS3V3"), "VDD + VDDIO both on 3V3")
check(nodes("Net-(U8-CAP)") == {"C20.1", "U8.9"} and vals.get("C20") == "100nF",
      "internal-LDO CAP pin bypassed (C20 100nF)")
check({"C23.1", "C24.1"} <= nodes("PLUS3V3"), "local decoupling C23/C24 at the IMU")

print("I5 IMU interrupt reaches the controller")
check(nodes("IMU_INT") == {"U3.30", "U8.14"}, "INT -> IO37 (module pad 30), no stubs")

print("I6 IMU firmware register audit (against the BNO055 datasheet)")
# XIN32/XOUT32 are UNCONNECTED on this board -> the fw MUST select the
# internal oscillator (SYS_TRIGGER CLK_SEL=0); writing 0x80 would hang fusion
check(re.search(r'\(name "unconnected-\(U8-XIN32', NET) is not None,
      "no 32k crystal fitted (XIN32 NC)", "internal osc is mandatory")
check(re.search(r"imu_write\(0x3F,\s*0x00\)", INO) is not None,
      "fw selects the INTERNAL oscillator (SYS_TRIGGER=0x00)")
check(re.search(r"imu_write\(0x3D,\s*0x00\)", INO) is not None and
      re.search(r"imu_write\(0x3D,\s*0x0C\)", INO) is not None,
      "fw mode sequence CONFIG (0x3D=0x00) -> NDOF (0x3D=0x0C)")
check(re.search(r"imu_read16\(0x18\)\s*/\s*16\.0f", INO) is not None,
      "gyro-Z read: reg 0x18 (GYR_DATA_Z_LSB), 16 LSB/dps")
check(re.search(r"imu_read16\(0x1A\)\s*/\s*16\.0f", INO) is not None,
      "heading read: reg 0x1A (EUL_HEADING_LSB), 16 LSB/deg")
check("imu_selftest" in INO and "0xA0" in INO,
      "boot self-test present (CHIP_ID 0xA0 + POST result)",
      "prints + beeps if the IMU fails power-on self-test")

print("M4 motor connector rating + direct-plug pin order (rev 7.2, JST ZH)")
# ZH contacts are 1 A rated. The ORDERED motor (robu GA12-N20, spec sheet
# 2026-07-20) stalls at 0.23 A -- 4.3x inside the contact rating. A generic
# hot-wind N20 (1.6 A stall) would NOT be ZH-compatible: re-check here if the
# motor is ever changed.
ROBU_STALL_A, ZH_RATING_A = 0.23, 1.0
check(ROBU_STALL_A < ZH_RATING_A, "robu GA12-N20 stall within the ZH 1A contact rating",
      f"{ROBU_STALL_A} A stall < {ZH_RATING_A} A")
# and the ZH pin order must be the robu CABLE order, motor plug straight in
for conn, m_p, m_n, ea, eb in (("J5", "MOTA_P", "MOTA_N", "ENC1_A", "ENC1_B"),
                               ("J6", "MOTB_P", "MOTB_N", "ENC2_A", "ENC2_B")):
    order_ok = (f"{conn}.1" in nodes(m_p) and f"{conn}.2" in nodes("PLUS3V3")
                and f"{conn}.3" in nodes(ea) and f"{conn}.4" in nodes(eb)
                and f"{conn}.5" in nodes("GND") and f"{conn}.6" in nodes(m_n))
    check(order_ok, f"{conn} pin order = robu cable (M1,VCC,C1,C2,GND,M2)")

print("=" * 70)
if FAILS:
    print(f"PRE-FLIGHT: {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("PRE-FLIGHT: ALL CHECKS PASS -- flashing/sensor/motor killers cleared.")
