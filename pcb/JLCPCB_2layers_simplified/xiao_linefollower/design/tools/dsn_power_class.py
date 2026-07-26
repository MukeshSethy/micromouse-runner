"""Post-process the exported DSN: pull the power rails out of kicad_default and
give them their own classes with IPC-2152-adequate widths, so Freerouting
routes them wide from the start.

  power    (BATT_RAW VM_BATT VM_6V SW_6V) -> width 500um
  power3v3 (PLUS3V3)                      -> width 400um

The class block layout KiCad exports is:
  (class kicad_default NET NET ...
    (circuit (use_via ...))
    (rule (width 200) (clearance 150.1))
  )
"""
import re, sys

DSN = r"D:\Projects\micromouse-pcb\pcb\JLCPCB_2layers\design\micromouse-pcb.dsn"
POWER = ["BATT_RAW", "VM_BATT", "VM_6V", "SW_6V"]
POWER3 = ["PLUS3V3"]

s = open(DSN, encoding="utf-8").read()

# find the kicad_default class block (balanced-paren scan from its '(')
i = s.index("(class kicad_default")
depth = 0
j = i
while True:
    if s[j] == "(":
        depth += 1
    elif s[j] == ")":
        depth -= 1
        if depth == 0:
            break
    j += 1
block = s[i:j + 1]

# split the block into header (net list) and the inner (circuit)/(rule) parts
inner_at = block.index("(circuit")
header, inner = block[:inner_at], block[inner_at:-1]   # inner keeps circuit+rule

# remove power nets from the default header
for net in POWER + POWER3:
    header = re.sub(r'(?<=[\s])%s(?=[\s])' % re.escape(net), " ", header)
header = re.sub(r"[ \t]+", " ", header)

new_default = header + "\n      " + inner.strip() + "\n    )"

def mkclass(name, nets, width):
    rule_inner = re.sub(r"\(width [0-9.]+\)", "(width %d)" % width, inner.strip())
    return ("(class %s %s\n      %s\n    )" % (name, " ".join(nets), rule_inner))

replacement = (new_default + "\n    " + mkclass("power", POWER, 500)
               + "\n    " + mkclass("power3v3", POWER3, 400))
s = s[:i] + replacement + s[j + 1:]
open(DSN, "w", encoding="utf-8", newline="\n").write(s)

# verify
chk = open(DSN, encoding="utf-8").read()
ok_p = re.search(r"\(class power BATT_RAW VM_BATT VM_6V SW_6V.*?\(width 500\)", chk, re.S)
ok_3 = re.search(r"\(class power3v3 PLUS3V3.*?\(width 400\)", chk, re.S)
gone = not re.search(r"class kicad_default[^(]*\bBATT_RAW\b", chk, re.S)
print("power class (500um):", bool(ok_p))
print("power3v3 class (400um):", bool(ok_3))
print("power nets removed from default:", gone)
sys.exit(0 if (ok_p and ok_3 and gone) else 1)
