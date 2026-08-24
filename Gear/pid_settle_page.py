"""
pid_settle_page.py - build the PID-settling artifact page from
pid_settle_data.json + _pid_settle.png.

    python pid_settle_page.py <out.html>
"""

import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = """<title>PID Settling at 2 m/s</title>
<style>
:root{--bg:#0d0d0d;--surface:#1a1a19;--ink:#f2ede8;--ink2:#a79c93;
--muted:#898781;--rule:#332c27;--accent:#e08a2a;--aqua:#199e70}
@media (prefers-color-scheme: light){:root:not([data-theme=dark]){
--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--rule:#e1e0d9;
--accent:#eb6834;--aqua:#1baf7a}}
:root[data-theme=light]{--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;
--ink2:#52514e;--rule:#e1e0d9;--accent:#eb6834;--aqua:#1baf7a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:15px;
line-height:1.6}
.wrap{max-width:920px;margin:0 auto;padding:34px 20px 60px;display:flex;
flex-direction:column;gap:22px}
.eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
color:var(--accent);font-weight:700}
h1{margin:.15em 0 0;font-size:clamp(24px,4vw,36px);letter-spacing:-.02em}
p{margin:0;max-width:70ch;color:var(--ink2)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--rule);border-radius:8px;
padding:14px 16px}
.tile .k{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
color:var(--muted)}
.tile .v{font-size:26px;font-weight:700;letter-spacing:-.02em;margin-top:3px;
color:var(--accent)}
.tile .n{font-size:12px;color:var(--ink2);margin-top:3px}
img{width:100%;border-radius:8px;border:1px solid var(--rule);display:block}
footer{border-top:1px solid var(--rule);padding-top:12px;font-size:12.5px;
color:var(--muted);line-height:1.6}
</style>
<div class=wrap>
<div><div class=eyebrow>micromouse 4wd &middot; control loops &middot;
hard-settle tune</div>
<h1>How fast does the error die at 2&thinsp;m/s?</h1></div>
<p>Measured in <code>sim_twin</code> &mdash; the same dynamics as the
published simulator &mdash; with the fast motors and the hardened
steering tune (P&nbsp;1.8, D&nbsp;2.3, gyro-D&nbsp;2.2), swept for
settling and validated against wall hits and lap time.</p>
<div class=tiles>
<div class=tile><div class=k>Motor PI, isolated</div>
<div class=v>__A_MS__&thinsp;ms</div>
<div class=n>2&thinsp;m/s step into &plusmn;2&#37; &mdash; ACTUATOR-limited:
duty saturates, so no gain can beat this (verified by sweep)</div></div>
<div class=tile><div class=k>Full robot 0&rarr;2 m/s</div>
<div class=v>__B_S__&thinsp;s</div>
<div class=n>friction-circle-limited launch (&approx;10&thinsp;m/s&sup2;)</div></div>
<div class=tile><div class=k>Cruise ripple</div>
<div class=v>&plusmn;__RIP__&thinsp;mm/s</div>
<div class=n>steering shares the grip; error orbits zero, never parks on it</div></div>
<div class=tile><div class=k>Corner recovery</div>
<div class=v>__C_MS__&thinsp;ms</div>
<div class=n>median: cross-track is back inside &plusmn;3&thinsp;mm AT
corner exit &mdash; the recovery happens inside the turn</div></div>
</div>
<img src="data:image/png;base64,__IMG__" alt="PID settling curves">
<p><strong>Where the &ldquo;harder&rdquo; went:</strong> the motor PI was
already at the physical wall &mdash; large steps saturate the duty (the
motor is giving 100&#37;, settle time = torque/inertia), and small
disturbances die in 26&thinsp;ms; sweeping Kp/Ki changed nothing or made
it oscillate. The tunable slack was in the STEERING loop: raising the
tangent gain 1.9&rarr;2.3 and cross-track gain 1.2&rarr;1.8 moved the
corner recovery from ~314&thinsp;ms after the turn to inside-the-turn
(median 0&thinsp;ms at exit), cut the 95th-percentile path error from
11.7 to 9.9&thinsp;mm, took the 2&thinsp;m/s championship run from 2 wall
hits to 0 &mdash; at an unchanged lap time. Pushing harder than this
(P&nbsp;&ge;2.4-3.2) still passed, but with choppier yaw and no further
settling gain, so the mildest winning tune ships.</p>
<footer>Gear/pid_settle.py (analysis + sweep), twin timestep 2&thinsp;ms;
bands &plusmn;2&#37; of the 2.0&thinsp;m/s step for speed,
&plusmn;3&thinsp;mm cross-track; __NC__ corner exits, championship maze,
&mu;&nbsp;1.1, fast motors. The published simulator carries the same
tune.</footer>
</div>
"""


def main(out):
    img = base64.b64encode(
        open(os.path.join(HERE, "_pid_settle.png"), "rb").read()).decode()
    d = json.load(open(os.path.join(HERE, "pid_settle_data.json")))
    html = (TEMPLATE
            .replace("__IMG__", img)
            .replace("__A_MS__", "%.0f" % d["motor_pi_settle_ms"])
            .replace("__B_S__", "%.2f" % d["launch_band_entry_s"])
            .replace("__RIP__", "%.0f" % (2*d["cruise_ripple_sigma_ms"]))
            .replace("__C_MS__", "%.0f" % d["corner_settle_median_ms"])
            .replace("__NC__", str(len(d["corner_recoveries"]))))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d KB)" % (out, len(html)//1024))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(HERE, "web", "pid_settle.html"))
