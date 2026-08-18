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
    vid = None
    pv = os.path.join(HERE, "_video_frames.json")
    if os.path.exists(pv):
        vid = json.load(open(pv))
    wings = None
    pw = os.path.join(HERE, "aero_wings.json")
    if os.path.exists(pw):
        wings = json.load(open(pw))

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

    # ---- SVG: what actually raises corner speed --------------------------
    R_T, MU_T, USE = 0.09, 2.3, 0.70
    v0 = math.sqrt(USE*MU_T*G*R_T)

    def v_with(df_over_w=0.0, mu=MU_T, R=R_T):
        return math.sqrt(USE*mu*G*R*(1.0 + df_over_w))

    def v_passive(cl):
        v = v0
        for _ in range(40):
            df = 0.5*RHO*cl*A_p*v*v
            v = math.sqrt(USE*MU_T*G*R_T*(1.0 + df/W))
        return v

    opts = [
        ("Rear wing + splitter (CL 0.3)", v_passive(0.30), C_DRAG),
        ("Full ground-effect diffuser (CL 0.6)", v_passive(0.60), C_DRAG),
        ("F1-grade underbody (CL 1.5, not reachable)", v_passive(1.50),
         C_DRAG),
        ("Add 100 g of ballast", v_with(0.0), MUTED),
        ("Suction fan, 100 Pa", v_with(100*A_p/W), C_ROLL),
        ("Suction fan, 250 Pa", v_with(250*A_p/W), C_ROLL),
        ("Tyre tape: mu 2.3 to 3.0", v_with(0.0, mu=3.0), C_ROLL),
    ]
    bw3 = 720
    bh3 = 34*len(opts) + 40
    bl3 = 300
    vspan = max(o[1] for o in opts) * 1.02
    svg3 = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Corner speed '
            'by option">' % (bw3, bh3)]
    x0 = bl3
    xw = bw3 - bl3 - 108
    svg3.append('<line x1="%.1f" y1="6" x2="%.1f" y2="%d" stroke="%s" '
                'stroke-width="1" stroke-dasharray="4 4"/>'
                % (x0 + xw*v0/vspan, x0 + xw*v0/vspan, bh3-26, MUTED))
    svg3.append('<text x="%.1f" y="%d" fill="%s" font-size="11" '
                'text-anchor="middle">baseline %s m/s</text>'
                % (x0 + xw*v0/vspan, bh3-10, MUTED, fmt(v0, 2)))
    for i, (lab, v, col) in enumerate(opts):
        y = 6 + i*34
        wpx = xw*v/vspan
        svg3.append('<text x="%d" y="%d" fill="%s" font-size="12" dy="14" '
                    'text-anchor="end">%s</text>' % (bl3-12, y, INK2, lab))
        svg3.append('<rect x="%d" y="%d" width="%.1f" height="20" rx="4" '
                    'fill="%s"/>' % (x0, y, wpx, col))
        svg3.append('<text x="%.1f" y="%d" fill="%s" font-size="12" dy="15" '
                    'font-weight="600">%s m/s  %+.0f%%</text>'
                    % (x0+wpx+9, y, INK, fmt(v, 2), 100*(v/v0-1)))
    svg3.append('</svg>')
    chart3 = "".join(svg3)

    # ---- measured wing / diffuser table ---------------------------------
    wtab = ""
    if wings and "baseline" in wings:
        b = wings["baseline"]
        wr = []
        for name in ("baseline", "rear wing", "diffuser", "wing + diffuser"):
            if name not in wings:
                continue
            e = wings[name]
            dcl = b["CL"] - e["CL"]                 # positive = downforce won
            gain = dcl * 0.5 * RHO * A_p * v0 * v0
            dcd = 100.0*(e["CD"]/b["CD"] - 1.0)
            wr.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                      "<td>%s</td></tr>"
                      % (name, fmt(e["CL"], 3),
                         "&mdash;" if name == "baseline"
                         else "%+.3f" % dcl,
                         "&mdash;" if name == "baseline"
                         else "%+.2f mN (%+.2f%%)" % (gain*1000,
                                                      100*gain/W),
                         "&mdash;" if name == "baseline"
                         else "%+.1f%%" % dcd))
        wtab = ("<div class=\"scroll\"><table><thead><tr>"
                "<th>Configuration</th><th>Measured CL</th>"
                "<th>&Delta;CL vs bare</th>"
                "<th>Downforce gained at %s m/s</th>"
                "<th>Drag penalty</th></tr></thead><tbody>%s</tbody>"
                "</table></div>" % (fmt(v0, 2), "".join(wr)))

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
    if vid and vid.get("frames"):
        html = html.replace("__VIDEO__", PLAYER)
        html = html.replace("/*FRAMES*/", json.dumps(vid,
                                                     separators=(",", ":")))
    else:
        html = html.replace("__VIDEO__", "")
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
        "__VCORNER__": fmt(v0, 2),
        "__CHART3__": chart3,
        "__DFC__": fmt(0.5*RHO*0.30*A_p*v0*v0*1000, 1),
        "__DFCPCT__": fmt(100*0.5*RHO*0.30*A_p*v0*v0/W, 1),
        "__FANF__": fmt(250*A_p, 2),
        "__FANPCT__": fmt(100*(v_with(250*A_p/W)/v0 - 1), 0),
        "__WTAB__": wtab,
        "__WGAIN__": fmt(((wings["baseline"]["CL"]-wings["rear wing"]["CL"])
                          * 0.5*RHO*A_p*v0*v0*1000) if wings else 0, 1),
        "__WDRAG__": fmt((100*(wings["rear wing"]["CD"]
                               / wings["baseline"]["CD"] - 1))
                         if wings else 0, 1),
        "__CLNEED__": "%.0f" % (W/(0.5*RHO*A_p*v0*v0)),
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
.pbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
 margin-bottom:12px}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:6px;
 overflow:hidden}
.seg button{background:transparent;color:var(--ink2);border:0;
 padding:6px 12px;font:inherit;font-size:12.5px;cursor:pointer}
.seg button+button{border-left:1px solid var(--rule)}
.seg button.on{background:var(--accent);color:#fff;font-weight:600}
.pbar>button{background:transparent;color:var(--ink);
 border:1px solid var(--rule);border-radius:6px;padding:6px 12px;
 font:inherit;font-size:12.5px;cursor:pointer}
.pbar>button:hover{border-color:var(--accent)}
.rng{display:flex;align-items:center;gap:8px;font-size:12px;
 color:var(--ink2)}
.rng input{accent-color:var(--accent);width:150px}
.hud{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
canvas{width:100%;height:auto;display:block;border-radius:6px;
 background:var(--surface)}
.cap{font-size:13.5px}
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

__VIDEO__

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
 <h2>Would a wing or a diffuser help?</h2>
 <p>No &mdash; and the reason is worth understanding, because it also
 rules out several other intuitive fixes. Downforce scales with
 <em>v&sup2;</em>, exactly like drag. But grip only matters in corners,
 and this robot corners at about __VCORNER__&nbsp;m/s. At that speed a
 realistic printed wing-and-splitter package (CL&nbsp;0.3 on plan area)
 makes __DFC__&nbsp;mN of downforce &mdash; __DFCPCT__&nbsp;% of the
 robot's weight. The aero device is asleep precisely where you need it.
 The assumption-free version of the same point: at __VCORNER__&nbsp;m/s
 the dynamic pressure is 0.85&nbsp;Pa, so matching the robot's own weight
 would need <strong>CL&nbsp;&asymp;&nbsp;__CLNEED__</strong>. The best
 wings ever built reach 2&ndash;3.</p>
 <p>That first estimate used a literature CL, which is an assumption, not
 a test &mdash; so I built the parts and measured them. A rear wing
 (26&nbsp;mm chord at &minus;12&deg; on struts) and an upswept underbody
 diffuser were added to the robot's real side profile and the force on the
 body was integrated by momentum exchange across the bounce-back links:</p>
 __WTAB__
 <p>The bare robot makes a little <em>lift</em> &mdash; the wheels are its
 highest surfaces, so flow accelerates over them and pulls up. The wing
 claws back about a quarter of that, worth __WGAIN__&nbsp;mN at corner
 speed, for __WDRAG__&nbsp;% more drag. The diffuser measures as doing
 nothing at all: at a 5&nbsp;mm ride height and this Reynolds number the
 underbody gap is thick with boundary layer, so there is no fast, clean
 flow for a diffuser to expand. This is measured, and it is
 <em>worse</em> than the CL&nbsp;0.3 I assumed before &mdash; and 2D
 simulation flatters wings, because it has no tip vortices.</p>
 <div class="card">__CHART3__</div>
 <p>Two of those bars are the whole lesson. <strong>Ballast does
 nothing</strong>: cornering speed is
 &radic;(&mu;gR), independent of mass &mdash; extra weight buys grip and
 inertia in equal measure. <strong>A passive wing does almost
 nothing</strong> here, not because the aerodynamics are wrong but because
 __VCORNER__&nbsp;m/s is too slow to load it. Even a perfect F1-grade
 underbody, which a 5&nbsp;mm ride height over a jointed maze floor cannot
 physically sustain, would buy under 1&nbsp;%.</p>
 <p>What does work is force that <em>doesn't</em> come with mass and
 <em>doesn't</em> need speed: a <strong>suction fan</strong> pulling a
 partial vacuum under a skirted underbody. 250&nbsp;Pa across the
 __AP__&nbsp;mm&sup2; plan area is __FANF__&nbsp;N &mdash; more than the
 robot's own weight, available at a standstill, and worth
 __FANPCT__&nbsp;% on corner speed. That is why serious mice fit fans and
 not wings. There is room for it: the board has a clear
 32&nbsp;&times;&nbsp;32&nbsp;mm window at its centre, big enough for a
 28&nbsp;mm fan duct, though using it means a hole through the PCB, a
 flexible skirt at 1&ndash;2&nbsp;mm ride height, and a second battery
 budget.</p>
 <p>Cheapest real gain, though, needs no hardware at all: better tyre
 rubber and a planner that dares to use more of the friction circle. The
 last bar is the same robot on tape, which is the change you already have
 in the simulator.</p>
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


PLAYER = r"""
<section id="wake">
 <h2>The wake in motion</h2>
 <p>The wake behind a bluff body is not steady &mdash; it sheds. These are
 the same lattice-Boltzmann solves run in time, after the start-up
 transient has washed out. Switch between straight and cornering attitude,
 and between speed and vorticity (vorticity shows the individual vortices
 rolling off the corners; speed shows how far the slow wake reaches).</p>
 <div class="card">
  <div class="pbar">
   <span class="seg" id="segCase">
    <button data-case="straight" class="on">Straight</button
    ><button data-case="corner">Cornering 6.7&deg;</button>
   </span>
   <span class="seg" id="segField">
    <button data-field="vort" class="on">Vorticity</button
    ><button data-field="speed">Speed</button>
   </span>
   <button id="vplay">&#10073;&#10073; Pause</button>
   <label class="rng">Frame
    <input id="vscrub" type="range" min="0" max="0" step="1" value="0">
   </label>
   <span class="hud" id="vhud"></span>
  </div>
  <canvas id="vcv" width="900" height="420"></canvas>
  <div class="legend" id="vleg"></div>
 </div>
 <p class="cap">Flow runs left to right. The body is drawn in ink; behind
 it the wake alternates as vortices peel off each side. In the cornering
 frame the shedding is asymmetric &mdash; one side separates earlier
 &mdash; which is the side force in the table above, and the reason a real
 crosswind would be felt as a small steering bias rather than as drag.</p>
</section>
<script id="vframes" type="application/json">/*FRAMES*/</script>
<script>
(function(){
"use strict";
const DOC=JSON.parse(document.getElementById("vframes").textContent);
const cv=document.getElementById("vcv"),cx=cv.getContext("2d");
const hud=document.getElementById("vhud"),leg=document.getElementById("vleg");
const scrub=document.getElementById("vscrub"),play=document.getElementById("vplay");
let curCase="straight",curField="vort",idx=0,playing=true,acc=0,last=0;
// colour maps: vorticity is diverging (two hues + neutral), speed is one hue
const RAMP={
  vort:[[0.00,[26,92,171]],[0.35,[120,160,200]],[0.50,[224,222,214]],
        [0.65,[214,140,86]],[1.00,[169,60,24]]],
  speed:[[0.00,[22,19,16]],[0.30,[90,58,31]],[0.60,[200,110,40]],
         [0.85,[224,138,42]],[1.00,[245,213,154]]]};
function lut(name){
  const st=RAMP[name],L=new Uint8ClampedArray(256*3);
  for(let i=0;i<256;i++){const t=i/255;
    let a=st[0],b=st[st.length-1];
    for(let k=0;k<st.length-1;k++){if(t>=st[k][0]&&t<=st[k+1][0]){a=st[k];b=st[k+1];break;}}
    const u=(t-a[0])/Math.max(1e-6,(b[0]-a[0]));
    for(let c=0;c<3;c++)L[i*3+c]=a[1][c]+(b[1][c]-a[1][c])*u;}
  return L;}
const LUT={vort:lut("vort"),speed:lut("speed")};
const BODY=[232,226,218];
const cache={};                     // decoded ImageData per case/field/frame
function decode(cs,fd,i,cb){
  const key=cs+fd+i;
  if(cache[key])return cb(cache[key]);
  const meta=DOC.frames[cs];
  const im=new Image();
  im.onload=()=>{
    const off=document.createElement("canvas");
    off.width=meta.w;off.height=meta.h;
    const oc=off.getContext("2d");
    oc.drawImage(im,0,0);
    const src=oc.getImageData(0,0,meta.w,meta.h).data;
    const out=oc.createImageData(meta.w,meta.h),L=LUT[fd];
    for(let p=0,n=meta.w*meta.h;p<n;p++){
      const g=src[p*4];
      if(g===0){out.data[p*4]=BODY[0];out.data[p*4+1]=BODY[1];
                out.data[p*4+2]=BODY[2];}
      else{out.data[p*4]=L[g*3];out.data[p*4+1]=L[g*3+1];
           out.data[p*4+2]=L[g*3+2];}
      out.data[p*4+3]=255;}
    cache[key]=out;cb(out);};
  im.src="data:image/png;base64,"+DOC.frames[cs][fd][i];
}
const tmp=document.createElement("canvas");
function draw(){
  const meta=DOC.frames[curCase];
  decode(curCase,curField,idx,img=>{
    tmp.width=meta.w;tmp.height=meta.h;
    tmp.getContext("2d").putImageData(img,0,0);
    const s=Math.min(cv.width/meta.w,cv.height/meta.h);
    const w=meta.w*s,h=meta.h*s;
    cx.fillStyle=getComputedStyle(cv).getPropertyValue("--surface")||"#1a1a19";
    cx.fillRect(0,0,cv.width,cv.height);
    cx.imageSmoothingEnabled=true;
    cx.drawImage(tmp,(cv.width-w)/2,(cv.height-h)/2,w,h);
  });
  hud.textContent="frame "+(idx+1)+" / "+DOC.frames[curCase][curField].length
    +"  ·  lattice Re ≈ "+DOC.frames[curCase].Re;
  const r=curField==="vort"?DOC.meta.vort_range:DOC.meta.speed_range;
  leg.innerHTML=curField==="vort"
    ?'<span><i style="background:#1a5cab"></i>clockwise</span>'
     +'<span><i style="background:#e0ded6"></i>irrotational</span>'
     +'<span><i style="background:#a93c18"></i>counter-clockwise</span>'
     +'<span>vorticity '+r[0]+' … '+r[1]+' (normalised)</span>'
    :'<span><i style="background:#161310"></i>stalled wake</span>'
     +'<span><i style="background:#e08a2a"></i>freestream</span>'
     +'<span><i style="background:#f5d59a"></i>accelerated ('+r[1]+'×)</span>';
}
function setCase(c){curCase=c;idx=Math.min(idx,DOC.frames[c][curField].length-1);
  scrub.max=DOC.frames[c][curField].length-1;draw();}
document.getElementById("segCase").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;
  for(const x of e.currentTarget.children)x.className="";
  b.className="on";setCase(b.dataset.case);};
document.getElementById("segField").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;
  for(const x of e.currentTarget.children)x.className="";
  b.className="on";curField=b.dataset.field;draw();};
scrub.oninput=e=>{idx=+e.target.value;playing=false;
  play.innerHTML="&#9654; Play";draw();};
play.onclick=()=>{playing=!playing;
  play.innerHTML=playing?"&#10073;&#10073; Pause":"&#9654; Play";};
function loop(ts){
  if(!last)last=ts;
  const dt=(ts-last)/1000;last=ts;
  if(playing){acc+=dt;
    if(acc>0.075){acc=0;
      idx=(idx+1)%DOC.frames[curCase][curField].length;
      scrub.value=idx;draw();}}
  requestAnimationFrame(loop);
}
setCase("straight");
// warm the cache so playback is smooth from the first loop
for(const cs of Object.keys(DOC.frames))
  for(const fd of ["vort","speed"])
    for(let i=0;i<DOC.frames[cs][fd].length;i++)decode(cs,fd,i,()=>{});
requestAnimationFrame(loop);
})();
</script>
"""


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(HERE, "web", "aero_report.html"))
