"""Tighten over-margined footprint courtyards to IPC-7351C "Least" excess.

WHY: the custom optical footprints (IR333-A / PT334-6B 5mm LEDs) and a few
R/Q parts in the dense front sensor cluster carry ~0.7mm courtyard margin.
That margin (not the copper) causes 22 of the 32 KiCad courtyard-overlap
errors (courtyards_overlap / *_inside_courtyard). Shrinking the courtyard to
the true keep-out (component body + pads + 0.13mm, IPC "Least") is a
standards-compliant fix that moves NO part and needs NO reroute.

This operates at the TEXT level (S-expression surgery) on purpose: the pcbnew
Python API's footprint child iterators (GraphicalItems/Pads) are intermittently
degraded ("SwigPyObject is not iterable") on this build, so a robust,
deterministic text pass is the reliable tool (project lore: prefer text-level
board surgery). Idempotent.

The 10 residual pth_inside_courtyard errors (wall-sensor pads ~0.27mm under the
opposite-side line-sensor BODY) are NOT courtyard-margin -- they are genuine
tight overlaps and are resolved by the rev-7 placement changes, not here.
See pcb/REQUIREMENTS.md MMSE-REM-1 / MMSE-REM-2.
"""
import re, sys

BOARD = r"D:\Projects\micromouse-pcb\pcb\micromouse-tht.kicad_pcb"
EXCESS = 0.13  # mm, IPC-7351C "Least"
# targets: optical parts (by value substring) + the flagged dense R/Q pairs (by ref)
OPT_VALUES = ("IR333", "PT334", "TCRT5000")
RQ_REFS = {"R41", "R42", "R47", "R48", "R49", "R50", "Q20", "Q27"}


def find_blocks(s):
    """Yield (start, end, text) for every top-level (footprint ...) block."""
    i = 0
    while True:
        p = s.find("(footprint ", i)
        if p < 0:
            return
        depth, q = 0, p
        while q < len(s):
            c = s[q]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            q += 1
        yield p, q + 1, s[p:q + 1]
        i = q + 1


def sub_blocks(b, token):
    """Yield (start,end,text) of each (token ...) s-expr inside b."""
    i = 0
    while True:
        p = b.find(token, i)
        if p < 0:
            return
        depth, q = 0, p
        while q < len(b):
            c = b[q]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            q += 1
        yield p, q + 1, b[p:q + 1]
        i = q + 1


def nums(txt, key):
    m = re.search(r"\(" + key + r"\s+(-?[\d.]+)\s+(-?[\d.]+)", txt)
    return (float(m.group(1)), float(m.group(2))) if m else None


def ref_of(b):
    m = re.search(r'\(property "Reference" "([^"]+)"', b)
    return m.group(1) if m else None


def value_of(b):
    m = re.search(r'\(property "Value" "([^"]*)"', b)
    return m.group(1) if m else ""


def keepout_bbox(b):
    """(x1,y1,x2,y2) union of Fab body + pad extents, footprint-local."""
    xs, ys = [], []
    for lay in ("F.Fab", "B.Fab"):
        for _, _, sh in list(sub_blocks(b, "(fp_circle")) + list(sub_blocks(b, "(fp_rect")) \
                + list(sub_blocks(b, "(fp_line")) + list(sub_blocks(b, "(fp_poly")):
            if f'(layer "{lay}")' not in sh:
                continue
            if sh.startswith("(fp_circle"):
                c = nums(sh, "center")
                e = nums(sh, "end")
                if c and e:
                    r = ((e[0] - c[0]) ** 2 + (e[1] - c[1]) ** 2) ** 0.5
                    xs += [c[0] - r, c[0] + r]
                    ys += [c[1] - r, c[1] + r]
            else:
                for pt in re.findall(r"\((?:start|end|xy)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", sh):
                    xs.append(float(pt[0]))
                    ys.append(float(pt[1]))
    for _, _, pad in sub_blocks(b, "(pad "):
        at = nums(pad, "at")
        sz = nums(pad, "size")
        if at and sz:
            xs += [at[0] - sz[0] / 2, at[0] + sz[0] / 2]
            ys += [at[1] - sz[1] / 2, at[1] + sz[1] / 2]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def main():
    s = open(BOARD, encoding="utf-8", newline="").read()
    out = []
    last = 0
    changed = 0
    for st, en, b in find_blocks(s):
        ref = ref_of(b)
        val = value_of(b)
        target = any(k in val for k in OPT_VALUES) or (ref in RQ_REFS)
        if not target:
            continue
        bb = keepout_bbox(b)
        if not bb:
            continue
        x1, y1, x2, y2 = bb
        nx1, ny1, nx2, ny2 = x1 - EXCESS, y1 - EXCESS, x2 + EXCESS, y2 + EXCESS
        # rewrite the CrtYd fp_rect(s) start/end in this block
        nb = b
        for layer in ("F.CrtYd", "B.CrtYd"):
            for ps, pe, sh in sub_blocks(nb, "(fp_rect"):
                if f'(layer "{layer}")' not in sh:
                    continue
                new = re.sub(r"\(start\s+-?[\d.]+\s+-?[\d.]+\)",
                             f"(start {nx1:.3f} {ny1:.3f})", sh, count=1)
                new = re.sub(r"\(end\s+-?[\d.]+\s+-?[\d.]+\)",
                             f"(end {nx2:.3f} {ny2:.3f})", new, count=1)
                nb = nb[:ps] + new + nb[pe:]
                changed += 1
                break  # one courtyard rect per footprint
        if nb != b:
            out.append(s[last:st])
            out.append(nb)
            last = en
    out.append(s[last:])
    open(BOARD, "w", encoding="utf-8", newline="").write("".join(out))
    print(f"tighten_courtyards: rewrote {changed} courtyard rects (excess {EXCESS}mm)")


if __name__ == "__main__":
    main()
