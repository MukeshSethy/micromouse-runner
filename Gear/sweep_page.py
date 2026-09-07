"""
sweep_page.py - interactive 0..300 km/h airflow sweep. A slider (or play
button) sweeps speed; the flow image snaps to the nearest computed rung
and the force/regime numbers update live from the exact v^2 relations.

    python sweep_page.py <out.html>
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(out):
    sweep = json.load(open(os.path.join(HERE, "_sweep.json")))
    d = json.load(open(os.path.join(HERE, "aero_data.json")))
    consts = {
        "A_f": d["areas"]["front_mm2"]*1e-6,
        "A_p": d["areas"]["plan_mm2"]*1e-6,
        "L": d["areas"]["length_mm"]*1e-3,
        "rho": 1.204, "nu": 1.516e-5, "a_snd": 343.0,
        "m": 0.22, "g": 9.81, "Cd": 0.9, "CLpkg": 4.0, "mu": 2.3,
        "Rmaze": 0.09,
    }
    payload = json.dumps({"sweep": sweep, "consts": consts},
                         separators=(",", ":"))
    html = TEMPLATE.replace("/*DATA*/", payload)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%.2f MB)" % (out, os.path.getsize(out)/1e6))


TEMPLATE = r"""<title>Micromouse Airflow 0-300 km/h</title>
<style>
:root{--bg:#0d0d0d;--surface:#1a1a19;--ink:#f2ede8;--ink2:#a79c93;
--muted:#898781;--rule:#332c27;--accent:#e08a2a;--aqua:#199e70;
--crit:#d03b3b}
@media (prefers-color-scheme: light){:root:not([data-theme=dark]){
--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--rule:#e1e0d9;
--accent:#eb6834;--aqua:#1baf7a}}
:root[data-theme=light]{--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;
--ink2:#52514e;--rule:#e1e0d9;--accent:#eb6834;--aqua:#1baf7a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:15px;
line-height:1.6}
.wrap{max-width:940px;margin:0 auto;padding:30px 20px 60px;display:flex;
flex-direction:column;gap:18px}
.eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
color:var(--accent);font-weight:700}
h1{margin:.1em 0 0;font-size:clamp(22px,3.6vw,32px);letter-spacing:-.02em}
p{margin:0;max-width:72ch;color:var(--ink2)}
.stage{background:var(--surface);border:1px solid var(--rule);
border-radius:10px;padding:16px;display:flex;flex-direction:column;gap:14px}
canvas{width:100%;height:auto;display:block;border-radius:6px;
background:#161310}
.speedrow{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.bignum{font-size:clamp(34px,7vw,60px);font-weight:800;letter-spacing:-.03em;
color:var(--accent);font-variant-numeric:tabular-nums;line-height:1}
.bignum small{font-size:.34em;color:var(--ink2);font-weight:600;
letter-spacing:0}
.ctl{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.ctl input[type=range]{flex:1;min-width:200px;accent-color:var(--accent)}
button{background:#262019;color:var(--ink);border:1px solid var(--rule);
border-radius:6px;padding:8px 16px;font:inherit;font-size:13px;
cursor:pointer}
button:hover{border-color:var(--accent)}
button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
gap:10px}
.tile{background:var(--bg);border:1px solid var(--rule);border-radius:8px;
padding:11px 13px}
.tile .k{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;
color:var(--muted)}
.tile .v{font-size:20px;font-weight:700;letter-spacing:-.02em;margin-top:2px;
font-variant-numeric:tabular-nums}
.tile .n{font-size:11.5px;color:var(--ink2);margin-top:1px}
.regime{font-size:13px;color:var(--ink2)}
.regime b{color:var(--accent)}
footer{border-top:1px solid var(--rule);padding-top:12px;font-size:12px;
color:var(--muted);line-height:1.6}
</style>
<div class=wrap>
<div><div class=eyebrow>micromouse 4wd &middot; airflow sweep</div>
<h1>The flow from 0 to 300 km/h</h1></div>
<p>Drag and downforce follow speed&sup2; exactly, so the numbers below are
computed live. The flow picture is a lattice-Boltzmann ladder: as speed
rises the wake goes from attached and quiet to an unsteady, turbulent
shed &mdash; drag the slider or press play.</p>

<div class=stage>
 <div class=speedrow>
  <div class=bignum id=spd>0<small>km/h</small></div>
  <div class=regime id=reg></div>
 </div>
 <canvas id=cv width=1000 height=430></canvas>
 <div class=ctl>
  <button id=play>&#9654; Play 0&rarr;300</button>
  <input id=sl type=range min=0 max=300 step=1 value=120>
 </div>
 <div class=tiles id=tiles></div>
</div>

<footer>Forces from the drag equation (Cd 0.9 frontal, downforce package
CL 4.0 on plan area) &mdash; exact in v&sup2;. Flow field: Gear/aero_sweep.py
(D2Q9 LBM, lattice Re walked up the same 0-300 ladder) &mdash; the wake
regime is qualitative, not a validated Cd; real Re reaches ~8e5 at
300 km/h, past what a lattice resolves. g-forces and corner limit for the
90 mm maze turn shown to keep it honest.</footer>
</div>
<script id=data type="application/json">/*DATA*/</script>
<script>
(function(){
"use strict";
const D=JSON.parse(document.getElementById("data").textContent);
const F=D.sweep.frames, C=D.consts;
const cv=document.getElementById("cv"), cx=cv.getContext("2d");
const sl=document.getElementById("sl"), play=document.getElementById("play");
const spdEl=document.getElementById("spd"), regEl=document.getElementById("reg");
const tiles=document.getElementById("tiles");
// preload images
const imgs=F.map(fr=>{const im=new Image(); im.src=fr.img; return im;});
function nearest(kmh){
  let bi=0,bd=1e9;
  for(let i=0;i<F.length;i++){const dd=Math.abs(F[i].kmh-kmh);
    if(dd<bd){bd=dd;bi=i;}}
  return bi;
}
function fmt(x,d){return x.toLocaleString(undefined,
  {minimumFractionDigits:d,maximumFractionDigits:d});}
function draw(kmh){
  const im=imgs[nearest(kmh)];
  cx.fillStyle="#161310"; cx.fillRect(0,0,cv.width,cv.height);
  if(im.complete&&im.naturalWidth){
    const s=Math.min(cv.width/im.naturalWidth,cv.height/im.naturalHeight);
    const w=im.naturalWidth*s,h=im.naturalHeight*s;
    cx.drawImage(im,(cv.width-w)/2,(cv.height-h)/2,w,h);
  }
  const v=kmh/3.6;
  const q=0.5*C.rho*v*v;
  const drag=q*C.Cd*C.A_f;
  const df=q*C.CLpkg*C.A_p;
  const Re=v*C.L/C.nu;
  const M=v/C.a_snd;
  const decg=drag/C.m/C.g;
  const dfw=df/C.W|0;   // placeholder
  const dfwr=df/(C.m*C.g);
  const ac_g=(v*v/C.Rmaze)/C.g;
  spdEl.innerHTML=Math.round(kmh)+"<small>km/h</small>";
  let regime, rc;
  if(M<0.02){regime="barely moving air";}
  else if(Re<1e5){regime="laminar-ish, wake steady";}
  else if(M<0.3){regime="turbulent wake, shedding";}
  else{regime="compressibility mattering";}
  regEl.innerHTML="<b>"+fmt(v,1)+" m/s</b> &middot; "+regime;
  const cells=[
    ["Drag", drag<1?fmt(drag*1000,0)+" mN":fmt(drag,1)+" N",
     drag<C.W?"below its weight":fmt(drag/C.W,1)+"x weight"],
    ["Drag power", drag*v<1?fmt(drag*v,2)+" W":fmt(drag*v/1000,2)+" kW",
     "to hold speed"],
    ["Downforce (package)", df<1?fmt(df*1000,0)+" mN":fmt(df,0)+" N",
     dfwr<1?"< weight":fmt(dfwr,0)+"x weight"],
    ["Reynolds no.", Re<1000?fmt(Re,0):(Re/1000).toFixed(0)+"k",
     Re<1e5?"sub-turbulent":"turbulent"],
    ["Mach", fmt(M,2), M<0.3?"incompressible":"compressible"],
    ["Drag decel", fmt(decg,2)+" g", "off-throttle, air alone"],
  ];
  tiles.innerHTML=cells.map(c=>
    "<div class=tile><div class=k>"+c[0]+"</div><div class=v>"+c[1]+
    "</div><div class=n>"+c[2]+"</div></div>").join("");
}
C.W=C.m*C.g;
let playing=false,raf=0,last=0;
function loop(ts){
  if(!last)last=ts; const dt=(ts-last)/1000; last=ts;
  if(playing){let v=+sl.value + dt*60; if(v>=300){v=300;playing=false;
    play.innerHTML="&#9654; Play 0&rarr;300";play.classList.remove("on");}
    sl.value=v; draw(v);}
  raf=requestAnimationFrame(loop);
}
sl.oninput=()=>{playing=false;play.innerHTML="&#9654; Play 0&rarr;300";
  play.classList.remove("on");draw(+sl.value);};
play.onclick=()=>{playing=!playing;
  if(playing){if(+sl.value>=300)sl.value=0;last=0;
    play.innerHTML="&#10073;&#10073; Pause";play.classList.add("on");}
  else{play.innerHTML="&#9654; Play 0&rarr;300";play.classList.remove("on");}};
let ready=0;
imgs.forEach(im=>{im.onload=()=>{if(++ready===imgs.length)draw(+sl.value);};});
const _h=new URLSearchParams(location.hash.slice(1));
if(_h.has("v")){sl.value=Math.max(0,Math.min(300,+_h.get("v")||0));}
draw(+sl.value);
requestAnimationFrame(loop);
})();
</script>
"""


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(HERE, "web", "airflow_sweep.html"))
