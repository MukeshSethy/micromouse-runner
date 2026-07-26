"""Build the Lion Circuits production folder, sibling to export_jlcpcb.py's
JLCPCB folder -- same underlying design (same BOM.csv, same corrected
positions logic), reformatted to Lion Circuits' own documented upload
requirements (lioncircuits.com/faq/pcb-assembly/..., checked 2026-07-21):

  lioncircuits/micromouse-pcb-2layer-gerbers.zip   fab (RS-274X + Excellon,
        same files as the JLC zip -- Lion's stated Gerber/drill format
        matches JLCPCB's, no divergence found)
  lioncircuits/BOM_Lion.xlsx   columns EXACTLY:
        Item Description | Manufacturer Part Number | Name | Package | Designator | Quantity
  lioncircuits/CPL_Lion.xlsx   columns EXACTLY:
        Designator | X Data | Y Data | Layer | Rotation

Unlike the JLC folder, this BOM uses the design's OWN canonical MPN/
Manufacturer directly -- no per-vendor substitute-part mapping layer, because
Lion Circuits' BOM is keyed by manufacturer part number (their own docs), and
after the 2026-07-21 dual-vendor audit every BOM line's canonical MPN is
either confirmed common to both vendors, or (for the ~5 flagged passives)
already the real part Lion stocks -- JLCPCB is the one substituting to its
own Basic-tier equivalents for those, via jlcpcb_lcsc_map.py.

KNOWN EXCEPTION (flag for user review): XT60-M (J10) shows "Out of Stock" on
Lion Circuits specifically (still orderable, same quoted lead time as their
in-stock parts) -- no clean same-footprint alternate exists at both vendors.
Left as-is; J10 is a redundant/parallel battery-input option to J1 in this
design.
"""
import csv
import os
import zipfile

from export_jlcpcb import write_xlsx, expand_refs, clean_comment, short_fp, rot_fmt, num_fmt

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FAB = os.path.join(BASE, "fab")
OUT = os.path.join(BASE, "fab_release", "lioncircuits")


def main():
    os.makedirs(OUT, exist_ok=True)

    # ---- gerber + drill zip (identical fab data to the JLC package; Lion's
    #      stated Gerber=RS-274X/drill=Excellon requirements match) ---------
    zpath = os.path.join(OUT, "micromouse-pcb-simplified-2layer-lion-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in os.listdir(os.path.join(FAB, "gerbers")):
            z.write(os.path.join(FAB, "gerbers", f), f)
        for f in os.listdir(os.path.join(FAB, "drill")):
            if f.endswith(".drl"):
                z.write(os.path.join(FAB, "drill", f), f)

    # ---- BOM: canonical MPN/Manufacturer, no per-vendor substitution -------
    bom = list(csv.DictReader(open(os.path.join(BASE, "BOM.csv"),
                                   newline="", encoding="utf-8-sig")))
    all_refs = set()
    bom_rows = []
    for r in bom:
        refs = expand_refs(r["Reference"])
        designators = ",".join(refs)
        comment = clean_comment(r["Value"], r["MPN"].strip())
        bom_rows.append([r["Value"], r["MPN"].strip(), comment,
                          short_fp(r["Footprint"]), designators, str(r["Qty"])])
        all_refs.update(refs)

    bom_table = [["Item Description", "Manufacturer Part Number", "Name",
                  "Package", "Designator", "Quantity"]] + bom_rows
    write_xlsx(os.path.join(OUT, "BOM_Lion.xlsx"), bom_table)
    with open(os.path.join(OUT, "BOM_Lion.csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(bom_table)

    # ---- CPL (Lion's own centroid-file column order/rotation convention) --
    lion_pos_path = os.path.join(FAB, "micromouse-pcb-simplified.lion-positions.csv")
    if not os.path.exists(lion_pos_path):
        raise SystemExit(
            "missing " + lion_pos_path + " -- run gen_lion_positions.py first, "
            'with KiCad\'s bundled Python: "C:\\Program Files\\KiCad\\10.0\\'
            'bin\\python.exe" gen_lion_positions.py')
    pos = list(csv.DictReader(open(lion_pos_path, newline="", encoding="utf-8-sig")))
    cpl = [["Designator", "X Data", "Y Data", "Layer", "Rotation"]]
    placed = 0
    for r in pos:
        if r["Designator"] not in all_refs:
            continue
        cpl.append([r["Designator"], f'{num_fmt(r["X Data"])}mm',
                    f'{num_fmt(r["Y Data"])}mm', r["Layer"], rot_fmt(r["Rotation"])])
        placed += 1
    write_xlsx(os.path.join(OUT, "CPL_Lion.xlsx"), cpl)
    with open(os.path.join(OUT, "CPL_Lion.csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(cpl)

    print(f"BOM lines: {len(bom_rows)} | CPL placements: {placed}")
    print("lioncircuits folder:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
