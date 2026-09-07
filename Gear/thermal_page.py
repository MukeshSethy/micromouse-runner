"""
thermal_page.py - build the motor-thermal artifact page from
thermal_data.json + _thermal.png.

    python thermal_page.py <out.html>
"""

import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = """<title>Micromouse Thermals</title>
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
flex-direction:column;gap:22px}
.eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
color:var(--accent);font-weight:700}
h1{margin:.15em 0 0;font-size:clamp(24px,4vw,36px);letter-spacing:-.02em}
h2{margin:0;font-size:19px}
p{margin:0;max-width:70ch;color:var(--ink2)}
table{border-collapse:collapse;width:100%;font-size:13.5px;
font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:7px 9px;border-bottom:1px solid var(--rule)}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-size:11px;letter-spacing:.08em;
text-transform:uppercase;font-weight:600}
.scroll{overflow-x:auto}
img{width:100%;border-radius:8px;border:1px solid var(--rule);display:block}
.note{border-left:3px solid var(--accent);padding:10px 0 10px 14px;
font-size:13.5px;color:var(--ink2)}
.warn{border-left-color:var(--crit)}
footer{border-top:1px solid var(--rule);padding-top:12px;font-size:12.5px;
color:var(--muted);line-height:1.6}
code{font-family:ui-monospace,Consolas,monospace;font-size:.92em;
color:var(--ink)}
</style>
<div class=wrap>
<div><div class=eyebrow>micromouse 4wd &middot; motor thermals</div>
<h1>One run barely warms them. Continuous racing cooks them.</h1></div>
<p>Motor copper loss computed from the twin's own duty/speed history at
every 2&thinsp;ms step (winding current follows exactly from the sim's
torque model), clamped by a realistic H-bridge current limit, then fed
into a lumped thermal node per motor. No cooling credit is taken from
vehicle motion &mdash; the aero study showed airflow at these speeds is
negligible.</p>

<section>
<h2>The numbers</h2>
<div class=scroll><table>
<thead><tr><th>Regime</th><th>Avg loss / motor</th><th>Peak</th>
<th>One run heats by</th><th>Continuous steady-state</th>
<th>Time to 100&thinsp;&deg;C limit</th></tr></thead>
<tbody>__ROWS__</tbody>
</table></div>
</section>

<img src="data:image/png;base64,__IMG__"
 alt="Motor copper loss traces and temperature curves">

<section>
<h2>What it means</h2>
<p><strong>Single speed-runs are thermally free.</strong> A full
race-glue lap at 3&thinsp;m/s dumps ~24&thinsp;K into each winding;
a stock mission ~19&thinsp;K. Motors recover with a couple of minutes
of rest (thermal time constant &approx;&thinsp;3.8&thinsp;min).</p>
<p><strong>Continuous hard running is thermally impossible.</strong>
At racing intensity the motors average ~10&thinsp;W each against a
still-air dissipation budget of ~1.7&thinsp;W at the limit: back-to-back
missions cross 100&thinsp;&deg;C in about 40&thinsp;seconds. The
practical rule: hard run, then 2&ndash;3 minutes of cooldown &mdash;
which is how real competition sessions work anyway. For sustained
practice at speed you would need a real heat path (aluminium motor clamp
into a plate, or forced air), worth roughly a 3&ndash;5&times; lower
Rth.</p>
<p><strong>Where the heat actually comes from</strong> is not cruising
&mdash; near the back-EMF ceiling the current is small. It is the
accelerate/brake/corner cycle: every brake is plug-braking (reversed
duty against a spinning rotor), which without a driver limit would draw
up to 1.9&times; stall current. The H-bridge current limit is what caps
racing losses at ~12.5&thinsp;W bursts &mdash; pick your driver
accordingly.</p>
<div class="note warn"><strong>Two findings this study surfaced:</strong>
(1) the twin's aggressive tune leans on plug-braking torque that a real
driver will clamp &mdash; expect slightly longer real braking distances
than simulated, sized by your driver's current limit; (2) the race-glue
regime WEDGES on the mission return leg (2 hits, unrecoverable) &mdash;
a controller bug found because a wedged robot grinding at the current
limit lit up this analysis. Logged for a fix.</div>
</section>

<footer>Gear/thermal_study.py; currents from the twin's exact PI duty at
2&thinsp;ms steps; assumed constants (typical 6&thinsp;V N20 catalogue
values, stated not measured): stock winding 1.6&thinsp;A stall /
3.75&thinsp;&ohm;, high-RPM 3.0&thinsp;A / 2.0&thinsp;&ohm;; driver
limits 1.5 / 2.5&thinsp;A; per motor Rth 45&thinsp;K/W still air,
C 5&thinsp;J/K; ambient 25&thinsp;&deg;C; iron/brush losses neglected.
CFD airflow companion study: see the aero artifact.</footer>
</div>
"""


def main(out):
    img = base64.b64encode(
        open(os.path.join(HERE, "_thermal.png"), "rb").read()).decode()
    d = json.load(open(os.path.join(HERE, "thermal_data.json")))
    rows = []
    for name, v in d.items():
        if name == "assumptions":
            continue
        limit = ("%.1f min" % v["minutes_to_limit"]
                 if v["minutes_to_limit"] else "never")
        rows.append(
            "<tr><td>%s</td><td>%.1f W</td><td>%.1f W</td>"
            "<td>+%.0f K</td><td>%.0f &deg;C</td><td>%s</td></tr>"
            % (name, v["p_avg_W"], v["p_peak_W"], v["dT_one_run_K"],
               v["T_steady_C"], limit))
    html = (TEMPLATE.replace("__IMG__", img)
            .replace("__ROWS__", "".join(rows)))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d KB)" % (out, len(html)//1024))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(HERE, "web", "thermal.html"))
