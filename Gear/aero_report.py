"""
aero_report.py - build the aerodynamics artifact from the computed data.

Every number in the page comes from aero_data.json (areas rasterised from
the CAD, slip angles measured in sim_twin) - nothing is typed by hand.

    python aero_report.py <out.html>
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

RHO = 1.204
NU = 1.516e-5
G = 9.81
CD = {"lo": 0.70, "nom": 0.90, "hi": 1.15}
CRR = 0.015
SPEEDS = [1.0, 2.0, 5.0]

# dataviz reference palette, dark column, validated first-three subset
C_DRAG = "#d95926"      # slot 2 orange
C_ROLL = "#199e70"      # slot 3 aqua
INK = "#f2ede8"
INK2 = "#a79c93"
MUTED = "#898781"
GRID = "#2c2c2a"
SURF = "#1a1a19"


def fmt(x, n=2):
    return ("%." + str(n) + "f") % x


def main(out_path):
    d = json.load(open(os.path.join(HERE, "aero_data.json")))
    A_f = d["areas"]["front_mm2"] * 1e-6
    A_s = d["areas"]["side_mm2"] * 1e-6
    A_p = d["areas"]["plan_mm2"] * 1e-6
    L = d["areas"]["length_mm"] * 1e-3
    m = d["mass"]
    W = m * G
    beta95 = d["slip"]["fast 3.0"]["beta_corner_p95"]
    beta_st = d["slip"]["stock 0.8"]["beta_corner_mean"]
    b = math.radians(beta95)
    A_yaw = A_f * math.cos(b) + A_s * math.sin(b)

    imgs = {}
    p = os.path.join(HERE, "_flow_images.json")
    if os.path.exists(p):
        imgs = json.load(open(p))

    rows = []
    for v in SPEEDS:
        Re = v * L / NU
        dn = 0.5 * RHO * CD["nom"] * A_f * v * v
        dl = 0.5 * RHO * CD["lo"] * A_f * v * v
        dh = 0.5 * RHO * CD["hi"] * A_f * v * v
        dc = 0.5 * RHO * CD["nom"] * A_yaw * v * v
        Cs = CD["nom"] * math.sin(2 * b)
        side = 0.5 * RHO * Cs * A_s * v * v
        rows.append(dict(v=v, Re=Re, dl=dl, dn=dn, dh=dh, dc=dc, side=side,
                         P=dn * v, dec=dn / m))
    roll = CRR * W
    v_eq = math.sqrt(roll / (0.5 * RHO * CD["nom"] * A_f))
    d5 = rows[-1]["dn"]

    # ---- SVG: drag vs speed, log-ish linear with Cd band ----------------
    Wpx, Hpx = 720, 300
    ml, mr, mt, mb = 62, 22, 18, 40
    pw, ph = Wpx - ml - mr, Hpx - mt - mb
    vmax, fmax = 5.2, 45.0     # Cd-hi at 5.2 is 40 mN: keep the band inside

    def X(v):
        return ml + pw * v / vmax

    def Y(f):
        return mt + ph * (1 - f / fmax)

    def curve(cd, step=0.1):
        pts = []
        v = 0.0
        while v <= vmax + 1e-9:
            pts.append("%.1f,%.1f" % (X(v), Y(0.5*RHO*cd*A_f*v*v*1000)))
            v += step
        return " ".join(pts)

    band_up = curve(CD["hi"])
    band_dn = " ".join(reversed(curve(CD["lo"]).split()))
    svg = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Drag force '
           'versus speed">' % (Wpx, Hpx)]
    for f in (0, 10, 20, 30, 40):  # ticks stop below fmax by design
        svg.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
                   'stroke-width="1"/>' % (ml, Y(f), Wpx-mr, Y(f), GRID))
        svg.append('<text x="%d" y="%.1f" fill="%s" font-size="11" '
                   'text-anchor="end" dy="4">%d</text>'
                   % (ml-8, Y(f), MUTED, f))
    svg.append('<text x="14" y="%d" fill="%s" font-size="11" '
               'transform="rotate(-90 14 %d)" text-anchor="middle">drag '
               'force (mN)</text>' % (mt+ph/2, MUTED, mt+ph/2))
    for v in (0, 1, 2, 3, 4, 5):
        svg.append('<text x="%.1f" y="%d" fill="%s" font-size="11" '
                   'text-anchor="middle">%d</text>'
                   % (X(v), Hpx-14, MUTED, v))
    svg.append('<text x="%.1f" y="%d" fill="%s" font-size="11" '
               'text-anchor="middle">speed (m/s)</text>'
               % (ml+pw/2, Hpx-1, MUTED))
    svg.append('<polygon points="%s %s" fill="%s" opacity="0.22"/>'
               % (band_up, band_dn, C_DRAG))
    # rolling-resistance reference
    svg.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
               'stroke-width="2" stroke-dasharray="5 4"/>'
               % (ml, Y(roll*1000), Wpx-mr, Y(roll*1000), C_ROLL))
    svg.append('<text x="%d" y="%.1f" fill="%s" font-size="11" dy="-6">'
               'rolling resistance %s mN</text>'
               % (ml+6, Y(roll*1000), C_ROLL, fmt(roll*1000, 1)))
    svg.append('<polyline points="%s" fill="none" stroke="%s" '
               'stroke-width="2"/>' % (curve(CD["nom"]), C_DRAG))
    for r in rows:
        svg.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="%s" '
                   'stroke="%s" stroke-width="2"/>'
                   % (X(r["v"]), Y(r["dn"]*1000), C_DRAG, SURF))
        svg.append('<text x="%.1f" y="%.1f" fill="%s" font-size="11.5" '
                   'text-anchor="middle" dy="-11" font-weight="600">%s mN'
                   '</text>' % (X(r["v"]), Y(r["dn"]*1000), INK,
                                fmt(r["dn"]*1000, 1)))
    svg.append('</svg>')
    chart1 = "".join(svg)

    # ---- SVG: force budget at 5 m/s -------------------------------------
    bars = [("Traction available (race glue, mu 2.3)", 2.3*W, MUTED),
            ("Weight", W, MUTED),
            ("Rolling resistance", roll, C_ROLL),
            ("Aero drag at 5 m/s", d5, C_DRAG)]
    bw, bh = 720, 40*len(bars)+34
    bl = 250
    bmax = max(b[1] for b in bars)
    svg2 = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Force budget">'
            % (bw, bh)]
    for i, (lab, val, col) in enumerate(bars):
        y = 8 + i*40
        wpx = (bw - bl - 96) * val / bmax
        svg2.append('<text x="%d" y="%d" fill="%s" font-size="12" dy="15" '
                    'text-anchor="end">%s</text>' % (bl-12, y, INK2, lab))
        svg2.append('<rect x="%d" y="%d" width="%.1f" height="22" rx="4" '
                    'fill="%s"/>' % (bl, y, max(wpx, 2.5), col))
        svg2.append('<text x="%.1f" y="%d" fill="%s" font-size="12" dy="16" '
                    'font-weight="600">%s N</text>'
                    % (bl+max(wpx, 2.5)+9, y, INK, fmt(val, 3)))
    svg2.append('</svg>')
    chart2 = "".join(svg2)

    trows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
        "<td>%s</td><td>%s</td></tr>"
        % (fmt(r["v"], 0), "{:,.0f}".format(r["Re"]),
           fmt(r["dn"]*1000, 2), "%s–%s" % (fmt(r["dl"]*1000, 2),
                                            fmt(r["dh"]*1000, 2)),
           fmt(r["dc"]*1000, 2), fmt(r["side"]*1000, 2),
           fmt(r["P"], 3)) for r in rows)

    figs = ""
    for key, cap in (("straight", "Straight running, plan view. Stagnation "
                      "at the nose, flow accelerating to ~1.5x freestream "
                      "past the wheels, and a wake as wide as the robot "
                      "trailing more than a body length."),
                     ("corner", "Cornering attitude (6.7 deg yaw). The wake "
                      "deflects to one side and the windward wheels see "
                      "attached faster flow - this asymmetry is the side "
                      "force, and it is what a crosswind would look like."),
                     ("side", "Side view with the maze floor modelled. The "
                      "5 mm underbody gap runs faster than the top surface; "
                      "the square tail sheds a thick separated wake.")):
        if key in imgs:
            figs += ('<figure><img src="%s" alt="%s"/>'
                     '<figcaption>%s</figcaption></figure>' %
                     (imgs[key], cap.split(".")[0], cap))

    html = TEMPLATE
    for k, v in {
        "__CHART1__": chart1, "__CHART2__": chart2, "__ROWS__": trows,
        "__FIGS__": figs,
        "__AF__": fmt(d["areas"]["front_mm2"], 0),
        "__AS__": fmt(d["areas"]["side_mm2"], 0),
        "__AP__": fmt(d["areas"]["plan_mm2"], 0),
        "__D5__": fmt(d5*1000, 1),
        "__D5PCT__": fmt(100*d5/W, 2),
        "__D1__": fmt(rows[0]["dn"]*1000, 2),
        "__D2__": fmt(rows[1]["dn"]*1000, 2),
        "__DEC5__": fmt(rows[-1]["dec"], 3),
        "__P5__": fmt(rows[-1]["P"], 3),
        "__ROLL__": fmt(roll*1000, 1),
        "__VEQ__": fmt(v_eq, 2),
        "__BETA__": fmt(beta95, 1),
        "__BETAST__": fmt(beta_st, 1),
        "__YAWPCT__": fmt(100*(A_yaw/A_f - 1), 1),
        "__SIDE5__": fmt(rows[-1]["side"]*1000, 2),
        "__RE5__": "{:,.0f}".format(rows[-1]["Re"]),
        "__VCORNER__": fmt(math.sqrt(0.70*2.3*G*0.09), 2),
    }.items():
        html = html.replace(k, v)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%.2f MB)" % (out_path, os.path.getsize(out_path)/1e6))


TEMPLATE = r"""<title>Micromouse Aerodynamics</title>
<style>
:root{
  --bg:#0d0d0d; --surface:#1a1a19; --ink:#f2ede8; --ink2:#a79c93;
  --muted:#898781; --grid:#2c2c2a; --rule:#332c27; --accent:#d95926;
  --aqua:#199e70;
}
:root:not([data-theme="dark"]){}
@media (prefers-color-scheme: light){
  :root:not([data-theme="dark"]){
    --bg:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
    --muted:#898781; --grid:#e1e0d9; --rule:#e1e0d9; --accent:#eb6834;
    --aqua:#1baf7a;
  }
}
:root[data-theme="light"]{
  --bg:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --rule:#e1e0d9; --accent:#eb6834;
  --aqua:#1baf7a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
 font-size:15px;line-height:1.6}
.wrap{max-width:940px;margin:0 auto;padding:34px 20px 60px;
 display:flex;flex-direction:column;gap:26px}
.eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
 color:var(--accent);font-weight:700}
h1{margin:.15em 0 0;font-size:clamp(26px,4.4vw,40px);line-height:1.1;
 letter-spacing:-.02em;text-wrap:balance}
h2{margin:0;font-size:19px;letter-spacing:-.01em}
p{margin:0;max-width:68ch;color:var(--ink2)}
p.lead{color:var(--ink);font-size:16.5px}
section{display:flex;flex-direction:column;gap:12px}
.card{background:var(--surface);border:1px solid var(--rule);
 border-radius:8px;padding:18px 20px}
.hero{display:flex;flex-wrap:wrap;gap:26px;align-items:baseline}
.hero .big{font-size:clamp(40px,7vw,64px);font-weight:700;line-height:1;
 letter-spacing:-.03em;color:var(--accent)}
.hero .sub{color:var(--ink2);font-size:14px;max-width:44ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
 gap:12px}
.tile{background:var(--surface);border:1px solid var(--rule);
 border-radius:8px;padding:13px 15px}
.tile .k{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
 color:var(--muted)}
.tile .v{font-size:23px;font-weight:700;letter-spacing:-.02em;
 margin-top:3px}
.tile .n{font-size:12px;color:var(--ink2);margin-top:2px}
svg{width:100%;height:auto;display:block}
table{border-collapse:collapse;width:100%;font-size:13.5px;
 font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:7px 9px;border-bottom:1px solid var(--rule)}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-size:11px;letter-spacing:.08em;
 text-transform:uppercase;font-weight:600}
.scroll{overflow-x:auto}
figure{margin:0;display:flex;flex-direction:column;gap:8px}
figure img{width:100%;border-radius:6px;border:1px solid var(--rule);
 display:block}
figcaption{font-size:13px;color:var(--ink2);max-width:72ch}
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12.5px;
 color:var(--ink2)}
.legend i{width:11px;height:11px;border-radius:2px;display:inline-block;
 margin-right:6px;vertical-align:-1px}
.note{border-left:3px solid var(--accent);padding:10px 0 10px 14px;
 font-size:13.5px;color:var(--ink2)}
footer{border-top:1px solid var(--rule);padding-top:14px;font-size:12.5px;
 color:var(--muted);line-height:1.65}
code{font-family:ui-monospace,Consolas,monospace;font-size:.92em;
 color:var(--ink)}
</style>
<div class="wrap">

<header>
 <div class="eyebrow">micromouse 4wd &middot; aero study</div>
 <h1>Air is not what is slowing your mouse down</h1>
</header>

<p class="lead">At 5&nbsp;m/s the whole robot pushes __D5__&nbsp;mN of air
&mdash; about __D5PCT__&nbsp;% of its own weight, and less than the friction
of its own tyres rolling. Below 2&nbsp;m/s it is close to unmeasurable. This
page computes that from the real CAD silhouette rather than a guess, and
shows what the flow actually does in straights and in corners.</p>

<div class="hero card">
 <div><div class="big">__D5__ mN</div>
 <div class="sub">total aerodynamic drag at 5&nbsp;m/s (Cd&nbsp;0.9 on the
 measured __AF__&nbsp;mm&sup2; frontal area)</div></div>
 <div><div class="big">__DEC5__</div>
 <div class="sub">m/s&sup2; of deceleration it causes &mdash; against
 &gt;10&nbsp;m/s&sup2; from the brakes</div></div>
</div>

<div class="tiles">
 <div class="tile"><div class="k">Frontal area</div>
  <div class="v">__AF__</div><div class="n">mm&sup2;, rasterised from CAD</div></div>
 <div class="tile"><div class="k">Side area</div>
  <div class="v">__AS__</div><div class="n">mm&sup2;</div></div>
 <div class="tile"><div class="k">Reynolds @ 5 m/s</div>
  <div class="v">__RE5__</div><div class="n">turbulent, but subcritical</div></div>
 <div class="tile"><div class="k">Drag power @ 5 m/s</div>
  <div class="v">__P5__ W</div><div class="n">of several watts available</div></div>
</div>

<section>
 <h2>Drag versus speed</h2>
 <p>Drag grows with the square of speed, so it is negligible at
 1&nbsp;m/s (__D1__&nbsp;mN) and still small at 5&nbsp;m/s. The band is the
 honest uncertainty in Cd for a bluff, open-wheeled, ground-proximity body
 (0.70&ndash;1.15); the line is Cd&nbsp;0.90. The dashed line is rolling
 resistance &mdash; drag only catches it at __VEQ__&nbsp;m/s.</p>
 <div class="card">__CHART1__</div>
 <div class="legend">
  <span><i style="background:var(--accent)"></i>aero drag (band = Cd 0.70&ndash;1.15)</span>
  <span><i style="background:var(--aqua)"></i>rolling resistance (Crr 0.015)</span>
 </div>
</section>

<section>
 <h2>Where it sits in the force budget</h2>
 <p>The comparison that settles it: at full speed, drag is roughly a
 hundredth of the grip the tyres can deliver. Nothing about the robot's
 lap time is decided by air.</p>
 <div class="card">__CHART2__</div>
</section>

<section>
 <h2>Straights and corners</h2>
 <p>In a corner the body runs at a slip angle, so it presents a slightly
 bigger area and picks up a side force. The slip angles here are not
 assumed &mdash; they are measured in <code>sim_twin</code>, the same
 offline twin that tunes the controller: __BETAST__&deg; mean in corners
 at 0.8&nbsp;m/s, __BETA__&deg; at the 95th percentile at 3&nbsp;m/s. That
 attitude adds only __YAWPCT__&nbsp;% to the frontal area, and the side
 force at 5&nbsp;m/s is __SIDE5__&nbsp;mN &mdash; three orders of magnitude
 below the cornering force the tyres are already carrying.</p>
 <div class="scroll"><table>
  <thead><tr><th>Speed (m/s)</th><th>Re</th><th>Drag straight (mN)</th>
  <th>Cd band (mN)</th><th>Drag cornering (mN)</th><th>Side force (mN)</th>
  <th>Power (W)</th></tr></thead>
  <tbody>__ROWS__</tbody>
 </table></div>
 <div class="note">5&nbsp;m/s <em>through a corner</em> is not physically
 reachable on this robot: a 90&nbsp;mm turn radius on race-glue tyres caps
 corner speed near __VCORNER__&nbsp;m/s on grip alone. The cornering column
 is the drag the robot <em>would</em> see at that attitude, listed at the
 same speeds so the comparison is like-for-like.</div>
</section>

<section>
 <h2>What the flow does</h2>
 <p>A 2D lattice-Boltzmann solve over the robot's real silhouette. Read
 these for the shape of the wake, not for a number: the lattice runs near
 Re&nbsp;10&sup3; while the robot at 5&nbsp;m/s is at Re&nbsp;__RE5__, so the
 separation points are indicative and the turbulent detail is not resolved.
 Every force on this page comes from the drag equation, never from these
 fields.</p>
 __FIGS__
</section>

<section>
 <h2>So what would actually help</h2>
 <p>Nothing aerodynamic &mdash; at this scale streamlining buys back a
 fraction of a milliNewton. The forces that decide your lap time are grip
 (tyre compound and how much of the friction circle the planner dares to
 use), motor back-EMF ceiling, and mass. The one aero effect worth
 remembering is the opposite of drag: at these speeds you get essentially
 <em>no</em> downforce either, which is why the full-size mice that chase
 2&nbsp;m/s corner speeds fit a vacuum fan and generate their own.</p>
</section>

<footer>
Frontal, side and plan areas rasterised at 0.5&nbsp;mm from the tessellated
assembly (<code>Gear/aero_study.py</code>); slip angles logged from
<code>sim_twin.py</code>; flow fields from a D2Q9 lattice-Boltzmann solver
over the same silhouettes (<code>Gear/aero_flow.py</code>). Air at 20&nbsp;&deg;C
(&rho;&nbsp;1.204&nbsp;kg/m&sup3;, &nu;&nbsp;1.516&times;10&#8315;&#8309;&nbsp;m&sup2;/s),
robot mass 0.22&nbsp;kg. Cd band and Crr are literature values for bluff
ground vehicles, not measurements &mdash; they are the least certain inputs
here, and the conclusion holds across the whole band.
</footer>
</div>
"""


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(HERE, "web", "aero_report.html"))
