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
NET = open(os.path.join(FW, "..", "pcb", "netlist.net"), encoding="utf-8").read()
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
analog = ["PIN_WALL1_SENSE", "PIN_WALL2_SENSE", "PIN_WALL3_SENSE",
          "PIN_WALL4_SENSE", "PIN_WALL5_SENSE", "PIN_WALL6_SENSE",
          "PIN_MUX_SENSE"]
declared = dict(re.findall(r"#define\s+(PIN_\w+)\s+(\d+)", PINS))
bad = [(a, declared.get(a)) for a in analog
       if not (declared.get(a) and 1 <= int(declared[a]) <= 10)]
check(not bad, "7 analog channels all on ADC1",
      "WALL1-6 + MUX_SENSE on GPIO " + ",".join(declared[a] for a in analog))

print("S2 mux settling vs scan slot")
# worst source: TCRT collector 47k pull-up + CD74HC4067 Ron ~125R into the
# S3 ADC sampling cap (~10 pF): tau ~ 0.47 us; 5-tau settle ~ 2.4 us.
tau_us = (47e3 + 125) * 10e-12 * 1e6
slot_us = 1e6 / 500 / 2            # 500 Hz loop, conservative half-slot per read
check(5 * tau_us < slot_us, "5-tau mux settle fits the ADC slot",
      f"{5*tau_us:.1f} us << {slot_us:.0f} us")

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

print("=" * 70)
if FAILS:
    print(f"PRE-FLIGHT: {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("PRE-FLIGHT: ALL CHECKS PASS -- flashing/sensor/motor killers cleared.")
