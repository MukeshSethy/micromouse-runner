"""
gear_lib.py - Involute spur gear geometry for the Micromouse 4WD 1:1 drivetrain.

Standard full-depth involute profile:
    pitch dia      d  = m * N
    base dia       db = d * cos(alpha)
    tip dia        da = m * (N + 2*ha)
    root dia       df = m * (N - 2*hf)
    tooth thk @ d  s  = pi*m/2 - backlash/2

Flanks are true involutes (fitted with a B-spline through 14 exact points),
tip and root are exact circular arcs, and the root/flank junction carries a
tangent circular fillet (auto-shrunk when the base circle sits on top of the
root circle, which happens as N approaches 41 at 20 deg pressure angle).
"""

import math

import cadquery as cq


def _pol(r, th):
    return (r * math.cos(th), r * math.sin(th))


def _rot(p, off):
    c, s = math.cos(off), math.sin(off)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def gear_params(m, N, alpha_deg=20.0, backlash=0.05, ha=1.0, hf=1.25):
    a = math.radians(alpha_deg)
    rp = m * N / 2.0
    return {
        "m": m, "N": N, "alpha": a,
        "rp": rp,
        "rb": rp * math.cos(a),
        "ra": rp + ha * m,
        "rf": rp - hf * m,
        "sp": math.pi * m / 2.0 - backlash / 2.0,
        "tau": 2.0 * math.pi / N,
    }


def _tooth_segments(m, N, alpha_deg, backlash, ha, hf, fil_c, n_flank):
    P = gear_params(m, N, alpha_deg, backlash, ha, hf)
    a, rp, rb, ra, rf, sp, tau = (P["alpha"], P["rp"], P["rb"],
                                  P["ra"], P["rf"], P["sp"], P["tau"])

    def inv(t):
        return math.tan(t) - t

    inv_a = inv(a)

    def psi(r):
        rr = max(r, rb)
        ar = math.acos(max(-1.0, min(1.0, rb / rr)))
        return sp / (2.0 * rp) + inv_a - inv(ar)

    r_start = max(rb, rf + 1e-4)
    thA = psi(r_start)

    # largest tangent root fillet that still fits below the involute start
    rfil = fil_c * m
    while rfil > 0.02:
        dC = rf + rfil
        d = math.asin(min(1.0, rfil / dC))
        if dC * math.cos(d) <= r_start - 0.01:
            break
        rfil *= 0.8
    else:
        rfil = 0.0

    segs = []
    if rfil > 0.0:
        dC = rf + rfil
        d = math.asin(rfil / dC)
        B_r = _pol(rf, -(thA + d))
        A_r = _pol(dC * math.cos(d), -thA)
        Cc = _pol(dC, -(thA + d))
        ub = (B_r[0] - Cc[0], B_r[1] - Cc[1])
        ua = (A_r[0] - Cc[0], A_r[1] - Cc[1])
        nb, na = math.hypot(*ub), math.hypot(*ua)
        mx, my = ub[0] / nb + ua[0] / na, ub[1] / nb + ua[1] / na
        nm = math.hypot(mx, my)
        M_r = (Cc[0] + rfil * mx / nm, Cc[1] + rfil * my / nm)
        segs.append(("arc", B_r, M_r, A_r))
        segs.append(("line", A_r, _pol(r_start, -thA)))
        th_root = thA + d
    else:
        B_r = _pol(rf, -thA)
        segs.append(("line", B_r, _pol(r_start, -thA)))
        th_root = thA

    rs = [r_start + (ra - r_start) * i / (n_flank - 1) for i in range(n_flank)]
    right = [_pol(r, -psi(r)) for r in rs]
    left = [_pol(r, psi(r)) for r in reversed(rs)]
    segs.append(("spline", right))
    segs.append(("arc", right[-1], _pol(ra, 0.0), left[0]))
    segs.append(("spline", left))

    if rfil > 0.0:
        A_l = (A_r[0], -A_r[1])
        M_l = (M_r[0], -M_r[1])
        B_l = (B_r[0], -B_r[1])
        segs.append(("line", left[-1], A_l))
        segs.append(("arc", A_l, M_l, B_l))
    else:
        B_l = (B_r[0], -B_r[1])
        segs.append(("line", left[-1], B_l))

    segs.append(("arc", B_l, _pol(rf, tau / 2.0), _pol(rf, tau - th_root)))
    return segs, P, thA


def gear_wire(m, N, alpha_deg=20.0, backlash=0.05, ha=1.0, hf=1.25,
              fil_c=0.25, n_flank=14):
    """Closed planar wire of a full involute spur gear, centred on the origin."""
    segs, P, _ = _tooth_segments(m, N, alpha_deg, backlash, ha, hf,
                                 fil_c, n_flank)
    tau = P["tau"]
    wp = cq.Workplane("XY").moveTo(*segs[0][1])
    for k in range(N):
        off = k * tau
        for s in segs:
            if s[0] == "line":
                wp = wp.lineTo(*_rot(s[2], off))
            elif s[0] == "arc":
                wp = wp.threePointArc(_rot(s[2], off), _rot(s[3], off))
            else:
                pts = [_rot(p, off) for p in s[1]]
                wp = wp.spline(pts[1:], includeCurrent=True)
    return wp.close()


def _d_bore_tool(bore_d, flat_off, h):
    """Cutting tool for a D-profile bore: circle with one chord removed."""
    tool = cq.Workplane("XY").circle(bore_d / 2.0).extrude(h)
    chord = (cq.Workplane("XY").center(flat_off + bore_d, 0)
             .rect(2 * bore_d, 2 * bore_d).extrude(h))
    return tool.cut(chord)


def spur_gear(m, N, face_width, bore="D3", boss=None, chamfer=None, **kw):
    """
    bore:    "D3"  -> 3 mm D-profile bore (N20 / Pololu wheel shaft)
             float -> plain round bore of that diameter
    boss:    (dia, height) added to BOTH faces (used for the idlers so the gear
             body never rubs the chassis plates).
    chamfer: tip-edge chamfer in mm. Off by default - at m0.5 it adds ~3.5x to
             the STEP size for a 0.15 mm break. Pass chamfer=0.15 if your
             supplier or slicer wants it modelled.
    """
    g = gear_wire(m, N, **kw).extrude(face_width)

    if chamfer:
        try:
            g = g.edges(">Z or <Z").chamfer(chamfer)
        except Exception:
            pass

    if boss:
        bd, bh = boss
        g = g.union(cq.Workplane("XY").circle(bd / 2.0).extrude(bh)
                    .translate((0, 0, face_width)))
        g = g.union(cq.Workplane("XY").circle(bd / 2.0).extrude(bh)
                    .translate((0, 0, -bh)))
        z0, ht = -bh - 1.0, face_width + 2 * bh + 2.0
    else:
        z0, ht = -1.0, face_width + 2.0

    if bore == "D3":
        # 3 mm D-shaft: 3.00 dia, 2.50 across the flat -> flat 1.00 off centre
        tool = _d_bore_tool(3.0 + 0.08, 1.00 + 0.02, ht).translate((0, 0, z0))
    else:
        tool = (cq.Workplane("XY").circle(float(bore) / 2.0)
                .extrude(ht).translate((0, 0, z0)))
    return g.cut(tool)
