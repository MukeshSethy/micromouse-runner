"""
generate_drivetrain.py - build every STEP / DXF deliverable.

    python generate_drivetrain.py

Outputs
    step/   individual printable parts + drivetrain_assembly_4wd.step
    dxf/    1:1 flat layouts of both side plates + the parallel-axle layout
"""

import math
import os
import time

import cadquery as cq
from cadquery import exporters

import chassis_lib as C
import config as K
import gear_lib as gl

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.join(HERE, "step")
DXF = os.path.join(HERE, "dxf")
for d in (STEP, DXF):
    os.makedirs(d, exist_ok=True)


def _save(wp, name, folder=STEP, ext="step"):
    path = os.path.join(folder, "%s.%s" % (name, ext))
    exporters.export(wp, path)
    print("  %-42s %8.1f kB" % (os.path.basename(path),
                                os.path.getsize(path) / 1024.0))
    return path


# ------------------------------------------------------------------- gears
# chamfer: real cut/moulded POM gears carry a tip break. Modelling it costs
# ~3.5x the STEP size but the file is a manufacturing spec, so it stays in.
GK = dict(alpha_deg=K.PRESSURE_ANGLE, backlash=K.BACKLASH,
          ha=K.ADDENDUM_C, hf=K.DEDENDUM_C, fil_c=K.FILLET_C,
          chamfer=K.GEAR_TIP_CHAMFER)


def make_gears():
    motor = gl.spur_gear(K.MODULE, K.N_MOTOR, K.GEAR_FW, bore="D3", **GK)
    wheel = gl.spur_gear(K.MODULE, K.N_WHEEL, K.GEAR_FW, bore="D3", **GK)
    # the wheel's own 6-hole bolt circle, repeated in the gear (M2 clear):
    # both parts clock to the same D-flat, so holes cut at the same angles
    # in the part frame stay aligned through mesh phasing and mirroring
    for k in range(6):
        a = math.radians(60 * k)
        wheel = wheel.cut(
            cq.Workplane("XY").circle(K.GEAR_BC_HOLE / 2.0)
            .extrude(K.GEAR_FW + 2.0)
            .translate((K.WHEEL_BC_R * math.cos(a),
                        K.WHEEL_BC_R * math.sin(a), -1.0)))
    idler = None
    if K.N_IDLER is not None:
        idler = gl.spur_gear(K.MODULE, K.N_IDLER, K.IDLER_FW,
                             bore=K.IDLER_DOWEL_D + 0.15,
                             boss=(5.0, 0.15), **GK)
    return motor, idler, wheel


def _tooth_at(n, ang_deg, phase=0.0):
    """True if gear `n`, clocked by `phase`, has a tooth centred at ang_deg."""
    pitch = 360.0 / n
    k = (ang_deg - phase) / pitch
    return abs(k - round(k)) < 1e-6


def mesh_phase():
    """
    Half-pitch offsets that make a tooth face a space at every mesh.

    Tooth 0 of every generated gear is centred on the +X direction. At a mesh
    along X, one gear must present a tooth where the other presents a space.
    Solved rather than hand-tabulated, because the answer flips with tooth
    parity: an ODD pinion already presents a space at 180 deg, an even one
    does not.
    """
    ph = {"motor": 0.0}
    half_w = 360.0 / K.N_WHEEL / 2.0

    if K.N_IDLER is None:
        # pinion meshes each wheel gear directly
        for key, toward in (("wheel+", 180.0), ("wheel-", 0.0)):
            # direction from the wheel gear back to the pinion
            motor_face = 0.0 if key == "wheel+" else 180.0
            motor_has_tooth = _tooth_at(K.N_MOTOR, motor_face)
            # wheel gear must show a SPACE where the pinion shows a tooth
            want_tooth = not motor_has_tooth
            ph[key] = 0.0 if _tooth_at(K.N_WHEEL, toward) == want_tooth \
                else half_w
        return ph

    half_i = 360.0 / K.N_IDLER / 2.0
    ph["idler+"] = half_i if _tooth_at(K.N_MOTOR, 0.0) else 0.0
    ph["idler-"] = half_i if _tooth_at(K.N_MOTOR, 180.0) else 0.0
    ph["wheel+"] = half_w
    ph["wheel-"] = half_w
    return ph


def place_gear(g, x, y0, rot_deg=0.0):
    g = g.rotate((0, 0, 0), (0, 0, 1), rot_deg)
    return (g.rotate((0, 0, 0), (1, 0, 0), -90)
            .translate((x, y0, K.AXLE_Z)))


# ---------------------------------------------------------------- 2D layout
def layout_2d(kind):
    """Flat 1 mm proxy of a side plate, used only for the DXF export."""
    t = 1.0
    p = C._blank(t)
    for sx in (-1.0, 1.0):
        p = p.cut(C._cyl(K.BRG_FL_CB, t + 2.0, sx * K.X_AXLE, K.AXLE_Z, -1.0))
        if K.X_IDLER is not None:
            p = p.cut(C._cyl(2.90 if kind == "inner" else 3.05, t + 2.0,
                             sx * K.X_IDLER, K.AXLE_Z, -1.0))
    if kind == "inner":
        p = p.cut(C._motor_slot(t))
        p = C._holes(p, K.STANDOFF_PTS, K.M2_TAP, t)
        p = C._holes(p, K.TUBE_SCREW_PTS, K.M2_CLEAR, t)
    else:
        p = p.cut(C._cyl(K.MOT_SHAFT_CLR_D, t + 2.0, 0.0, K.AXLE_Z, -1.0))
        p = C._holes(p, K.STANDOFF_PTS, K.M2_CLEAR, t)
    return p.faces("<Z")


def axle_layout_2d():
    """Pitch + tip circles on the common axle line - the mounting schematic."""
    t = 1.0
    w = cq.Workplane("XY")
    specs = [(0.0, K.N_MOTOR),
             (-K.X_AXLE, K.N_WHEEL), (K.X_AXLE, K.N_WHEEL)]
    if K.X_IDLER is not None:
        specs += [(-K.X_IDLER, K.N_IDLER), (K.X_IDLER, K.N_IDLER)]
    solid = None
    for (x, n) in specs:
        ring = (C._cyl(K.MODULE * (n + 2), t, x, K.AXLE_Z)
                .cut(C._cyl(K.MODULE * n, t + 2.0, x, K.AXLE_Z, -1.0)))
        solid = ring if solid is None else solid.union(ring)
        pin = (C._cyl(K.BRG_OD, t, x, K.AXLE_Z)
               .cut(C._cyl(K.AXLE_D, t + 2.0, x, K.AXLE_Z, -1.0)))
        solid = solid.union(pin)
    return solid.faces("<Z")


# ------------------------------------------------------------------ assembly
def build_assembly(motor_g, idler, wheel_g):
    a = cq.Assembly(name="Micromouse_4WD_3to1_Drivetrain")
    ph = mesh_phase()

    for side, sgn in (("L", 1.0), ("R", -1.0)):
        def mir(x):
            return x.mirror("XZ") if sgn < 0 else x

        a.add(mir(C.place_plate(C.motor_pod(), K.Y_IN_OUT)),
              name="pod_%s" % side, color=cq.Color(*K.COL["plate"]))

        a.add(mir(place_gear(motor_g, K.X_MOTOR, K.Y_GEAR, ph["motor"])),
              name="gear_motor_%s" % side, color=cq.Color(*K.COL["gear"]))

        for i, sx in enumerate((-1.0, 1.0)):
            tag = "%s%d" % (side, i)
            key = "+" if sx > 0 else "-"
            if idler is not None:
                a.add(mir(place_gear(idler, sx * K.X_IDLER, K.Y_IDLER,
                                     ph["idler" + key])),
                      name="gear_idler_%s" % tag,
                      color=cq.Color(*K.COL["idler"]))
            a.add(mir(place_gear(wheel_g, sx * K.X_AXLE, K.Y_GEAR,
                                 ph["wheel" + key])),
                  name="gear_axle_%s" % tag, color=cq.Color(*K.COL["gear"]))

            # Live axle. The D-shaft must be clocked to the SAME phase as the
            # axle gear, otherwise the gear's D-bore flat and the shaft flat
            # disagree by the mesh offset and the two interfere.
            a.add(mir(place_gear(C.d_axle(), sx * K.X_AXLE, K.Y_AXLE_IN,
                                 ph["wheel" + key])),
                  name="axle_%s" % tag, color=cq.Color(*K.COL["hw"]))
            # Both bearings live in the cantilever boss: one flanged at the
            # boss's inboard end, one flanged at the plate's outboard face.
            for y0, flip in ((K.Y_BOSS_IN, False), (K.Y_IN_OUT, True)):
                b = C.bearing_f683()
                b = (b.rotate((0, 0, 0), (1, 0, 0), 90) if flip
                     else b.rotate((0, 0, 0), (1, 0, 0), -90))
                a.add(mir(b.translate((sx * K.X_AXLE, y0, K.AXLE_Z))),
                      name="brg_%s_%s" % (tag, "out" if flip else "in"),
                      color=cq.Color(*K.COL["brg"]))
            # wheel now has a real D-bore, so it clocks with the shaft too
            a.add(mir(place_gear(C.wheel_placeholder(), sx * K.X_AXLE,
                                 K.Y_WHEEL, ph["wheel" + key])),
                  name="wheel_%s" % tag, color=cq.Color(*K.COL["dark"]))

            if K.X_IDLER is not None:
                a.add(mir(C._cyl_y(K.IDLER_DOWEL_D, K.Y_TUBE,
                                   K.Y_TUBE + K.IDLER_DOWEL_L,
                                   x=sx * K.X_IDLER, z=K.AXLE_Z)),
                      name="dowel_%s" % tag, color=cq.Color(*K.COL["hw"]))

        # real vendor STEP, faceplate at the PCB-derived Y = +/-37
        a.add(mir(C.place_motor()),
              name="motor_N20_encoder_%s" % side, color=cq.Color(*K.COL["hw"]))

    a.add(C.pcb_board(), name="PCB_xiao_2layer_REFERENCE",
          color=cq.Color(*K.COL["pcb"]))
    return a


# ---------------------------------------------------------------------- main
def main():
    t0 = time.time()
    print(K.summary())

    print("\n[1/4] gears")
    motor_g, idler, wheel_g = make_gears()
    _save(motor_g, "gear_%02dT_m0p5_D3bore_MOTOR" % K.N_MOTOR)
    if idler is not None:
        _save(idler, "gear_%02dT_m0p5_B3_IDLER" % K.N_IDLER)
    _save(wheel_g, "gear_%02dT_m0p5_D3bore_WHEEL" % K.N_WHEEL)

    print("\n[2/4] printed structure + hardware")
    _save(C.motor_pod(), "motor_pod_x2")
    _save(C.d_axle(), "axle_D3_L%s_x4_REFERENCE"
          % ("%.1f" % K.AXLE_LEN).replace(".", "p"))

    print("\n[3/4] vendor geometry (imported, not re-modelled)")
    print("      motor: %s" % os.path.relpath(K.MOTOR_STEP, HERE))
    print("      board: %s" % os.path.relpath(K.PCB_STEP, HERE))

    print("\n[4/4] 2D layouts + assembly")
    _save(layout_2d("inner"), "plate_inner_layout", DXF, "dxf")
    _save(axle_layout_2d(), "parallel_axle_layout", DXF, "dxf")

    asm = build_assembly(motor_g, idler, wheel_g)
    path = os.path.join(STEP, "drivetrain_assembly_4wd.step")
    asm.save(path)
    print("  %-42s %8.1f kB" % ("drivetrain_assembly_4wd.step",
                                os.path.getsize(path) / 1024.0))
    print("\ndone in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
