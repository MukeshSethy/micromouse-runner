"""Strict JLC-cap-Lion geometric checker for ground via / escape-track placement.

Encodes the stricter of JLCPCB and Lion Circuits on every parameter, so anything
this module approves also passes the board's DRC rule set:

    CLR   0.20mm   copper to copper, different nets
    H2H   0.50mm   drilled hole edge to drilled hole edge (ALL holes, same net too)
    HCLR  0.25mm   drilled hole to copper of a different net
    EDGE  0.30mm   copper to board edge

Pads are modelled as RECTANGLES, not circles. An earlier version used a circle
of the pad's LARGEST dimension, which turned a 1.9 x 0.4mm TSSOP pad into a
0.95mm-radius disc and made legal escape tracks along a fine-pitch pad row look
illegal -- that false negative is what made U2 pad 18 and U1 pad 4 (the TB6612
logic ground and the buck ground) look impossible to connect.
"""
import math

import pcbnew

mm = pcbnew.ToMM
FM = pcbnew.FromMM

CLR = 0.20
H2H = 0.50
HCLR = 0.25
EDGE = 0.30
VIA_R = 0.30       # 0.6mm via pad radius
VIA_HR = 0.15      # 0.3mm via hole radius


def build(b):
    """Snapshot board geometry as plain numbers (SWIG proxies degrade on mutation)."""
    m = dict(tracks=[], pads=[], holes=[], outline=None)
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            m["holes"].append((mm(p.x), mm(p.y), mm(t.GetDrill()) / 2, t.GetNetname()))
            r = mm(t.GetWidth(pcbnew.F_Cu)) / 2
            m["pads"].append((mm(p.x) - r, mm(p.y) - r, mm(p.x) + r, mm(p.y) + r,
                              t.GetNetname(), "both"))
        else:
            s, e = t.GetStart(), t.GetEnd()
            m["tracks"].append(((mm(s.x), mm(s.y)), (mm(e.x), mm(e.y)),
                                mm(t.GetWidth()) / 2, t.GetNetname(), t.GetLayer()))
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            p = pad.GetPosition()
            d = mm(pad.GetDrillSize().x)
            if d > 0:
                m["holes"].append((mm(p.x), mm(p.y), d / 2, pad.GetNetname()))
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                continue
            bb = pad.GetBoundingBox()
            lay = "both"
            onf, onb = pad.IsOnLayer(pcbnew.F_Cu), pad.IsOnLayer(pcbnew.B_Cu)
            if onf and not onb:
                lay = "F"
            elif onb and not onf:
                lay = "B"
            m["pads"].append((mm(bb.GetLeft()), mm(bb.GetTop()),
                              mm(bb.GetRight()), mm(bb.GetBottom()),
                              pad.GetNetname(), lay))
    outl = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outl, True)
    m["outline"] = outl
    return m


def _dist_point_seg(p, a, c):
    ax, ay = a
    cx, cy = c
    px, py = p
    dx, dy = cx - ax, cy - ay
    L = dx * dx + dy * dy
    if L < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _dist_point_rect(p, rect):
    x, y = p
    l, t, r, bt = rect
    dx = max(l - x, 0.0, x - r)
    dy = max(t - y, 0.0, y - bt)
    return math.hypot(dx, dy)


def _seg_seg(a1, a2, b1, b2):
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = cross(b1, b2, a1)
    d2 = cross(b1, b2, a2)
    d3 = cross(a1, a2, b1)
    d4 = cross(a1, a2, b2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(_dist_point_seg(a1, b1, b2), _dist_point_seg(a2, b1, b2),
               _dist_point_seg(b1, a1, a2), _dist_point_seg(b2, a1, a2))


def _dist_seg_rect(a, c, rect):
    l, t, r, bt = rect
    corners = [(l, t), (r, t), (r, bt), (l, bt)]
    best = 9e9
    for i in range(4):
        best = min(best, _seg_seg(a, c, corners[i], corners[(i + 1) % 4]))
    # segment endpoint inside the rect counts as zero distance
    for p in (a, c):
        if l <= p[0] <= r and t <= p[1] <= bt:
            return 0.0
    return best


def _on_layer(lay_tag, layer):
    if lay_tag == "both":
        return True
    return lay_tag == ("F" if layer == pcbnew.F_Cu else "B")


def can_place_via(m, p, net="GND"):
    """True only if a 0.6/0.3mm via at p satisfies every vendor rule."""
    x, y = p
    o = m["outline"]
    if not o.Collide(pcbnew.VECTOR2I(FM(x), FM(y)), 0):
        return False, "off-board"
    for dx, dy in ((VIA_R + EDGE, 0), (-(VIA_R + EDGE), 0),
                   (0, VIA_R + EDGE), (0, -(VIA_R + EDGE))):
        if not o.Collide(pcbnew.VECTOR2I(FM(x + dx), FM(y + dy)), 0):
            return False, "edge<%.2f" % EDGE
    for (hx, hy, hr, hn) in m["holes"]:
        if abs(hx - x) < 1e-6 and abs(hy - y) < 1e-6:
            continue
        if math.hypot(hx - x, hy - y) < VIA_HR + hr + H2H:
            return False, "h2h<%.2f" % H2H
    for (a, c, hw, tn, lay) in m["tracks"]:
        if tn == net:
            continue
        d = _dist_point_seg(p, a, c)
        if d < VIA_R + hw + CLR:
            return False, "trk %s" % tn
        if d < VIA_HR + hw + HCLR:
            return False, "hole-trk %s" % tn
    for (l, t, r, bt, pn, lay) in m["pads"]:
        if pn == net:
            continue
        if _dist_point_rect(p, (l, t, r, bt)) < VIA_R + CLR:
            return False, "pad %s" % pn
    return True, "ok"


def can_place_track(m, a, c, layer, hw=0.10, net="GND"):
    """True only if a track of half-width hw from a to c on `layer` is legal."""
    o = m["outline"]
    for p in (a, c):
        if not o.Collide(pcbnew.VECTOR2I(FM(p[0]), FM(p[1])), 0):
            return False, "off-board"
    for (t1, t2, thw, tn, tlay) in m["tracks"]:
        if tn == net or tlay != layer:
            continue
        if _seg_seg(a, c, t1, t2) < hw + thw + CLR:
            return False, "trk %s" % tn
    for (l, t, r, bt, pn, lay) in m["pads"]:
        if pn == net or not _on_layer(lay, layer):
            continue
        if _dist_seg_rect(a, c, (l, t, r, bt)) < hw + CLR:
            return False, "pad %s" % pn
    for (hx, hy, hr, hn) in m["holes"]:
        if hn == net:
            continue
        if _dist_point_seg((hx, hy), a, c) < hw + hr + HCLR:
            return False, "hole %s" % hn
    return True, "ok"
