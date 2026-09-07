"""
f1_downforce_page.py - the designed downforce package for the micromouse
at F1 speed: geometry spec + downforce budget (literature coefficients on
plan area) + the LBM airflow fields (topology).

Force numbers use established automotive lift coefficients, NOT the 2D LBM
force integration - 2D with no tip losses over-predicts by ~10x and is
only trustworthy for TOPOLOGY (which is what the flow images show).

    python f1_downforce_page.py <out.html>
"""

import base64
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RHO, G, A_SND = 1.204, 9.81, 343.0
MU = 2.3
COR, STR = 75.0, 100.0

# designed package: literature CL referenced to PLAN area, per device
DEVICES = [
    ("Front splitter + dam", 0.5,
     "flat plate 30 mm forward of the nose, full 98 mm width, at floor "
     "level; stagnation high-pressure on top, suction beneath"),
    ("Sealed underbody + rear diffuser", 2.2,
     "full-length flat floor 3.5 mm off the road, 12&deg; diffuser ramp "
     "over the rear 45 mm (2.4:1 expansion) - the dominant device"),
    ("Rear wing (2-element)", 1.3,
     "90 mm span, 30 mm chord main + flap at -14&deg;/-26&deg; on "
     "endplates 36 mm above the deck"),
]
SKIRT = ("Side skirts", "flexible blades sealing both underbody edges to "
         "~1 mm off the road - what turns the ideal 2D underbody into a "
         "real one; without them the floor leaks and loses most of its "
         "suction")


def img_or_none(key):
    d = json.load(open(os.path.join(HERE, "aero_package.json")))
    return d.get("images", {}).get(key)


TEMPLATE = """<title>Micromouse F1 Downforce Package</title>
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
.wrap{max-width:940px;margin:0 auto;padding:34px 20px 60px;display:flex;
flex-direction:column;gap:24px}
.eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
color:var(--accent);font-weight:700}
h1{margin:.15em 0 0;font-size:clamp(24px,4.2vw,36px);letter-spacing:-.02em;
text-wrap:balance}
h2{margin:0;font-size:19px}
p{margin:0;max-width:72ch;color:var(--ink2)}
p.lead{color:var(--ink);font-size:16.5px}
section{display:flex;flex-direction:column;gap:12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
gap:12px}
.tile{background:var(--surface);border:1px solid var(--rule);
border-radius:8px;padding:13px 15px}
.tile .k{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
color:var(--muted)}
.tile .v{font-size:25px;font-weight:700;letter-spacing:-.02em;margin-top:3px;
color:var(--accent)}
.tile .n{font-size:12px;color:var(--ink2);margin-top:2px}
table{border-collapse:collapse;width:100%;font-size:13.5px;
font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--rule);
vertical-align:top}
td.n,th.n{text-align:right;white-space:nowrap}
th{color:var(--muted);font-size:11px;letter-spacing:.08em;
text-transform:uppercase;font-weight:600}
tr.tot td{font-weight:700;color:var(--ink);border-top:2px solid var(--rule)}
.scroll{overflow-x:auto}
figure{margin:0;display:flex;flex-direction:column;gap:7px}
figure img{width:100%;border-radius:8px;border:1px solid var(--rule);
display:block}
figcaption{font-size:13px;color:var(--ink2)}
.note{border-left:3px solid var(--accent);padding:10px 0 10px 14px;
font-size:13.5px;color:var(--ink2)}
.warn{border-left-color:var(--crit)}
footer{border-top:1px solid var(--rule);padding-top:12px;font-size:12.5px;
color:var(--muted);line-height:1.6}
</style>
<div class=wrap>
<header>
 <div class=eyebrow>micromouse 4wd &middot; F1-speed downforce package</div>
 <h1>Wings, diffuser and skirts &mdash; and the airflow that makes them
 work</h1>
</header>
<p class=lead>At 270&thinsp;km/h downforce is trivially easy to make: the
same v&sup2; that makes drag brutal makes a wing a monster. Here is a
concrete three-device package for the 120&thinsp;mm robot, the downforce
budget it produces, and the CFD airflow showing each device loaded.</p>

<div class=tiles>
 <div class=tile><div class=k>Total downforce @ 270 km/h</div>
  <div class=v>__DF_COR__ N</div><div class=n>__DFW_COR__&times; the
  robot's weight</div></div>
 <div class=tile><div class=k>@ 360 km/h straight</div>
  <div class=v>__DF_STR__ N</div><div class=n>__DFW_STR__&times; weight
  &mdash; pins it hard</div></div>
 <div class=tile><div class=k>Package CL (plan area)</div>
  <div class=v>__CLT__</div><div class=n>ground-effect car territory</div></div>
 <div class=tile><div class=k>Corner it unlocks @ 75 m/s</div>
  <div class=v>__RMIN__ m radius</div><div class=n>track-scale, not
  maze-scale</div></div>
</div>

<section>
 <h2>The package</h2>
 <div class=scroll><table>
 <thead><tr><th>Device</th><th class=n>C<sub>L</sub> (plan)</th>
 <th class=n>Downforce @ 270 km/h</th><th>Geometry &amp; function</th>
 </tr></thead><tbody>__ROWS__</tbody></table></div>
 <div class=note><strong>__SKIRT_NAME__:</strong> __SKIRT_DESC__.</div>
</section>

<section>
 <h2>CFD airflow at F1 speed</h2>
 <p>2D lattice-Boltzmann with a moving ground (a rolling road is
 mandatory &mdash; ground-effect suction does not exist over a static
 floor). Read these for topology: where the flow accelerates (low
 pressure = downforce) and how each device is loaded. The 2D solve is the
 perfectly-sealed-skirt case, so it flatters the underbody &mdash; the
 force numbers above come from literature coefficients, not from this.</p>
 __FIGS__
</section>

<section>
 <h2>Is it &ldquo;sufficient&rdquo;? Yes &mdash; spectacularly, and
 pointlessly</h2>
 <p>Because the robot weighs only 220&thinsp;g, even a modest package
 buries it under __DFW_COR__&times; its weight in downforce at corner
 speed. That is far past &ldquo;sufficient&rdquo; for traction: the tyres
 become the limit long before grip runs out. It unlocks genuinely fast
 cornering &mdash; a __RMIN__&thinsp;m-radius corner at 75&thinsp;m/s,
 which is a real racetrack sweeper.</p>
 <div class="note warn"><strong>But it cannot rescue the maze.</strong> A
 micromouse corner is 90&thinsp;mm, and holding that radius at
 75&thinsp;m/s needs 6,370&thinsp;g of centripetal force &mdash; no
 downforce touches that (grip gives lateral&nbsp;g, not the
 thousands&nbsp;g the geometry demands). This package would let the robot
 corner fast on a 3&ndash;4&thinsp;m racetrack radius; through a 9&thinsp;cm
 maze turn it is still, physically, a straight-line-only device. Downforce
 buys grip; only a bigger corner buys the corner.</div>
</section>

<footer>Geometry designed for the 120&times;98&times;27&thinsp;mm robot;
downforce from the standard equation with literature plan-area lift
coefficients (splitter 0.5, sealed underbody+diffuser 2.2, 2-element wing
1.3) at &rho;&nbsp;1.204&thinsp;kg/m&sup3;, plan area
__AP__&thinsp;mm&sup2;, mass 220&thinsp;g; corner radius from
&radic;(&mu;gR(1+DF/W)), &mu;&nbsp;2.3. Airflow: Gear/aero_package.py
(D2Q9 LBM, moving ground, momentum-exchange - topology only, lattice
Re&nbsp;~&nbsp;1e3). The measured 2D coefficients over-predict ~10&times;
and are not used for the force budget.</footer>
</div>
"""


def main(out):
    d = json.load(open(os.path.join(HERE, "aero_data.json")))
    A_p = d["areas"]["plan_mm2"]*1e-6
    W = 0.22*G
    q_cor = 0.5*RHO*COR*COR
    q_str = 0.5*RHO*STR*STR
    CLt = sum(cl for _, cl, _ in DEVICES)
    DF_cor = CLt*q_cor*A_p
    DF_str = CLt*q_str*A_p
    Rmin = COR*COR/(MU*G*(1+DF_cor/W))

    rows = []
    for name, cl, desc in DEVICES:
        rows.append("<tr><td>%s</td><td class=n>%.1f</td>"
                    "<td class=n>%.0f N</td><td>%s</td></tr>"
                    % (name, cl, cl*q_cor*A_p, desc))
    rows.append("<tr class=tot><td>Full package</td><td class=n>%.1f</td>"
                "<td class=n>%.0f N (%.0f&times; W)</td>"
                "<td>splitter + floor + wing, skirt-sealed</td></tr>"
                % (CLt, DF_cor, DF_cor/W))

    figs = ""
    for key, cap in (("pkg_bare", "Bare robot at 270 km/h: flow rides "
                      "over the top, a broad low-energy wake trails the "
                      "tail, and the underbody is just a leaky gap."),
                     ("pkg_full", "Full package: the sealed undertray "
                      "accelerates flow beneath the body (bright band = "
                      "suction = downforce), the diffuser expands it up "
                      "into the base, and the rear wing loads its own "
                      "wake above.")):
        im = img_or_none(key)
        if im:
            figs += ('<figure><img src="%s" alt="%s"><figcaption>%s'
                     "</figcaption></figure>" % (im, cap.split(":")[0], cap))

    rep = {
        "__DF_COR__": "%.0f" % DF_cor, "__DFW_COR__": "%.0f" % (DF_cor/W),
        "__DF_STR__": "%.0f" % DF_str, "__DFW_STR__": "%.0f" % (DF_str/W),
        "__CLT__": "%.1f" % CLt, "__RMIN__": "%.1f" % Rmin,
        "__ROWS__": "".join(rows), "__FIGS__": figs,
        "__SKIRT_NAME__": SKIRT[0], "__SKIRT_DESC__": SKIRT[1],
        "__AP__": "%.0f" % (A_p*1e6),
    }
    html = TEMPLATE
    for k, v in rep.items():
        html = html.replace(k, v)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d KB)" % (out, len(html)//1024))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(HERE, "web", "f1_downforce.html"))
