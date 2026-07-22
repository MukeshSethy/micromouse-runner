"""Build the JLCPCB production folder in JLC's EXACT upload formats (matched to
the user's JLCSMT sample files), ready to upload directly.

JLC's **Standard PCBA** assembles BOTH surface-mount AND through-hole parts
(reflow for SMD, then wave/selective/hand-solder for THT) -- so the whole board
is turnkey, no hand-soldering, provided every part is in JLC's library (all of
ours are; C-numbers are in jlcpcb_lcsc_map.py). Only the cheaper Economy PCBA
tier is SMD-only. So we emit ONE combined BOM + ONE combined CPL covering every
part:

  jlcpcb/micromouse-pcb-2layer-jlcpcb-gerbers.zip  fab (Gerber X2 + Excellon)
  jlcpcb/BOM_JLC-assembly.xlsx   full assembly BOM, columns EXACTLY:
        Comment | Designator | Footprint | JLCPCB Part #（optional）
  jlcpcb/CPL_JLC-assembly.xlsx   full placement, columns EXACTLY:
        Designator | Mid X | Mid Y | Layer | Rotation
  jlcpcb/THT_parts_reference.csv  which BOM lines are through-hole (info only:
        so you can see the THT-assembly cost delta, or deselect them in JLC's
        tool if you'd rather run Economy PCBA + self-solder)
  jlcpcb/ORDERING.md              tier choice, swaps, rotation/coord caveats

Coordinate frame: the placement data and the KiCad gerbers share one frame
(outline X[0,100] Y[-120,0] mm, Y-up so the board sits below the origin;
parts fall inside it) -- do NOT "normalise" Y to positive.

CPL source: placement comes from `gen_jlc_positions.py` (run via KiCad's
bundled Python, which alone has pcbnew), NOT kicad-cli's raw `pcb export pos`.
kicad-cli reports each footprint's KiCad *anchor*, which for many THT parts
(switches, LEDs, connectors) is not the physical body center JLC's
pick-and-place needs; and KiCad's raw rotation is the mirrored, as-drawn
value for bottom-side parts, not JLC's "as viewed from above" convention.
gen_jlc_positions.py corrects both, plus known KiCad-vs-JLC package rotation
mismatches (SOT-23 family, SSOP, electrolytic caps) -- see its module
docstring for the full reasoning and how each correction was verified
against this board's own footprint geometry.

Same rev-7.2 board as the Lion package: every LCSC choice is footprint- and
value-compatible, so gerbers + placement are unchanged; only BOM part #s differ
(passives -> JLC Basic equivalents to kill per-part setup fees).
"""
import csv
import os
import re
import zipfile

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FAB = os.path.join(BASE, "fab")
OUT = os.path.join(BASE, "fab_release", "jlcpcb")


def _load_map():
    from jlcpcb_lcsc_map import LCSC_MAP
    return LCSC_MAP


# ----------------------------------------------------------------- xlsx writer
_XML = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def _esc(s):
    return "".join(_XML.get(c, c) for c in str(s))


def _col(i):  # 0->A 1->B ...
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, rows):
    """rows: list of lists; row 0 is the header. Cells written as inline
    strings (JLC parses them fine, incl. '95.05mm' and '270')."""
    sheet = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for r, row in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{_col(c)}{r}" t="inlineStr"><is><t xml:space="preserve">{_esc(v)}</t></is></c>'
            for c, v in enumerate(row))
        sheet.append(f'<row r="{r}">{cells}</row>')
    sheet.append("</sheetData></worksheet>")
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        "xl/worksheets/sheet1.xml": "".join(sheet),
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)


# --------------------------------------------------------------- ref expansion
def expand_refs(s):
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok:
            a, b = tok.split("-", 1)
            ma = re.match(r"([A-Za-z]+)(\d+)", a)
            mb = re.match(r"([A-Za-z]*)(\d+)", b)
            if ma and mb:
                pref, lo, hi = ma.group(1), int(ma.group(2)), int(mb.group(2))
                out += [f"{pref}{n}" for n in range(lo, hi + 1)]
                continue
        out.append(tok)
    return out


def clean_comment(value, mpn):
    c = (value or "").split("(")[0].strip()
    return (c or mpn)[:40]


def short_fp(fp):
    return (fp or "").rsplit(":", 1)[-1]


def rot_fmt(v):
    try:
        f = float(v) % 360.0          # JLC CPL convention is [0,360): -45 -> 315
        return str(int(round(f))) if abs(f - round(f)) < 1e-6 else f"{f:g}"
    except ValueError:
        return v


def num_fmt(v):
    try:
        return f"{float(v):.4f}".rstrip("0").rstrip(".")
    except ValueError:
        return v


def main():
    LCSC_MAP = _load_map()
    os.makedirs(OUT, exist_ok=True)
    # clean stale outputs (older SMT-only and blank-LCSC exports)
    for f in ("bom_jlcpcb.csv", "cpl_jlcpcb.csv", "micromouse-pcb-rev7.2-jlcpcb.zip",
              "BOM_JLCPCB.csv", "CPL_JLCPCB.csv", "micromouse-pcb-jlcpcb-gerbers.zip",
              "BOM_JLCSMT.xlsx", "CPL_JLCSMT.xlsx", "THT_hand-solder_parts.csv"):
        p = os.path.join(OUT, f)
        if os.path.exists(p):
            os.remove(p)

    # ---- gerber + drill zip (flat) -----------------------------------------
    zpath = os.path.join(OUT, "micromouse-pcb-2layer-jlcpcb-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in os.listdir(os.path.join(FAB, "gerbers")):
            z.write(os.path.join(FAB, "gerbers", f), f)
        for f in os.listdir(os.path.join(FAB, "drill")):
            if f.endswith(".drl"):
                z.write(os.path.join(FAB, "drill", f), f)

    # ---- read BOM (ALL parts -> one assembly BOM for Standard PCBA) ---------
    bom = list(csv.DictReader(open(os.path.join(BASE, "BOM.csv"),
                                   newline="", encoding="utf-8-sig")))
    all_refs = set()
    bom_rows, tht_ref_rows, missing = [], [], []
    for r in bom:
        mpn = r["MPN"].strip()
        m = LCSC_MAP.get(mpn)
        if not m or not m["lcsc"]:
            missing.append(mpn)
        lcsc = m["lcsc"] if m else ""
        is_smt = m["smt"] if m else True
        # JLC wants EXPLICIT comma-separated designators, not KiCad ranges
        # (e.g. "C12,C13,C14,C15" not "C12-C15"); a range string hard-fails
        # its BOM parser and desyncs from the per-part CPL.
        refs = expand_refs(r["Reference"])
        designators = ",".join(refs)
        bom_rows.append([clean_comment(r["Value"], mpn), designators, short_fp(r["Footprint"]), lcsc])
        all_refs.update(refs)
        if not is_smt:
            tht_ref_rows.append([designators, clean_comment(r["Value"], mpn),
                                 short_fp(r["Footprint"]), lcsc, m["part"] if m else mpn, str(r["Qty"])])

    bom_table = [["Comment", "Designator", "Footprint", "JLCPCB Part #（optional）"]] + bom_rows
    write_xlsx(os.path.join(OUT, "BOM_JLC-assembly.xlsx"), bom_table)
    # CSV twin (JLC accepts csv; robust against xlsx-parser quirks). ASCII
    # header for the LCSC column -- JLC matches "LCSC Part #" too.
    with open(os.path.join(OUT, "BOM_JLC-assembly.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writerows(bom_rows)

    # ---- CPL (ALL placements for BOM parts) --------------------------------
    jlc_pos_path = os.path.join(FAB, "micromouse-pcb.jlc-positions.csv")
    if not os.path.exists(jlc_pos_path):
        raise SystemExit(
            "missing " + jlc_pos_path + " -- run gen_jlc_positions.py first, "
            'with KiCad\'s bundled Python: "C:\\Program Files\\KiCad\\10.0\\'
            'bin\\python.exe" gen_jlc_positions.py')
    pos = list(csv.DictReader(open(jlc_pos_path, newline="", encoding="utf-8-sig")))
    cpl = [["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]]
    placed = 0
    for r in pos:
        if r["Ref"] not in all_refs:
            continue  # non-BOM mechanical (mount holes, fiducials) -- JLC skips
        side = "Top" if r["Side"].lower().startswith("t") else "Bottom"
        cpl.append([r["Ref"], f'{num_fmt(r["PosX"])}mm', f'{num_fmt(r["PosY"])}mm',
                    side, rot_fmt(r["Rot"])])
        placed += 1
    write_xlsx(os.path.join(OUT, "CPL_JLC-assembly.xlsx"), cpl)
    with open(os.path.join(OUT, "CPL_JLC-assembly.csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(cpl)

    # ---- THT reference (info only) -----------------------------------------
    with open(os.path.join(OUT, "THT_parts_reference.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Comment", "Footprint", "LCSC Part #", "Order MPN", "Qty"])
        w.writerows(tht_ref_rows)

    tht_lines = len(tht_ref_rows)
    print(f"BOM lines: {len(bom_rows)} ({tht_lines} THT) | CPL placements: {placed}")
    if missing:
        print(f"NO LCSC for {len(missing)}: {sorted(set(missing))}")
    else:
        print("every BOM MPN has a JLCPCB/LCSC part")
    print("jlcpcb folder:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
