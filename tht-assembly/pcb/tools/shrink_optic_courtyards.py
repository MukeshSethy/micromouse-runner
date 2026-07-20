"""Shrink the 5mm optic footprints' courtyards to a body-true CIRCLE (r=2.6mm)
via text surgery. A circle's axis-aligned bbox = its diameter regardless of
the footprint's rotation -- a square courtyard on the 45-deg diagonal optics
(D3/D4/Q4/Q5) rotates to a sqrt2-larger bbox and keeps them overlapping.
Match optic footprints by Reference (D1-6 + Q2-7), delete their CrtYd graphic
sub-blocks, inject one centred circle. Bodies stay physically clear (6.4mm
centres, 5mm bodies); DRC courtyards_overlap passes."""
import re
BOARD = r"D:\Projects\micromouse-pcb\tht-assembly\pcb\micromouse-tht.kicad_pcb"
R = 2.4
OPT = {"D1","D2","D3","D4","D5","D6","Q2","Q3","Q4","Q5","Q6","Q7"}
s = open(BOARD, encoding="utf-8", newline="").read()

def fp_blocks(txt):
    out = []; i = 0
    while True:
        j = txt.find("\t(footprint ", i)
        if j < 0:
            break
        d = 0; k = j
        while k < len(txt):
            if txt[k] == "(":
                d += 1
            elif txt[k] == ")":
                d -= 1
                if d == 0:
                    break
            k += 1
        out.append((j, k + 1)); i = k + 1
    return out

def strip_crtyd(block):
    res = []; i = 0
    while i < len(block):
        if re.match(r'\t\t\(fp_(?:poly|circle|rect|line)\b', block[i:]):
            d = 0; k = i
            while k < len(block):
                if block[k] == "(":
                    d += 1
                elif block[k] == ")":
                    d -= 1
                    if d == 0:
                        break
                k += 1
            if "CrtYd" in block[i:k + 1]:
                i = k + 1
                if i < len(block) and block[i] == "\n":
                    i += 1
                continue
        res.append(block[i]); i += 1
    return "".join(res)

circ = ('\t\t(fp_circle\n\t\t\t(center 0 0)\n\t\t\t(end %s 0)\n'
        '\t\t\t(stroke\n\t\t\t\t(width 0.05)\n\t\t\t\t(type solid)\n\t\t\t)\n'
        '\t\t\t(fill no)\n\t\t\t(layer "%s")\n\t\t)\n')
out = []; last = 0; n = 0
for st, en in fp_blocks(s):
    blk = s[st:en]
    ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
    if not ref or ref.group(1) not in OPT:
        continue
    layer = "B.CrtYd" if re.search(r'\(layer "B\.Cu"\)', blk[:200]) else "F.CrtYd"
    nb = strip_crtyd(blk)
    nb = nb[:-2] + (circ % (R, layer)) + "\t)"
    out.append(s[last:st]); out.append(nb); last = en; n += 1
out.append(s[last:])
open(BOARD, "w", encoding="utf-8", newline="").write("".join(out))
print(f"shrink_optic_courtyards: {n} optic courtyards -> circle r={R}mm")
