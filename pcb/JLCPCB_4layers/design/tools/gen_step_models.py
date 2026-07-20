"""Generates project-local 3D models so `kicad-cli pcb export step` covers
EVERY part (the rev-5 audit found the exported STEP silently omitted both N20
motors -- VRML-only -- and U1/L1, whose library .step files don't exist in
the KiCad install at all).

Emits hand-authored AP214 STEP solids built purely from axis-aligned boxes --
crude but dimensionally true, which is all a chassis/bracket/wheel fit check
needs:
  pcb/n20.3dshapes/N20_Motor_Encoder.step     (sibling of the .wrl; picked up
                                               by --subst-models)
  pcb/3d/Texas_DRC0010J.{wrl,step}            (U1 TPS63001, SON-10 3x3x1)
  pcb/3d/L_Bourns_SRP7028A_7.3x6.6mm.{wrl,step} (L1, 7.3x6.6x3.0)
U1/L1 footprints are repointed to the project .wrl by build_pcb.py; the
sibling .step satisfies --subst-models at export time.
"""
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class Step:
    def __init__(self, name):
        self.name = name
        self.e = []          # entity bodies, id = index+1
        self.solids = []

    def add(self, body):
        self.e.append(body)
        return len(self.e)

    def pt(self, x, y, z):
        return self.add(f"CARTESIAN_POINT('',({x:.4f},{y:.4f},{z:.4f}))")

    def dr(self, x, y, z):
        return self.add(f"DIRECTION('',({x:.1f},{y:.1f},{z:.1f}))")

    def box(self, x1, y1, z1, x2, y2, z2):
        # 8 corners keyed by (xbit, ybit, zbit)
        c = {}
        vp = {}
        for xb in (0, 1):
            for yb in (0, 1):
                for zb in (0, 1):
                    p = self.pt(x2 if xb else x1, y2 if yb else y1, z2 if zb else z1)
                    c[(xb, yb, zb)] = p
                    vp[(xb, yb, zb)] = self.add(f"VERTEX_POINT('',#{p})")
        edges = {}    # (a, b) -> EDGE_CURVE id (a, b are corner keys)

        def edge(a, b):
            if (a, b) in edges:
                return edges[(a, b)], True
            if (b, a) in edges:
                return edges[(b, a)], False
            d = tuple(bb - aa for aa, bb in zip(a, b))
            dirid = self.dr(*d)
            vec = self.add(f"VECTOR('',#{dirid},1.)")
            ln = self.add(f"LINE('',#{c[a]},#{vec})")
            ec = self.add(f"EDGE_CURVE('',#{vp[a]},#{vp[b]},#{ln},.T.)")
            edges[(a, b)] = ec
            return ec, True

        # faces: (loop corner keys CCW-from-outside, outward normal, in-plane ref)
        F = [
            ([(0,0,0), (0,1,0), (1,1,0), (1,0,0)], (0, 0, -1), (1, 0, 0)),   # bottom
            ([(0,0,1), (1,0,1), (1,1,1), (0,1,1)], (0, 0, 1), (1, 0, 0)),    # top
            ([(0,0,0), (1,0,0), (1,0,1), (0,0,1)], (0, -1, 0), (1, 0, 0)),   # front
            ([(0,1,0), (0,1,1), (1,1,1), (1,1,0)], (0, 1, 0), (1, 0, 0)),    # back
            ([(0,0,0), (0,0,1), (0,1,1), (0,1,0)], (-1, 0, 0), (0, 1, 0)),   # left
            ([(1,0,0), (1,1,0), (1,1,1), (1,0,1)], (1, 0, 0), (0, 1, 0)),    # right
        ]
        faces = []
        for loop, n, ref in F:
            oes = []
            for i in range(4):
                a, b = loop[i], loop[(i + 1) % 4]
                ec, fwd = edge(a, b)
                oes.append(self.add(
                    f"ORIENTED_EDGE('',*,*,#{ec},{'.T.' if fwd else '.F.'})"))
            el = self.add("EDGE_LOOP('',(" + ",".join(f"#{i}" for i in oes) + "))")
            fb = self.add(f"FACE_OUTER_BOUND('',#{el},.T.)")
            org = self.pt(x2 if loop[0][0] else x1, y2 if loop[0][1] else y1,
                          z2 if loop[0][2] else z1)
            ax = self.add(f"AXIS2_PLACEMENT_3D('',#{org},#{self.dr(*n)},#{self.dr(*ref)})")
            pl = self.add(f"PLANE('',#{ax})")
            faces.append(self.add(f"ADVANCED_FACE('',(#{fb}),#{pl},.T.)"))
        sh = self.add("CLOSED_SHELL('',(" + ",".join(f"#{i}" for i in faces) + "))")
        self.solids.append(self.add(f"MANIFOLD_SOLID_BREP('',#{sh})"))

    def write(self, path):
        n0 = len(self.e)
        ac = self.add("APPLICATION_CONTEXT('automotive design')")
        self.add(f"APPLICATION_PROTOCOL_DEFINITION('draft international standard','automotive_design',1998,#{ac})")
        pc = self.add(f"PRODUCT_CONTEXT('',#{ac},'mechanical')")
        pr = self.add(f"PRODUCT('{self.name}','{self.name}','',(#{pc}))")
        pdf = self.add(f"PRODUCT_DEFINITION_FORMATION('','',#{pr})")
        pdc = self.add(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{ac},'design')")
        pd = self.add(f"PRODUCT_DEFINITION('design','',#{pdf},#{pdc})")
        pds = self.add(f"PRODUCT_DEFINITION_SHAPE('','',#{pd})")
        lu = self.add("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
        au = self.add("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
        su = self.add("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
        un = self.add(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-05),#{lu},'distance_accuracy_value','')")
        ctx = self.add(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{un}))GLOBAL_UNIT_ASSIGNED_CONTEXT((#{lu},#{au},#{su}))REPRESENTATION_CONTEXT('',''))")
        org = self.pt(0, 0, 0)
        ax = self.add(f"AXIS2_PLACEMENT_3D('',#{org},#{self.dr(0,0,1)},#{self.dr(1,0,0)})")
        ids = ",".join(f"#{s}" for s in self.solids)
        rep = self.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION('',({ids},#{ax}),#{ctx})")
        self.add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{rep})")
        prpc = self.add(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part','',(#{pr}))")
        lines = [
            "ISO-10303-21;", "HEADER;",
            "FILE_DESCRIPTION((''),'2;1');",
            f"FILE_NAME('{os.path.basename(path)}','2026-07-16T00:00:00',(''),(''),'','','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
            "ENDSEC;", "DATA;",
        ]
        lines += [f"#{i+1}={b};" for i, b in enumerate(self.e)]
        lines += ["ENDSEC;", "END-ISO-10303-21;"]
        with open(path, "w", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print(f"wrote {path} ({len(self.solids)} solids, {len(self.e)} entities)")


def wrl_box_file(path, boxes):
    S = 2.54
    parts = []
    for (x1, y1, z1, x2, y2, z2, rgb) in boxes:
        cx, cy, cz = (x1+x2)/2/S, (y1+y2)/2/S, (z1+z2)/2/S
        dx, dy, dz = (x2-x1)/S, (y2-y1)/S, (z2-z1)/S
        parts.append(f"""    Transform {{
      translation {cx:.4f} {cy:.4f} {cz:.4f}
      children Shape {{
        appearance Appearance {{ material Material {{ diffuseColor {rgb} }} }}
        geometry Box {{ size {dx:.4f} {dy:.4f} {dz:.4f} }}
      }}
    }}""")
    with open(path, "w", newline="\n") as f:
        f.write("#VRML V2.0 utf8\nGroup { children [\n" + "\n".join(parts) + "\n] }\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    # ---- N20 motor: box-approximated version of the WRL in gen_n20_lib.py ------
    # origin = faceplate center, +X = shaft, axis height z=5
    n20 = Step("N20_Motor_Encoder")
    n20.box(0.0, -1.5, 3.5, 10.0, 1.5, 6.5)            # shaft (3mm sq approx)
    n20.box(-0.7, -6.0, 0.0, 0.0, 6.0, 10.0)           # faceplate
    n20.box(-9.7, -6.0, 0.0, -0.7, 6.0, 10.0)          # gearbox 9 long
    n20.box(-25.1, -6.0, 0.0, -9.7, 6.0, 10.0)         # motor can 15.4 (flatted)
    n20.box(-26.1, -2.5, 2.5, -25.1, 2.5, 7.5)         # rear boss
    n20.box(-27.7, -7.0, -1.0, -26.1, 7.0, 11.0)       # encoder PCB
    n20.box(-32.7, -4.5, 0.5, -27.7, 4.5, 9.5)         # magnet disc
    n20.write(os.path.join(BASE, "n20.3dshapes", "N20_Motor_Encoder.step"))

    # ---- U1 TPS63001 (SON-10 3x3x1) + L1 Bourns SRP7028A (7.3x6.6x3.0) ---------
    d3 = os.path.join(BASE, "3d")
    os.makedirs(d3, exist_ok=True)

    u1 = Step("Texas_DRC0010J")
    u1.box(-1.5, -1.5, 0.02, 1.5, 1.5, 1.0)
    u1.write(os.path.join(d3, "Texas_DRC0010J.step"))
    wrl_box_file(os.path.join(d3, "Texas_DRC0010J.wrl"),
                 [(-1.5, -1.5, 0.02, 1.5, 1.5, 1.0, "0.15 0.15 0.15")])

    l1 = Step("L_Bourns_SRP7028A_7.3x6.6mm")
    l1.box(-3.65, -3.3, 0.02, 3.65, 3.3, 3.0)
    l1.write(os.path.join(d3, "L_Bourns_SRP7028A_7.3x6.6mm.step"))
    wrl_box_file(os.path.join(d3, "L_Bourns_SRP7028A_7.3x6.6mm.wrl"),
                 [(-3.65, -3.3, 0.02, 3.65, 3.3, 3.0, "0.25 0.25 0.28")])
