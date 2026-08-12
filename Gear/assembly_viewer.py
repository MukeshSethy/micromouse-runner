"""
assembly_viewer.py - WebGL render of the real CAD assemblies with a SEQUENCED
exploded view: the slider replays the disassembly procedure step by step
(wheels off -> axles out -> gears -> bearings -> pinions -> motors -> pods),
so scrubbing it back to zero is the assembly procedure in reverse order.

Two scenes in one page: the 4WD drivetrain and the tyre-casting mould stack.

    python assembly_viewer.py <output.html>
"""

import json
import math
import os
import sys

import cadquery as cq

import chassis_lib as C
import config as K
import generate_drivetrain as G
import mold_tyre as M
import export_mesh as EM

HERE = os.path.dirname(os.path.abspath(__file__))

UP = (0.0, 0.0, 1.0)


def _side(name):
    """+1 for the CAD +Y (left) side, -1 for the mirrored side."""
    return 1.0 if ("_L" in name or name.endswith("L")) else -1.0


def _plan(name):
    """(stage, direction CAD-frame, distance) for the DISASSEMBLY sequence.

    Order is the physical one: each part must be free to move when its stage
    fires. Reverse order is exactly how the robot is built.
    """
    s = _side(name)
    out = (0.0, s, 0.0)
    inw = (0.0, -s, 0.0)
    if name.startswith("wheel_"):
        return 0, out, 60.0            # pull wheels off the D-flats
    if name.startswith("axle_"):
        return 1, out, 40.0            # slide axles out through the bearings
    if name.startswith("gear_axle_"):
        return 2, UP, 26.0             # 40T gears are now loose - lift out
    if name.startswith("brg_"):
        # flange dictates the press direction: outer presses out outboard,
        # inner presses out inboard
        return (3, out, 15.0) if name.endswith("_out") else (3, inw, 11.0)
    if name.startswith("gear_motor_"):
        return 4, out, 20.0            # pinions off the motor shafts
    if name.startswith("motor_N20"):
        return 5, UP, 55.0             # motors lift out of the pod channels
    if name.startswith("pod_"):
        return 6, UP, 25.0             # unscrew M3s, pods off the PCB
    return -1, UP, 0.0                 # PCB stays put


DRIVETRAIN_STEPS = [
    "Pull the four wheels off the axle D-flats",
    "Slide the four D3 axles out through the bearings",
    "Lift out the 40T wheel gears (loose once the axle is gone)",
    "Press the F683ZZ bearings out of the bosses (flange side leads)",
    "Pull the 19T pinions off the N20 motor shafts",
    "Lift the motors out of the pod U-channels",
    "Unscrew the four M3s and lift the pods off the PCB",
]

MOLD_STEPS = [
    "Unscrew the three M3×16 socket-head clamp screws (they thread "
    "straight into the printed cup bosses — no nuts)",
    "Lift the plug — the cured sprue and plenum puck pull out with it; "
    "snip flush at the three gates",
    "Push the three ejector pins — the wheel rises out of the cup with "
    "its tyre already keyed on. Nothing else to do: the tyre stays on the "
    "wheel for life",
]

COL = {
    "pod": "#E11A27", "gear": "#EDAB36", "wheel": "#4A4441",
    "axle": "#C8C2BC", "brg": "#9A928C", "motor": "#3A3532",
    "pcb": "#2E6B33", "cup": "#8A2B32", "tyre": "#F2501A",
    "plug": "#9A928C",
}


def _color(name):
    for k, c in (("pod_", "pod"), ("gear_", "gear"), ("wheel_", "wheel"),
                 ("axle_", "axle"), ("brg_", "brg"), ("motor_", "motor"),
                 ("PCB_", "pcb")):
        if name.startswith(k):
            return COL[c]
    return "#888888"


def _emit(name, shape, stage, dcad, dist, color, tol):
    P, N, _ = EM.tess(shape, (0, 0, 0), tol)
    v64, n64 = EM.pack(P, N)
    # tess() rotates 180 deg about Z, so directions rotate with it
    dv = [-dcad[0], -dcad[1], dcad[2]]
    print("  %-26s stage %2d %7d tris" % (name, stage, len(P) // 3))
    return {"name": name, "color": color, "stage": stage, "dir": dv,
            "dist": dist, "n": len(P), "v": v64, "nr": n64}


def scene_drivetrain():
    motor_g, idler, wheel_g = G.make_gears()
    asm = G.build_assembly(motor_g, idler, wheel_g)
    parts = []
    for ch in asm.children:
        if ch.obj is None:
            continue
        shape = ch.obj.val().moved(ch.loc)
        stage, dcad, dist = _plan(ch.name)
        if ch.name.startswith("PCB_"):
            solids = [x for x in shape.Solids() if x.Volume() > 25.0]
            shape = cq.Compound.makeCompound(solids)
            tol = 1.4
        elif ch.name.startswith("motor_N20"):
            # the vendor STEP is faceted (42 planar faces) - tol is moot,
            # the low-poly look IS the vendor model
            tol = 0.8
        elif ch.name.startswith(("wheel_", "brg_", "axle_")):
            tol = 0.55
        else:
            tol = 0.4
        parts.append(_emit(ch.name, shape, stage, dcad, dist,
                           _color(ch.name), tol))
    return {"label": "Drivetrain", "steps": DRIVETRAIN_STEPS,
            "cz": 12.0, "czk": 14.0, "d": 240.0, "parts": parts}


def _m3x16_shcs():
    """M3x16 socket-head cap screw, head at z=0, shank hanging down."""
    s = (cq.Workplane("XY").circle(5.5 / 2).extrude(3.0)
         .union(cq.Workplane("XY").circle(3.0 / 2).extrude(-16.0)))
    hexs = (cq.Workplane("XY").polygon(6, 2.5 / math.cos(math.radians(30)))
            .extrude(1.6).translate((0, 0, 1.4)))
    return s.cut(hexs)


def scene_mold():
    zw = M.FLOOR_T
    tyre = (cq.Workplane("XY").circle(M.MOLD_BORE / 2).extrude(M.CH_W)
            .cut(cq.Workplane("XY").circle(M.CH_D / 2).extrude(M.CH_W))
            .translate((0, 0, zw + M.FL_W)))
    wheel = C.wheel_placeholder(bare=True, keyed=True).translate((0, 0, zw))
    plug = M.mold_plug().translate((0, 0, zw + M.W))
    # heads seat on the plug plate top; 16 mm reaches ~12 mm into the
    # tapped cup bosses (2.90 pilot, thread-forming - no nuts)
    z_head = zw + M.W + M.PLATE_T
    parts = [
        _emit("mold_cup", M.mold_cup().val(), -1, UP, 0.0, COL["cup"], 0.3),
        # wheel and tyre leave TOGETHER - the keying is permanent
        _emit("wheel_keyed", wheel.val(), 2, UP, 34.0, COL["wheel"], 0.3),
        _emit("tyre_cast", tyre.val(), 2, UP, 34.0, COL["tyre"], 0.3),
        _emit("mold_plug", plug.val(), 1, UP, 37.0, COL["plug"], 0.3),
    ]
    for k in range(3):
        a = math.radians(120 * k + 60)
        scr = _m3x16_shcs().translate(
            (M.BOLT_BC / 2 * math.cos(a), M.BOLT_BC / 2 * math.sin(a),
             z_head))
        # travel keeps the shank tips above the plug's exploded position
        parts.append(_emit("screw_M3x16_%d" % k, scr.val(), 0, UP, 55.0,
                           "#55504C", 0.15))
    return {"label": "Tyre mould", "steps": MOLD_STEPS,
            "cz": 14.0, "czk": 26.0, "d": 120.0, "parts": parts}


def main(out_path):
    doc = {"scenes": [scene_drivetrain(), scene_mold()]}
    js = json.dumps(doc, separators=(",", ":"))
    html = TEMPLATE.replace("/*MESH*/", js)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%.2f MB)" % (out_path, os.path.getsize(out_path) / 1e6))


TEMPLATE = r"""<title>Micromouse assembly — exploded view</title>
<style>
:root{--bg:#14110F;--panel:#1C1815;--ink:#F2EDE8;--dim:#A79C93;--rule:#332C27;
--accent:#E11A27;--gold:#EDAB36}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}
.wrap{max-width:1180px;margin:0 auto;padding:22px 16px 40px;display:flex;
flex-direction:column;gap:13px}
h1{margin:0;font-size:clamp(20px,3vw,28px);font-weight:700;
letter-spacing:-.02em;font-family:ui-sans-serif,system-ui,"Segoe UI",
sans-serif;font-stretch:condensed}
.eyebrow{font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;
color:var(--accent);font-weight:700}
.grid{display:grid;grid-template-columns:1fr 300px;gap:13px}
@media(max-width:820px){.grid{grid-template-columns:1fr}}
canvas{display:block;width:100%;height:auto;border:1px solid var(--rule);
border-radius:3px;background:#0B0908;touch-action:none;cursor:grab}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
background:var(--panel);border:1px solid var(--rule);border-radius:3px;
padding:11px 13px}
label{display:flex;align-items:center;gap:8px;color:var(--dim);
font-size:11px;letter-spacing:.06em;text-transform:uppercase}
input[type=range]{accent-color:var(--accent);width:200px}
button{background:#262019;color:var(--ink);border:1px solid var(--rule);
border-radius:3px;padding:6px 12px;font:inherit;font-size:11.5px;
cursor:pointer;letter-spacing:.04em}
button:hover{border-color:var(--gold)}
button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.steps{background:var(--panel);border:1px solid var(--rule);border-radius:3px;
padding:13px 15px;display:flex;flex-direction:column;gap:2px;min-width:0}
.steps h2{margin:0 0 8px;font-size:11px;letter-spacing:.14em;
text-transform:uppercase;color:var(--dim);font-weight:700}
.step{display:flex;gap:9px;padding:6px 7px;border-radius:3px;color:var(--dim);
font-size:11.8px;line-height:1.45}
.step b{color:var(--gold);font-weight:700;min-width:16px}
.step.done{color:#6B625B}
.step.done b{color:#6B625B}
.step.live{background:#2A1214;color:var(--ink);outline:1px solid #57272B}
.step.live b{color:var(--accent)}
.note{margin-top:auto;padding-top:10px;border-top:1px solid var(--rule);
font-size:11px;color:#6B625B;line-height:1.55}
.hud{font-size:11px;color:var(--dim)}
.hud b{color:var(--ink)}
footer{color:#6B625B;font-size:11px;border-top:1px solid var(--rule);
padding-top:10px;line-height:1.6}
</style>
<div class="wrap">
<div><div class="eyebrow">micromouse 4wd &middot; parametric cad, rev 7</div>
<h1>Assembly render &mdash; sequenced exploded view</h1></div>
<div class="bar">
  <span id="tabs"></span>
  <label>Explode <input id="ex" type="range" min="0" max="1" step="0.002"
    value="0"></label>
  <button id="dis">Disassemble &#9654;</button>
  <button id="asm">&#9664; Assemble</button>
  <span class="hud" id="hud"><b>Assembled</b></span>
</div>
<div class="grid">
  <canvas id="gl" width="1280" height="880"></canvas>
  <div class="steps"><h2 id="st">Disassembly order</h2><div id="list"></div>
  <div class="note">Slider left&rarr;right = disassembly. Right&rarr;left =
  the same steps in reverse: the assembly procedure. Each band of the slider
  moves exactly one step. Drag the canvas to orbit, wheel to zoom.</div></div>
</div>
<footer>Rendered from the same parametric CAD that generated the STEP files
(Gear/generate_drivetrain.py, Gear/mold_tyre.py). 19T&rarr;40T, 2.105:1,
M0.5&thinsp;20&deg;; F683ZZ bearings on live D3 axles; N20 encoder motors;
PCB is the imported fab model. Mould scene: pour-through-the-wheel v2,
fill path verified.</footer>
</div>
<script id="mesh" type="application/json">/*MESH*/</script>
<script>
(function(){
"use strict";
const DOC=JSON.parse(document.getElementById("mesh").textContent);
const cv=document.getElementById("gl"),
gl=cv.getContext("webgl",{antialias:true});
const VS=`attribute vec3 p;attribute vec3 n;uniform mat4 mvp;uniform vec3 off;
varying vec3 vn;void main(){vn=n;gl_Position=mvp*vec4(p+off,1.0);}`;
const FS=`precision mediump float;varying vec3 vn;uniform vec3 col;
void main(){vec3 N=normalize(vn);
float d=max(dot(N,normalize(vec3(0.4,0.3,0.85))),0.0);
float d2=max(dot(N,normalize(vec3(-0.5,-0.2,0.3))),0.0);
gl_FragColor=vec4(col*(0.34+0.56*d+0.18*d2),1.0);}`;
function sh(t,s){const o=gl.createShader(t);gl.shaderSource(o,s);
gl.compileShader(o);return o;}
const PR=gl.createProgram();
gl.attachShader(PR,sh(gl.VERTEX_SHADER,VS));
gl.attachShader(PR,sh(gl.FRAGMENT_SHADER,FS));
gl.linkProgram(PR);gl.useProgram(PR);gl.enable(gl.DEPTH_TEST);
const A_p=gl.getAttribLocation(PR,"p"),A_n=gl.getAttribLocation(PR,"n"),
U_mvp=gl.getUniformLocation(PR,"mvp"),U_off=gl.getUniformLocation(PR,"off"),
U_c=gl.getUniformLocation(PR,"col");
const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
const SCENES=DOC.scenes.map(sc=>({...sc,parts:sc.parts.map(g=>{
  const vb=b64(g.v),nb=b64(g.nr);
  const iv=new Int16Array(vb.buffer,0,vb.length>>1),
  inv=new Int8Array(nb.buffer);
  const a=new Float32Array(g.n*6);
  for(let i=0;i<g.n;i++){a[i*6]=iv[i*3]/100;a[i*6+1]=iv[i*3+1]/100;
    a[i*6+2]=iv[i*3+2]/100;a[i*6+3]=inv[i*3]/127;a[i*6+4]=inv[i*3+1]/127;
    a[i*6+5]=inv[i*3+2]/127;}
  const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);
  gl.bufferData(gl.ARRAY_BUFFER,a,gl.STATIC_DRAW);
  return {buf,count:g.n,stage:g.stage,dir:g.dir,dist:g.dist,
    col:[1,3,5].map(k=>parseInt(g.color.substr(k,2),16)/255)};
})}));
function mul(a,b){const o=new Float32Array(16);
for(let i=0;i<4;i++)for(let j=0;j<4;j++){let s=0;
for(let k=0;k<4;k++)s+=a[k*4+j]*b[i*4+k];o[i*4+j]=s;}return o;}
function persp(f,a,n,fa){const t=1/Math.tan(f/2),m=new Float32Array(16);
m[0]=t/a;m[5]=t;m[10]=(fa+n)/(n-fa);m[11]=-1;m[14]=2*fa*n/(n-fa);return m;}
function look(e,c,u){let z=[e[0]-c[0],e[1]-c[1],e[2]-c[2]];
let l=Math.hypot(z[0],z[1],z[2]);z=z.map(v=>v/l);
let x=[u[1]*z[2]-u[2]*z[1],u[2]*z[0]-u[0]*z[2],u[0]*z[1]-u[1]*z[0]];
l=Math.hypot(x[0],x[1],x[2])||1;x=x.map(v=>v/l);
const y=[z[1]*x[2]-z[2]*x[1],z[2]*x[0]-z[0]*x[2],z[0]*x[1]-z[1]*x[0]];
return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,
x[2],y[2],z[2],0,-(x[0]*e[0]+x[1]*e[1]+x[2]*e[2]),
-(y[0]*e[0]+y[1]*e[1]+y[2]*e[2]),-(z[0]*e[0]+z[1]*e[1]+z[2]*e[2]),1]);}
const ss=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);};
let cur=0,yaw=0.72,pitch=0.42,zoom=1,ex=0,vel=0,drag=false,lx=0,ly=0;
const exEl=document.getElementById("ex"),hud=document.getElementById("hud"),
list=document.getElementById("list"),tabs=document.getElementById("tabs"),
bDis=document.getElementById("dis"),bAsm=document.getElementById("asm");
function buildTabs(){tabs.innerHTML="";SCENES.forEach((s,i)=>{
  const b=document.createElement("button");b.textContent=s.label;
  b.className=i===cur?"on":"";
  b.onclick=()=>{cur=i;ex=0;vel=0;exEl.value=0;buildTabs();buildSteps();};
  tabs.appendChild(b);});}
function buildSteps(){list.innerHTML="";SCENES[cur].steps.forEach((s,i)=>{
  const d=document.createElement("div");d.className="step";d.dataset.i=i;
  d.innerHTML="<b>"+(i+1)+"</b><span>"+s+"</span>";list.appendChild(d);});}
buildTabs();buildSteps();
// #scene=1&ex=0.5 - deep-link a state (also how the page is smoke-tested)
(function(){const h=new URLSearchParams(location.hash.slice(1));
if(h.has("scene")){cur=Math.min(SCENES.length-1,+h.get("scene")||0);
  buildTabs();buildSteps();}
if(h.has("ex")){ex=Math.max(0,Math.min(1,+h.get("ex")||0));exEl.value=ex;}
if(h.has("yaw"))yaw=+h.get("yaw");if(h.has("pitch"))pitch=+h.get("pitch");})();
cv.addEventListener("pointerdown",e=>{drag=true;lx=e.clientX;ly=e.clientY;
cv.setPointerCapture(e.pointerId);});
cv.addEventListener("pointerup",()=>drag=false);
cv.addEventListener("pointermove",e=>{if(!drag)return;
yaw+=(e.clientX-lx)*0.008;pitch=Math.max(-1.3,Math.min(1.45,
pitch+(e.clientY-ly)*0.006));lx=e.clientX;ly=e.clientY;});
cv.addEventListener("wheel",e=>{e.preventDefault();
zoom=Math.max(0.35,Math.min(3,zoom*(1+Math.sign(e.deltaY)*0.1)));},
{passive:false});
exEl.oninput=e=>{ex=parseFloat(e.target.value);vel=0;};
bDis.onclick=()=>{vel=0.22;};
bAsm.onclick=()=>{vel=-0.22;};
let tPrev=null;
function frame(ts){
  if(tPrev==null)tPrev=ts;
  const dt=Math.min(0.05,(ts-tPrev)/1000);tPrev=ts;
  if(vel){ex=Math.max(0,Math.min(1,ex+vel*dt));exEl.value=ex;
    if(ex<=0||ex>=1)vel=0;}
  const S=SCENES[cur],NS=S.steps.length;
  const live=ex<=0?-1:ex>=1?NS:Math.min(NS-1,Math.floor(ex*NS));
  for(const el of list.children){const i=+el.dataset.i;
    el.className="step"+(i<live?" done":i===live?" live":"");}
  hud.innerHTML=ex<=0?"<b>Assembled</b>":ex>=1?"<b>Fully disassembled</b>":
    "<b>Step "+(live+1)+"/"+NS+"</b>"+(vel<0?" (assembling)":"");
  gl.viewport(0,0,cv.width,cv.height);
  gl.clearColor(0.043,0.035,0.031,1);
  gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  const cz=S.cz+ex*S.czk,d=S.d*(1+0.30*ss(ex))*zoom;
  const eye=[Math.cos(yaw)*Math.cos(pitch)*d,
             Math.sin(yaw)*Math.cos(pitch)*d,cz+Math.sin(pitch)*d];
  const VP=mul(persp(0.66,cv.width/cv.height,5,3000),
               look(eye,[0,0,cz],[0,0,1]));
  gl.uniformMatrix4fv(U_mvp,false,VP);
  for(const m of S.parts){
    const k=m.stage<0?0:ss(ex*NS-m.stage);
    gl.bindBuffer(gl.ARRAY_BUFFER,m.buf);
    gl.enableVertexAttribArray(A_p);
    gl.vertexAttribPointer(A_p,3,gl.FLOAT,false,24,0);
    gl.enableVertexAttribArray(A_n);
    gl.vertexAttribPointer(A_n,3,gl.FLOAT,false,24,12);
    gl.uniform3f(U_off,m.dir[0]*m.dist*k,m.dir[1]*m.dist*k,
                 m.dir[2]*m.dist*k);
    gl.uniform3fv(U_c,m.col);gl.drawArrays(gl.TRIANGLES,0,m.count);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
})();
</script>
"""


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(HERE, "web", "assembly_view.html"))
