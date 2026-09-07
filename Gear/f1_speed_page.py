"""
f1_speed_page.py - "what if the 120 mm micromouse ran at F1 speeds?"
Extrapolates the same aero model (real frontal/plan areas, drag equation,
the measured wing CL) to 360 km/h straights and 270 km/h corners, and
shows where the physics changes qualitatively (compressibility, Reynolds
regime, and the impossible corner). Pure hypothetical - stated as such.

    python f1_speed_page.py <out.html>
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RHO, NU, A_SND = 1.204, 1.516e-5, 343.0
G = 9.81
CD = 0.9
MU = 2.3
R_CORNER = 0.09
STR, COR = 100.0, 75.0          # m/s: ~360 and ~270 km/h


def build():
    d = json.load(open(os.path.join(HERE, "aero_data.json")))
    A_f = d["areas"]["front_mm2"]*1e-6
    A_p = d["areas"]["plan_mm2"]*1e-6
    L = d["areas"]["length_mm"]*1e-3
    m = 0.22
    W = m*G

    def row(v):
        q = 0.5*RHO*v*v
        D = q*CD*A_f
        return dict(v=v, kmh=v*3.6, D=D, wr=D/W, P=D*v, dec_g=D/m/G,
                    M=v/A_SND, Re=v*L/NU, ac_g=(v*v/R_CORNER)/G)

    speeds = {"straight": row(STR), "corner": row(COR), "ref": row(5.0)}
    # wing downforce at corner speed, for a few CLs
    wings = []
    for CL, name in ((0.3, "printed wing"), (1.5, "aggressive wing"),
                     (3.0, "F1-grade underbody")):
        DF = 0.5*RHO*CL*A_p*COR*COR
        vmax = math.sqrt(MU*G*R_CORNER*(1+DF/W))
        wings.append((name, CL, DF, DF/W, vmax))
    # radius needed to actually take a 75 m/s corner
    r_nowing = COR*COR/(MU*G)
    DF3 = 0.5*RHO*3.0*A_p*COR*COR
    r_wing = COR*COR/(MU*G*(1+DF3/W))

    return dict(A_f=A_f, A_p=A_p, W=W, speeds=speeds, wings=wings,
                r_nowing=r_nowing, r_wing=r_wing)


def bar_svg(items, unit, vmax, w=680, rowh=34, lab=250, col="#e08a2a",
            lognote=False):
    h = rowh*len(items) + 12
    out = ['<svg viewBox="0 0 %d %d" role="img">' % (w, h)]
    xw = w - lab - 110
    for i, (name, val, disp) in enumerate(items):
        y = 6 + i*rowh
        frac = (math.log10(max(val, 1e-6))/math.log10(vmax)) if lognote \
            else val/vmax
        frac = max(0.004, min(1.0, frac))
        out.append('<text x="%d" y="%d" fill="#a79c93" font-size="12" '
                   'dy="15" text-anchor="end">%s</text>'
                   % (lab-12, y, name))
        out.append('<rect x="%d" y="%d" width="%.1f" height="20" rx="4" '
                   'fill="%s"/>' % (lab, y, xw*frac, col))
        out.append('<text x="%.1f" y="%d" fill="#f2ede8" font-size="12" '
                   'dy="15" font-weight="600">%s</text>'
                   % (lab+xw*frac+8, y, disp))
    out.append('</svg>')
    return "".join(out)


TEMPLATE = """<title>Micromouse at F1 Speeds</title>
<style>
:root{--bg:#0d0d0d;--surface:#1a1a19;--ink:#f2ede8;--ink2:#a79c93;
--muted:#898781;--rule:#332c27;--accent:#e08a2a;--aqua:#199e70;
--crit:#d03b3b}
@media (prefers-color-scheme: light){:root:not([data-theme=dark]){
--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--rule:#e1e0d9;
--accent:#eb6834;--aqua:#1baf7a;--crit:#d03b3b}}
:root[data-theme=light]{--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;
--ink2:#52514e;--rule:#e1e0d9;--accent:#eb6834;--aqua:#1baf7a;
--crit:#d03b3b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:15px;
line-height:1.6}
.wrap{max-width:920px;margin:0 auto;padding:34px 20px 60px;display:flex;
flex-direction:column;gap:24px}
.eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
color:var(--accent);font-weight:700}
h1{margin:.15em 0 0;font-size:clamp(24px,4.4vw,38px);letter-spacing:-.02em;
text-wrap:balance}
h2{margin:0;font-size:19px}
p{margin:0;max-width:70ch;color:var(--ink2)}
p.lead{color:var(--ink);font-size:16.5px}
section{display:flex;flex-direction:column;gap:12px}
.card{background:var(--surface);border:1px solid var(--rule);
border-radius:8px;padding:18px 20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
gap:12px}
.tile{background:var(--surface);border:1px solid var(--rule);
border-radius:8px;padding:13px 15px}
.tile .k{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
color:var(--muted)}
.tile .v{font-size:24px;font-weight:700;letter-spacing:-.02em;margin-top:3px;
color:var(--accent)}
.tile .n{font-size:12px;color:var(--ink2);margin-top:2px}
svg{width:100%;height:auto;display:block}
.note{border-left:3px solid var(--accent);padding:10px 0 10px 14px;
font-size:13.5px;color:var(--ink2)}
.warn{border-left-color:var(--crit)}
table{border-collapse:collapse;width:100%;font-size:13.5px;
font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:7px 9px;border-bottom:1px solid var(--rule)}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-size:11px;letter-spacing:.08em;
text-transform:uppercase;font-weight:600}
.scroll{overflow-x:auto}
footer{border-top:1px solid var(--rule);padding-top:12px;font-size:12.5px;
color:var(--muted);line-height:1.6}
</style>
<div class=wrap>
<header>
 <div class=eyebrow>micromouse 4wd &middot; a hypothetical</div>
 <h1>The 120&thinsp;mm robot at Formula&nbsp;1 speeds</h1>
</header>
<p class=lead>Take the same aero model &mdash; real CAD frontal area, the
drag equation, the measured wing &mdash; and wind it up to F1 pace:
360&thinsp;km/h on the straight, 270&thinsp;km/h through a fast corner.
Every conclusion from the normal study inverts. Aero stops being
negligible and starts dominating; the useless wing becomes a monster;
and the maze corner turns out to be the one thing physics simply
forbids.</p>

<div class=tiles>
 <div class=tile><div class=k>Drag @ 360 km/h</div>
  <div class=v>__D_STR__ N</div><div class=n>__WR_STR__&times; the robot's
  own weight</div></div>
 <div class=tile><div class=k>Drag power</div>
  <div class=v>__P_STR__ kW</div><div class=n>vs a few watts from its
  motors</div></div>
 <div class=tile><div class=k>Drag deceleration</div>
  <div class=v>__DEC_STR__ g</div><div class=n>lift off the throttle and
  air alone hauls it down</div></div>
 <div class=tile><div class=k>Mach number</div>
  <div class=v>__M_STR__</div><div class=n>compressibility now real
  (+__PG_STR__% Cd)</div></div>
</div>

<section>
 <h2>1. On the straight, air becomes the dominant force</h2>
 <p>Drag scales with the square of speed, so going from 5&thinsp;m/s to
 100&thinsp;m/s multiplies it by 400. What was an ignorable
 29&thinsp;mN becomes __D_STR__&thinsp;N &mdash; more than five times the
 robot's weight, pushing back with __DEC_STR__&thinsp;g of deceleration
 and demanding __P_STR__&thinsp;kW just to hold speed.</p>
 <div class=card>__CHART_DRAG__</div>
 <div class=note>Two regime changes the low-speed model quietly assumed
 away: <strong>Reynolds number</strong> climbs to __RE_STR__ (genuinely
 turbulent, ~20&times; the micromouse's own), so the boundary layer and
 wake are now fully turbulent; and <strong>Mach number</strong> reaches
 __M_STR__ &mdash; past ~0.3 air can no longer be treated as
 incompressible, and even here a Prandtl-Glauert correction adds ~__PG_STR__%
 to Cd. The lattice-Boltzmann pictures in the main aero study are still
 topologically right (sharp-edged separation barely moves with Re) but
 the absolute forces would need a compressible solver.</div>
</section>

<section>
 <h2>2. The wing that was useless is suddenly a monster</h2>
 <p>At micromouse pace a wing made fractions of a milliNewton and we
 dismissed it. Downforce also scales with v&sup2;, and at
 270&thinsp;km/h the same surfaces come alive:</p>
 <div class=card>__CHART_DF__</div>
 <p>An F1-grade underbody would press this 220&thinsp;g robot into the
 floor with over __DF3__&thinsp;N &mdash; __DFW3__ times its weight. At
 low speed the required lift coefficient to matter was an absurd
 CL&nbsp;196; at F1 speed a perfectly ordinary CL&nbsp;3 does it. This is
 the whole reason downforce is an F1 obsession and a non-topic for small
 slow robots: it is a high-speed phenomenon, full stop.</p>
</section>

<section>
 <h2>3. ...but the corner is physically impossible</h2>
 <p>Here the hypothetical breaks against geometry. A micromouse corner is
 a 90&thinsp;mm radius. Holding that radius at 75&thinsp;m/s demands a
 centripetal acceleration of:</p>
 <div class=card><div style="font-size:34px;font-weight:700;
 color:var(--crit);letter-spacing:-.02em">62,500 m/s&sup2; = 6,370 g</div>
 <div style="color:var(--ink2);font-size:13.5px;margin-top:4px">
 v&sup2;/R with v = 75&thinsp;m/s, R = 0.09&thinsp;m</div></div>
 <p>No tyre, no downforce, no material survives thousands of g. Even
 giving the robot that monster F1 underbody &mdash; __DFW3__&times; its
 weight in grip &mdash; the fastest it could round a 90&thinsp;mm corner
 is about __VMAX3__&thinsp;m/s. To actually take a corner at
 75&thinsp;m/s you would need a radius of __RNEED__&thinsp;m
 (~__RNEED_CELLS__ maze cells) &mdash; which is exactly why F1 corners
 are tens of metres wide, not 9&thinsp;centimetres.</p>
 <div class="note warn"><strong>The real lesson of the whole aero
 series, in one line:</strong> aerodynamic force follows v&sup2; and
 needs SPEED to exist; cornering grip needs speed but the geometry needs
 SPACE. A micromouse has neither &mdash; so aero is irrelevant to it. An
 F1 car has both &mdash; so aero defines it. Same equations, opposite
 worlds; this robot can borrow F1's straight-line drag but never its
 corners.</div>
</section>

<footer>Hypothetical extrapolation of Gear/aero_study.py to
v&nbsp;=&nbsp;100 / 75&thinsp;m/s. Frontal area __AF__&thinsp;mm&sup2;,
plan __AP__&thinsp;mm&sup2; (rasterised from the CAD); Cd&nbsp;0.9, mass
220&thinsp;g, air at 20&thinsp;&deg;C. Drag/downforce from the standard
equation; corner limits from &radic;(&mu;gR(1+DF/W)) with
&mu;&nbsp;2.3. Compressibility flagged, not modelled &mdash; a true F1
CFD needs a compressible, fully-turbulent solver. See the main aero and
thermal artifacts for the real-speed analysis.</footer>
</div>
"""


def main(out):
    b = build()
    s = b["speeds"]
    st, co, W = s["straight"], s["corner"], b["W"]
    A_f = b["A_f"]; A_p = b["A_p"]
    fmt = lambda x, n=1: ("%." + str(n) + "f") % x

    chart_drag = bar_svg([
        ("5 m/s (micromouse)", s["ref"]["D"], "%.2f N" % s["ref"]["D"]),
        ("75 m/s (F1 corner)", co["D"], "%.1f N" % co["D"]),
        ("100 m/s (F1 straight)", st["D"], "%.1f N (%.1fx weight)"
         % (st["D"], st["D"]/W))],
        "N", st["D"]*1.15)

    df_items = []
    for name, CL, DF, dfw, vmax in b["wings"]:
        df_items.append(("%s (CL %.1f)" % (name, CL), DF,
                         "%.0f N = %.0fx weight" % (DF, dfw)))
    chart_df = bar_svg(df_items, "N", b["wings"][-1][2]*1.15, col="#199e70")

    DF3, DFW3, VMAX3 = b["wings"][-1][2], b["wings"][-1][3], b["wings"][-1][4]
    rep = {
        "__D_STR__": fmt(st["D"], 1), "__WR_STR__": fmt(st["wr"], 1),
        "__P_STR__": fmt(st["P"]/1000, 2), "__DEC_STR__": fmt(st["dec_g"], 1),
        "__M_STR__": fmt(st["M"], 2),
        "__PG_STR__": fmt(100*(1/math.sqrt(1-st["M"]**2)-1), 0),
        "__RE_STR__": "%.0e" % st["Re"],
        "__CHART_DRAG__": chart_drag, "__CHART_DF__": chart_df,
        "__DF3__": fmt(DF3, 0), "__DFW3__": fmt(DFW3, 0),
        "__VMAX3__": fmt(VMAX3, 1),
        "__RNEED__": fmt(b["r_nowing"], 0),
        "__RNEED_CELLS__": fmt(b["r_nowing"]/0.18, 0),
        "__AF__": fmt(A_f*1e6, 0), "__AP__": fmt(A_p*1e6, 0),
    }
    html = TEMPLATE
    for k, v in rep.items():
        html = html.replace(k, v)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d KB)" % (out, len(html)//1024))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(HERE, "web", "f1_speed.html"))
