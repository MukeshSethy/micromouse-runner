"""
export_mesh.py - tessellate the real assembly for the WebGL viewer.

Emits web/robot_mesh.json: one entry per render group, vertices quantised to
int16 (0.01 mm) and normals to int8, base64 packed. Rotating groups are moved
into a local frame centred on their own axle so the viewer can spin them.
"""

import base64
import json
import os
import struct

import cadquery as cq

import chassis_lib as C
import config as K
import generate_drivetrain as G

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "web")
os.makedirs(OUT, exist_ok=True)

TOL, ATOL = 0.35, 0.5          # coarse: this is a viewer, not a print


def tess(shape, origin=(0.0, 0.0, 0.0), tol=None):
    """
    Also rotates 180 deg about Z: (x,y) -> (-x,-y).

    The CAD frame puts the NOSE at X = -84 (board y = 0 is the radiused front,
    and board_to_X maps it to -84), so +X in the CAD is REARWARD. The viewer
    wants +X forward, and it wants +Y to be the robot's actual left. This is a
    proper rotation, so triangle winding survives it.
    """
    v, t = shape.tessellate(tol or TOL, ATOL)
    ox, oy, oz = origin
    verts = [(-(p.x - ox), -(p.y - oy), p.z - oz) for p in v]
    # face normals -> per-vertex (flat shading is fine for machined parts)
    P, Nrm, I = [], [], []
    for (a, b, c) in t:
        p0, p1, p2 = verts[a], verts[b], verts[c]
        ux, uy, uz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
        vx, vy, vz = p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2]
        nx, ny, nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
        L = (nx*nx+ny*ny+nz*nz) ** 0.5 or 1.0
        n = (nx/L, ny/L, nz/L)
        for p in (p0, p1, p2):
            I.append(len(P))
            P.append(p)
            Nrm.append(n)
    return P, Nrm, I


def pack(P, Nrm):
    vb = bytearray()
    nb = bytearray()
    for (x, y, z) in P:
        vb += struct.pack("<hhh", int(round(x*100)), int(round(y*100)),
                          int(round(z*100)))
    for (x, y, z) in Nrm:
        nb += struct.pack("<bbb", max(-127, min(127, int(round(x*127)))),
                          max(-127, min(127, int(round(y*127)))),
                          max(-127, min(127, int(round(z*127)))))
    return (base64.b64encode(bytes(vb)).decode(),
            base64.b64encode(bytes(nb)).decode())


def main():
    motor_g, idler, wheel_g = G.make_gears()
    asm = G.build_assembly(motor_g, idler, wheel_g)

    parts = {}
    for ch in asm.children:
        if ch.obj is None:
            continue
        parts[ch.name] = ch.obj.val().moved(ch.loc)

    groups = []

    def add(name, shapes, kind, origin=(0, 0, 0), color="#888888", tol=None):
        if not shapes:
            return
        comp = cq.Compound.makeCompound(shapes)
        P, Nrm, I = tess(comp, origin, tol)
        v64, n64 = pack(P, Nrm)
        groups.append({"name": name, "kind": kind, "color": color,
                       "origin": list(origin), "n": len(P),
                       "v": v64, "nr": n64})
        print("  %-22s %-9s %7d tris" % (name, kind, len(P)//3))

    # --- static in the body frame ---
    static, static_col = [], []
    for nm, s in parts.items():
        # rev 7: the printed structure is the two motor pods. This filter is
        # name-based; when the assembly renamed plate_/motor_tube -> pod_ the
        # pods silently vanished from the viewer. Fail LOUDLY instead.
        if nm.startswith(("pod_", "plate_", "motor_tube")):
            static.append(s)
    assert static, "no printed structure matched - check assembly part names"
    add("chassis", static, "static", color="#E11A27")
    # PCB: keep the board and the parts you can actually see; the 0603s cost
    # ~30k triangles between them and read as noise at this scale.
    pcb_solids = []
    for n, s in parts.items():
        if n.startswith("PCB_"):
            pcb_solids += [x for x in s.Solids() if x.Volume() > 25.0]
    add("pcb", pcb_solids, "static", color="#2E6B33", tol=1.4)
    add("motors", [s for n, s in parts.items()
                   if n.startswith("motor_N20")], "static", color="#3A3532")
    add("hw", [s for n, s in parts.items()
               if n.startswith(("standoff", "shim_", "brg_", "dowel"))],
        "static", color="#9A928C")

    # --- rotating parts: ONE mesh each, centred on its own axle and mid-plane,
    #     then instanced. Six gear copies became two unique meshes.
    yg = K.Y_GEAR + K.GEAR_FW / 2.0            # gear mid-plane
    yw = K.Y_WHEEL + K.WHEEL_W / 2.0           # wheel mid-plane
    add("pinion", [parts["gear_motor_L"]], "spin",
        origin=(0.0, yg, K.AXLE_Z), color="#EDAB36")
    add("gear", [parts["gear_axle_L1"]], "spin",
        origin=(K.X_AXLE, yg, K.AXLE_Z), color="#EDAB36")
    add("wheel", [parts["wheel_L1"]], "spin",
        origin=(K.X_AXLE, yw, K.AXLE_Z), color="#4A4441")

    # instance positions get the same 180 deg flip; side is then read off the
    # NEW y, so "side 1" really is the robot's left once it faces +X
    inst = []
    for sy in (1.0, -1.0):
        ny = -sy * yg
        inst.append({"m": "pinion", "x": 0.0, "y": ny, "z": K.AXLE_Z,
                     "side": 1 if ny > 0 else -1, "rate": K.RATIO})
        for sx in (-1.0, 1.0):
            inst.append({"m": "gear", "x": -sx * K.X_AXLE, "y": ny,
                         "z": K.AXLE_Z, "side": 1 if ny > 0 else -1,
                         "rate": 1.0})
            inst.append({"m": "wheel", "x": -sx * K.X_AXLE, "y": -sy * yw,
                         "z": K.AXLE_Z, "side": 1 if -sy > 0 else -1,
                         "rate": 1.0, "contact": True})

    meta = {"axleZ": K.AXLE_Z, "axleX": K.X_AXLE, "ratio": K.RATIO,
            "wheelR": K.WHEEL_DIA/2.0, "track": K.TRACK_OUTER,
            "wheelY": yw, "gearY": yg,
            "front": 84.0, "rear": 36.0, "halfW": K.TRACK_OUTER/2.0}
    doc = {"meta": meta, "groups": groups, "instances": inst}
    path = os.path.join(OUT, "robot_mesh.json")
    with open(path, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    tris = sum(g["n"] for g in groups)//3
    print("\n%s  %.2f MB  %d triangles total"
          % (os.path.relpath(path, HERE), os.path.getsize(path)/1e6, tris))


if __name__ == "__main__":
    main()
