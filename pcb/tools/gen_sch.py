import uuid, sys, json, io

SYM_LIB_DIR = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"

import re

def extract_symbol_block(lib_name, symbol_name):
    path = f"{SYM_LIB_DIR}\\{lib_name}.kicad_sym"
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    marker = f'\t(symbol "{symbol_name}"'
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f"symbol {symbol_name!r} not found in {lib_name}")
    depth = 0
    i = idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                block = text[idx:i+1]
                lines = block.split("\n")
                out = []
                for ln in lines:
                    if ln.startswith("\t"):
                        out.append(ln[1:])
                    else:
                        out.append(ln)
                block = "\n".join(out)
                # ONLY the top-level symbol name is fully qualified as
                # "LibName:SymbolName" in an embedded lib_symbols cache.
                # Nested sub-unit symbols (e.g. "R_0_1", "R_1_1") keep their
                # bare name, unprefixed -- confirmed against a real KiCad-
                # written schematic (power:+5V's sub-units are "+5V_0_1" /
                # "+5V_1_1", NOT "power:+5V_0_1"). Prefixing them breaks load.
                block = re.sub(
                    rf'^(\t*)\(symbol "{re.escape(symbol_name)}"',
                    lambda m: f'{m.group(1)}(symbol "{lib_name}:{symbol_name}"',
                    block,
                    count=1,
                    flags=re.MULTILINE,
                )
                block = re.sub(
                    # hyphens/dots are legal in symbol names (USBLC6-2P6 bit us:
                    # the old [A-Za-z0-9_]+ silently skipped the rewrite and the
                    # derived symbol resolved to nothing -- no pins, dangling labels)
                    r'\(extends "([A-Za-z0-9_.-]+)"\)',
                    lambda m: f'(extends "{lib_name}:{m.group(1)}")',
                    block,
                )
                return block
        i += 1
    raise ValueError("unbalanced parens")

def new_uuid():
    return str(uuid.uuid4())

GRID = 1.27
def snap(at):
    x, y = at
    return (round(round(x / GRID) * GRID, 4), round(round(y / GRID) * GRID, 4))

def pin_at(base, local_offset):
    # Empirically confirmed against kicad-cli ERC ground truth (unconnected-pin
    # positions) on Conn_01x03 and Q_PMOS: at rotation 0, a symbol instance's
    # absolute pin position is (base_x + local_x, base_y - local_y) -- KiCad
    # NEGATES the library-defined local Y offset. X is applied as-is. Getting
    # this wrong doesn't always show up as "dangling" in ERC (it can silently
    # land on a *different real pin* instead), so always go through this
    # helper for pin-derived label positions rather than raw base+offset math.
    bx, by = base
    lx, ly = local_offset
    return (round(bx + lx, 4), round(by - ly, 4))

def indent(text, levels):
    pad = "\t" * levels
    return "\n".join(pad + ln if ln.strip() else ln for ln in text.split("\n"))

class SchGen:
    def __init__(self, project_name, paper="A2"):
        self.project_name = project_name
        self.paper = paper
        self.root_uuid = new_uuid()
        self.lib_symbols_needed = {}   # lib_id -> verbatim block text (already re-indented by 1)
        self.symbol_instances = []     # list of rendered instance strings
        self.label_instances = []
        self.junctions = []
        self.no_connects = []
        self.pwr_counter = 0
        self.texts = []
        self.wires = []

    def need_lib_symbol(self, lib_name, symbol_name, extra_extends=None):
        lib_id = f"{lib_name}:{symbol_name}"
        # base ("extends") symbol must be inserted BEFORE the symbol that
        # extends it -- KiCad resolves lib_symbols in file order and fails
        # to load if a forward reference to an as-yet-undefined base occurs.
        if extra_extends:
            base_lib_id = f"{lib_name}:{extra_extends}"
            if base_lib_id not in self.lib_symbols_needed:
                block = extract_symbol_block(lib_name, extra_extends)
                self.lib_symbols_needed[base_lib_id] = block
        if lib_id not in self.lib_symbols_needed:
            block = extract_symbol_block(lib_name, symbol_name)
            self.lib_symbols_needed[lib_id] = block
        return lib_id

    def add_component(self, lib_name, symbol_name, ref, value, at, pin_offsets,
                       footprint="", extends=None, ref_offset=(0,5.08), value_offset=(0,-5.08),
                       hide_ref_value=False, datasheet=""):
        at = snap(at)
        lib_id = self.need_lib_symbol(lib_name, symbol_name, extra_extends=extends)
        x, y = at
        sym_uuid = new_uuid()
        ref_x, ref_y = x+ref_offset[0], y+ref_offset[1]
        val_x, val_y = x+value_offset[0], y+value_offset[1]
        hide = " (hide yes)" if hide_ref_value else ""
        s = []
        s.append(f'(symbol\n\t(lib_id "{lib_id}")\n\t(at {x} {y} 0)\n\t(unit 1)')
        s.append('\t(exclude_from_sim no)\n\t(in_bom yes)\n\t(on_board yes)\n\t(dnp no)\n\t(fields_autoplaced yes)')
        s.append(f'\t(uuid "{sym_uuid}")')
        s.append(f'\t(property "Reference" "{ref}"\n\t\t(at {ref_x} {ref_y} 0)\n\t\t(effects (font (size 1.27 1.27)){hide})\n\t)')
        s.append(f'\t(property "Value" "{value}"\n\t\t(at {val_x} {val_y} 0)\n\t\t(effects (font (size 1.27 1.27)){hide})\n\t)')
        s.append(f'\t(property "Footprint" "{footprint}"\n\t\t(at {x} {y} 0)\n\t\t(effects (font (size 1.27 1.27)) (hide yes))\n\t)')
        s.append(f'\t(property "Datasheet" "{datasheet}"\n\t\t(at {x} {y} 0)\n\t\t(effects (font (size 1.27 1.27)) (hide yes))\n\t)')
        # Extra BOM fields (MPN, Manufacturer, ...): an optional provider
        # callable set by the build script maps (ref, value, footprint) to a
        # dict of extra hidden properties -- keeps part-number policy in
        # build_schematic.py, not here.
        extra = getattr(self, "field_provider", None)
        if extra:
            for fname, fval in (extra(ref, value, footprint) or {}).items():
                s.append(f'\t(property "{fname}" "{fval}"\n\t\t(at {x} {y} 0)\n\t\t(effects (font (size 1.27 1.27)) (hide yes))\n\t)')
        for pin_num, net in pin_offsets.items():
            s.append(f'\t(pin "{pin_num}" (uuid "{new_uuid()}"))')
        s.append(f'\t(instances\n\t\t(project "{self.project_name}"\n\t\t\t(path "/{self.root_uuid}"\n\t\t\t\t(reference "{ref}")\n\t\t\t\t(unit 1)\n\t\t\t)\n\t\t)\n\t)')
        s.append(')')
        self.symbol_instances.append("\n".join(s))
        return sym_uuid

    def add_power_symbol(self, symbol_name, at, ref_prefix="#PWR"):
        at = snap(at)
        lib_id = self.need_lib_symbol("power", symbol_name)
        x, y = at
        self.pwr_counter += 1
        ref = f"{ref_prefix}{self.pwr_counter:03d}"
        sym_uuid = new_uuid()
        s = []
        s.append(f'(symbol\n\t(lib_id "{lib_id}")\n\t(at {x} {y} 0)\n\t(unit 1)')
        s.append('\t(exclude_from_sim no)\n\t(in_bom yes)\n\t(on_board yes)\n\t(dnp no)\n\t(fields_autoplaced yes)')
        s.append(f'\t(uuid "{sym_uuid}")')
        s.append(f'\t(property "Reference" "{ref}"\n\t\t(at {x} {y-2.54} 0)\n\t\t(effects (font (size 1.27 1.27)) (hide yes))\n\t)')
        s.append(f'\t(property "Value" "{symbol_name}"\n\t\t(at {x} {y-4} 0)\n\t\t(effects (font (size 1.27 1.27)))\n\t)')
        s.append(f'\t(property "Footprint" ""\n\t\t(at {x} {y} 0)\n\t\t(effects (font (size 1.27 1.27)) (hide yes))\n\t)')
        s.append(f'\t(property "Datasheet" ""\n\t\t(at {x} {y} 0)\n\t\t(effects (font (size 1.27 1.27)) (hide yes))\n\t)')
        s.append(f'\t(pin "1" (uuid "{new_uuid()}"))')
        s.append(f'\t(instances\n\t\t(project "{self.project_name}"\n\t\t\t(path "/{self.root_uuid}"\n\t\t\t\t(reference "{ref}")\n\t\t\t\t(unit 1)\n\t\t\t)\n\t\t)\n\t)')
        s.append(')')
        self.symbol_instances.append("\n".join(s))
        return sym_uuid

    def add_wire(self, p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        s = (f'(wire\n\t(pts\n\t\t(xy {x1} {y1}) (xy {x2} {y2})\n\t)\n'
             f'\t(stroke\n\t\t(width 0)\n\t\t(type default)\n\t)\n'
             f'\t(uuid "{new_uuid()}")\n)')
        self.wires.append(s)

    def add_label(self, text, at, shape="passive", rotation=0, stub=0):
        # `at` must always be the exact electrical point (a real pin position).
        # `stub`, if given, draws a short wire from that point out to where the
        # label text is actually placed, so the label doesn't sit flush on top
        # of the component body -- purely cosmetic, connectivity is unchanged
        # since the wire's near end is still exactly on the pin. CAUTION: a
        # stub introduces a new wire endpoint (the label side) which, same as
        # connect()'s bend points, must not coincide with an unrelated real
        # pin -- verify with a netlist export if you enable this broadly.
        x, y = at
        if stub:
            dx, dy = {0: (1, 0), 180: (-1, 0), 90: (0, -1), 270: (0, 1)}[rotation]
            lx, ly = round(x + dx*stub, 4), round(y + dy*stub, 4)
            self.add_wire((x, y), (lx, ly))
        else:
            lx, ly = x, y
        lbl_uuid = new_uuid()
        s = (f'(global_label "{text}"\n\t(shape {shape})\n\t(at {lx} {ly} {rotation})\n'
             f'\t(fields_autoplaced yes)\n\t(effects (font (size 1.27 1.27)) (justify left))\n'
             f'\t(uuid "{lbl_uuid}")\n'
             f'\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"\n\t\t(at {lx} {ly+2.5} {rotation})\n\t\t(effects (font (size 1.27 1.27)) (hide yes))\n\t)\n)')
        self.label_instances.append(s)
        return lbl_uuid

    def connect(self, p1, p2):
        # Direct point-to-point wire between two exact pin positions (for
        # local, 2-endpoint nets) -- clearer than two labels sitting near
        # each other, and standard schematic style for adjacent components.
        #
        # BUG HISTORY: an early version used a simple L-shape with the bend
        # at (x2, y1). In a tidy layout where many components share a common
        # baseline Y (very common -- that's what "tidy" means), that bend
        # point can land EXACTLY on a real, unrelated pin (e.g. two parts
        # placed on the same row, both with a symmetric +/-Y pin offset --
        # the bend reuses one part's X and the other part's Y, which is
        # exactly that other part's actual pin position). That silently
        # merges two unrelated nets with no ERC error pointing at it. Route
        # through the horizontal midpoint instead -- an arbitrary average of
        # two placements, never itself a placement anyone uses, so it can't
        # coincide with a real pin.
        x1, y1 = p1
        x2, y2 = p2
        if x1 == x2 or y1 == y2:
            self.add_wire(p1, p2)
        else:
            midx = snap(((x1 + x2) / 2, 0))[0]  # grid-snap so bend points don't
            c1 = (midx, y1)                      # trip "endpoint off grid" ERC
            c2 = (midx, y2)
            self.add_wire(p1, c1)
            self.add_wire(c1, c2)
            self.add_wire(c2, p2)

    def add_no_connect(self, at):
        x, y = at
        s = f'(no_connect\n\t(at {x} {y})\n\t(uuid "{new_uuid()}")\n)'
        self.no_connects.append(s)

    def add_text(self, text, at, size=2.0):
        x, y = at
        # embedded newlines must be the literal two chars "\n" inside the
        # quoted string, not a raw newline byte -- a raw one breaks the parser.
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        s = (f'(text "{escaped}"\n\t(at {x} {y} 0)\n\t(effects (font (size {size} {size})))\n'
             f'\t(uuid "{new_uuid()}")\n)')
        self.texts.append(s)

    def render(self, title="Micromouse PCB"):
        lib_syms = "\n".join(indent(b, 1) for b in self.lib_symbols_needed.values())
        out = []
        out.append("(kicad_sch")
        out.append("\t(version 20260306)")
        out.append('\t(generator "eeschema")')
        out.append('\t(generator_version "10.0")')
        out.append(f'\t(uuid "{self.root_uuid}")')
        out.append(f'\t(paper "{self.paper}")')
        out.append(f'\t(title_block\n\t\t(title "{title}")\n\t)')
        out.append(f"\t(lib_symbols\n{lib_syms}\n\t)")
        for block in self.texts:
            out.append(indent(block, 1))
        for block in self.wires:
            out.append(indent(block, 1))
        for block in self.symbol_instances:
            out.append(indent(block, 1))
        for block in self.label_instances:
            out.append(indent(block, 1))
        for block in self.no_connects:
            out.append(indent(block, 1))
        out.append('\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)')
        out.append(")")
        return "\n".join(out) + "\n"
