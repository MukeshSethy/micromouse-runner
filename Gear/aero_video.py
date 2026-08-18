"""
aero_video.py - time-resolved LBM: capture the unsteady wake as frames so
the artifact can play it back.

Same solver and the same honesty caveat as aero_flow.py (lattice Re ~ 1e3,
topology only). What is new here is TIME: the wake behind a bluff body is
not steady, it sheds. Frames are captured after the start-up transient has
washed out, then packed as 8-bit grayscale PNGs; the artifact applies the
colour map in JS, which keeps the page a fraction of the size of a video
and lets the viewer scrub.

    python aero_video.py   -> _video_frames.json
"""

import base64
import io
import json
import math
import os
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

WARMUP = 2600          # steps discarded: start-up transient
NFRAMES = 44
EVERY = 42             # steps between captured frames
DS = 2                 # spatial downsample of the stored field


def png_gray(arr8):
    """Minimal 8-bit grayscale PNG encoder (no PIL dependency)."""
    h, w = arr8.shape
    raw = b"".join(b"\x00" + arr8[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return (len(data).to_bytes(4, "big") + c +
                (zlib.crc32(c) & 0xffffffff).to_bytes(4, "big"))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", w.to_bytes(4, "big") + h.to_bytes(4, "big")
                    + bytes([8, 0, 0, 0, 0]))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def downsample(mask, target_w):
    ny, nx = mask.shape
    k = max(1, int(round(nx / target_w)))
    ny2, nx2 = ny // k, nx // k
    return mask[:ny2*k, :nx2*k].reshape(ny2, k, nx2, k).any(axis=(1, 3))


def rot_mask(mask, deg):
    a = math.radians(deg)
    ny, nx = mask.shape
    R = int(math.hypot(ny, nx) / 2) + 2
    out = np.zeros((2*R, 2*R), dtype=bool)
    yy, xx = np.mgrid[0:2*R, 0:2*R]
    dy, dx = yy - R, xx - R
    sy = (dx*math.sin(-a) + dy*math.cos(-a) + ny/2).astype(int)
    sx = (dx*math.cos(-a) - dy*math.sin(-a) + nx/2).astype(int)
    ok = (sy >= 0) & (sy < ny) & (sx >= 0) & (sx < nx)
    out[ok] = mask[sy[ok], sx[ok]]
    rows = np.where(out.any(axis=1))[0]
    cols = np.where(out.any(axis=0))[0]
    return out[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]


def run(mask, u_lb=0.075, tau=0.53, pad=(64, 250, 58, 58)):
    L, R, B, T = pad
    ny, nx = mask.shape
    NY, NX = ny + B + T, nx + L + R
    obs = np.zeros((NY, NX), dtype=bool)
    obs[B:B+ny, L:L+nx] = mask

    w = np.array([4/9] + [1/9]*4 + [1/36]*4)
    cx = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1])
    cy = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1])
    opp = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])

    def feq(rho, ux, uy):
        cu = 3.0*(cx[:, None, None]*ux + cy[:, None, None]*uy)
        u2 = 1.5*(ux*ux + uy*uy)
        return rho*w[:, None, None]*(1 + cu + 0.5*cu*cu - u2)

    rho = np.ones((NY, NX))
    ux = np.full((NY, NX), u_lb)
    uy = np.zeros((NY, NX))
    # tiny asymmetric nudge: a perfectly symmetric start can sit on the
    # unstable symmetric solution for thousands of steps before shedding
    uy[:NY//2, :] += 0.004
    f = feq(rho, ux, uy)

    total = WARMUP + NFRAMES*EVERY
    speed_fr, vort_fr = [], []
    for s in range(total):
        rho = f.sum(axis=0)
        ux = (cx[:, None, None]*f).sum(axis=0)/rho
        uy = (cy[:, None, None]*f).sum(axis=0)/rho
        ux[obs] = 0.0
        uy[obs] = 0.0
        fq = feq(rho, ux, uy)
        f += -(1.0/tau)*(f - fq)
        fb = f.copy()
        for i in range(9):
            f[i][obs] = fb[opp[i]][obs]
        for i in range(9):
            f[i] = np.roll(np.roll(f[i], cy[i], axis=0), cx[i], axis=1)
        f[:, :, 0] = feq(np.ones((NY, 1)), np.full((NY, 1), u_lb),
                         np.zeros((NY, 1)))[:, :, 0]
        f[:, :, -1] = f[:, :, -2]
        if not np.isfinite(f).all():
            print("   DIVERGED at", s)
            return None
        if s >= WARMUP and (s - WARMUP) % EVERY == 0:
            spd = np.hypot(ux, uy)/u_lb
            dvy_dx = np.gradient(uy, axis=1)
            dvx_dy = np.gradient(ux, axis=0)
            vort = (dvy_dx - dvx_dy)/u_lb
            speed_fr.append(spd[::DS, ::DS])
            vort_fr.append(vort[::DS, ::DS])
    nu_lb = (tau - 0.5)/3.0
    return (speed_fr, vort_fr, obs[::DS, ::DS], u_lb*nx/nu_lb)


def pack(frames, obs, lo, hi):
    """Quantise to 8-bit; 0 is reserved for the body so JS can key it."""
    out = []
    for fr in frames:
        v = np.clip((fr - lo)/(hi - lo), 0.0, 1.0)
        a = (1 + v*254).astype(np.uint8)
        a[obs] = 0
        out.append(base64.b64encode(png_gray(a)).decode())
    return out


def main():
    m_plan = np.load(os.path.join(HERE, "_m_plan.npy"))
    cases = [("straight", downsample(m_plan, 104), 0.0),
             ("corner", downsample(rot_mask(m_plan, 6.7), 104), 6.7)]
    doc = {"frames": {}, "meta": {}}
    for key, mask, yaw in cases:
        print("running", key, mask.shape)
        res = run(mask)
        if res is None:
            continue
        spd, vort, obs, Re = res
        h, w = obs.shape
        doc["frames"][key] = {
            "speed": pack(spd, obs, 0.0, 1.75),
            "vort": pack(vort, obs, -0.35, 0.35),
            "w": w, "h": h, "yaw": yaw, "Re": round(Re),
        }
        kb = sum(len(x) for x in doc["frames"][key]["speed"]) / 1024
        print("  %d frames, %dx%d, speed %.0f kB" % (len(spd), w, h, kb))
    doc["meta"] = {"nframes": NFRAMES, "warmup": WARMUP, "every": EVERY,
                   "speed_range": [0.0, 1.75], "vort_range": [-0.35, 0.35]}
    p = os.path.join(HERE, "_video_frames.json")
    with open(p, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    print("wrote %s (%.2f MB)" % (p, os.path.getsize(p)/1e6))


if __name__ == "__main__":
    main()
