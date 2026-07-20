"""Sync board footprint metadata to the schematic so KiCad's schematic-parity
check is clean (0 issues). Rev 6 surfaced 376 parity items -- ALL metadata,
no connectivity:

  footprint_symbol_mismatch (199)   board FPID stored bare ("C_0805_2012Metric")
                                    vs the symbol's full id ("Capacitor_SMD:...")
  footprint_symbol_field_mismatch   board footprints carry no MPN/Manufacturer
        (175)                       fields; the symbols do
  extra_footprint (2)               MOT1/MOT2 motor bodies are board-only
                                    (added by build_pcb, no schematic symbol)

Text-level (S-expression walk; no pcbnew/SWIG). Idempotent -- skips a
footprint already carrying a lib-qualified FPID + its MPN. Reads the exact
FPID + fields from pcb/netlist.net (the schematic's own export).
"""
import re
import uuid

BOARD = r"D:\Projects\micromouse-pcb\pcb\micromouse-pcb.kicad_pcb"
NETLIST = r"D:\Projects\micromouse-pcb\pcb\netlist.net"

# ref -> {fpid, value, mpn, mfr, datasheet} from the netlist (the schematic's
# own export -- the single source of truth)
net = open(NETLIST, encoding="utf-8").read()
meta = {}
for m in re.finditer(r'\(comp\s*\(ref "([^"]+)"\)(.*?)\n\t\t\)', net, re.S):
    ref, body = m.group(1), m.group(2)
    fp = re.search(r'\(footprint "([^"]+)"\)', body)
    val = re.search(r'\(value "([^"]*)"\)', body)
    mpn = re.search(r'\(name "MPN"\)\s*"([^"]*)"', body)
    mfr = re.search(r'\(name "Manufacturer"\)\s*"([^"]*)"', body)
    # Datasheet: a comp-level (datasheet "...") or a field; "" / "~" means none
    ds = re.search(r'\(datasheet "([^"]*)"\)', body)
    dsv = ds.group(1) if ds else ""
    if dsv == "~":
        dsv = ""
    meta[ref] = {"fpid": fp.group(1) if fp else None,
                 "value": val.group(1) if val else None,
                 "mpn": mpn.group(1) if mpn else None,
                 "mfr": mfr.group(1) if mfr else None,
                 "datasheet": dsv}

s = open(BOARD, encoding="utf-8", newline="").read()
out = []
i = 0
n = len(s)
patched_fpid = patched_field = patched_val = patched_ds = board_only = 0


def prop_block(name, value, uid):
    return (f'\t\t(property "{name}" "{value}"\n'
            f'\t\t\t(at 0 0 0)\n\t\t\t(unlocked yes)\n\t\t\t(layer "F.Fab")\n'
            f'\t\t\t(hide yes)\n\t\t\t(uuid "{uid}")\n'
            f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1 1)\n'
            f'\t\t\t\t\t(thickness 0.15)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')


while i < n:
    j = s.find("\t(footprint ", i)
    if j == -1:
        out.append(s[i:])
        break
    out.append(s[i:j])
    # block end by paren balance
    depth = 0
    e = j
    while e < n:
        if s[e] == "(":
            depth += 1
        elif s[e] == ")":
            depth -= 1
            if depth == 0:
                e += 1
                break
        e += 1
    block = s[j:e]

    ref_m = re.search(r'\(property "Reference" "([^"]+)"', block)
    ref = ref_m.group(1) if ref_m else None
    md = meta.get(ref, {})
    fpid, mpn, mfr = md.get("fpid"), md.get("mpn"), md.get("mfr")
    value, datasheet = md.get("value"), md.get("datasheet")

    # 1. full FPID: `(footprint "NAME"` -> `(footprint "LIB:NAME"` when bare
    name_m = re.match(r'\t\(footprint "([^"]+)"', block)
    if name_m and ":" not in name_m.group(1) and fpid and ":" in fpid:
        block = block.replace(f'\t(footprint "{name_m.group(1)}"',
                              f'\t(footprint "{fpid}"', 1)
        patched_fpid += 1

    # 2. Value: library-default footprints carry the FOOTPRINT NAME as Value;
    #    set it to the netlist component value.
    if value is not None:
        vm = re.search(r'(\(property "Value" ")([^"]*)(")', block)
        if vm and vm.group(2) != value:
            block = block[:vm.start(2)] + value + block[vm.end(2):]
            patched_val += 1

    # 3. Datasheet property: set to the netlist value (add if absent)
    dm = re.search(r'(\(property "Datasheet" ")([^"]*)(")', block)
    if dm:
        if dm.group(2) != (datasheet or ""):
            block = block[:dm.start(2)] + (datasheet or "") + block[dm.end(2):]
            patched_ds += 1
    elif datasheet:
        vm2 = re.search(r'(\(property "Value".*?\n\t\t\))', block, re.S)
        if vm2:
            block = (block[:vm2.end()] + "\n"
                     + prop_block("Datasheet", datasheet, uuid.uuid4()).rstrip("\n")
                     + block[vm2.end():])
            patched_ds += 1

    # 4. MPN + Manufacturer fields (after the Value property) if absent
    if mpn and '(property "MPN"' not in block:
        vm = re.search(r'(\(property "Value".*?\n\t\t\))', block, re.S)
        if vm:
            add = prop_block("MPN", mpn, uuid.uuid4())
            if mfr:
                add += prop_block("Manufacturer", mfr, uuid.uuid4())
            block = block[:vm.end()] + "\n" + add.rstrip("\n") + block[vm.end():]
            patched_field += 1

    # 3. MOT1/MOT2: board-only so parity ignores them
    if ref in ("MOT1", "MOT2") and "board_only" not in block:
        am = re.search(r'(\t\t\(attr\s+)([^\n]*)\)', block)
        if am:
            block = block[:am.start()] + f'\t\t(attr {am.group(2)} board_only exclude_from_bom)' + block[am.end():]
        else:
            # insert an attr line after the tags/descr near the top
            hm = re.search(r'(\(uuid "[^"]+"\)\n)', block)
            if hm:
                block = block[:hm.end()] + '\t\t(attr board_only exclude_from_bom)\n' + block[hm.end():]
        board_only += 1

    out.append(block)
    i = e

open(BOARD, "w", encoding="utf-8", newline="").write("".join(out))
print(f"sync_board_meta: {patched_fpid} FPIDs qualified, {patched_val} values, "
      f"{patched_ds} datasheets, {patched_field} MPN/Mfr blocks, "
      f"{board_only} motor bodies -> board_only")
