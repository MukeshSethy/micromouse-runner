/* Host-side line-following simulation for the micromouse firmware.
 *
 * Compiles the EXACT control_core.c that ships on the robot (no ESP32 deps)
 * against a physics + sensor model derived from the board's own numbers:
 *   - sensor bar: 8x TCRT5000 at 9.525 mm pitch, 70.5 mm ahead of the axle
 *     (board: array y=13.5, axle y=84)
 *   - track width 83 mm (wheel centerlines in the edge notches)
 *   - TCRT response: gaussian beam sigma 4 mm at the 2.4 mm ride height,
 *     ADC swing per TEST_REPORT O2 (white <=0.4 V, black >=1.89 V, 12-bit
 *     over 3.3 V) + white noise
 *   - motors: first-order velocity response tau 50 ms, 0.9 m/s at PWM 1.0
 *
 * Scenarios assert quantitative tracking bounds; exit 1 on any failure.
 * Output is parsed into pcb/TEST_REPORT.md (F-series tests).
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "../micromouse/control_core.h"

#define DT 0.002f              /* 500 Hz, matches LOOP_HZ */
#define SENSOR_AHEAD_MM 70.5f
#define TRACK_MM 83.0f
#define VMAX_MM_S 900.0f
#define TAU_S 0.05f
#define BASE LF_BASE_SPEED
#define KP LF_KP
#define KI LF_KI
#define KD LF_KD

static unsigned rng = 12345;
static float frand(void) {          /* deterministic noise */
    rng = rng * 1664525u + 1013904223u;
    return (float)(rng >> 8) / (float)(1u << 24) - 0.5f;
}

/* line lateral offset (mm) at longitudinal position s (mm), per scenario */
typedef float (*track_fn)(float s);
static float trk_straight(float s) { (void)s; return 0; }
static float trk_step(float s) { return s > 200 ? 25.0f : 0; }
static float trk_curve(float s) {  /* 800 mm radius arc from s=200 (small-slope
                                       parametrization stays valid to ~30 deg) */
    if (s < 200) return 0;
    float ds = s - 200;
    if (ds > 400) ds = 400;
    return 800.0f - sqrtf(800.0f * 800.0f - ds * ds);
}
static float trk_scurve(float s) { return 30.0f * sinf(s / 150.0f); }
static float trk_gap(float s) { return (s > 300 && s < 380) ? 1e6f : 0; } /* line vanishes 80mm */

/* TCRT5000 model: ADC counts for a sensor at lateral offset d from the line
 * center (18 mm wide tape edge blur folded into the beam sigma). */
static uint16_t tcrt_adc(float d_mm) {
    float line_ness = expf(-(d_mm * d_mm) / (2 * 6.5f * 6.5f));
    float v = 0.35f + line_ness * (1.95f - 0.35f);         /* volts */
    v += frand() * 0.04f;
    int adc = (int)(v / 3.3f * ADC_FULL);
    if (adc < 0) adc = 0;
    if (adc > ADC_FULL) adc = ADC_FULL;
    return (uint16_t)adc;
}

typedef struct { float x_mm, err_max_after_settle, err_rms; int lost_ticks; } simres_t;

static simres_t run_scenario(track_fn trk, float sim_mm, const char *name) {
    line_estimator_t est;
    pid_t pid;
    line_est_init(&est);
    /* calibrated device: tight cal from the model's own extremes */
    for (int i = 0; i < LINE_N; i++) { est.cal_min[i] = 460; est.cal_max[i] = 2350; }
    pid_init(&pid, KP, KI, KD, LF_I_CLAMP, LF_D_ALPHA);

    float x = 8.0f;          /* robot lateral pos (mm), start 8 mm off-line */
    float heading = 0.0f;    /* rad, 0 = along the track */
    float vl = 0, vr = 0;    /* wheel velocities mm/s */
    float s = 0;             /* distance along track */
    simres_t res = {0, 0, 0, 0};
    int n = 0, settled_from = -1;
    int steps = (int)(sim_mm / (VMAX_MM_S * BASE * DT) * 1.6f);

    for (int k = 0; k < steps && s < sim_mm; k++) {
        /* sensor bar pose */
        float bar_x = x + SENSOR_AHEAD_MM * sinf(heading);
        float bar_s = s + SENSOR_AHEAD_MM * cosf(heading);
        float line_x = trk(bar_s);
        uint16_t raw[LINE_N];
        for (int i = 0; i < LINE_N; i++) {
            float sens_x = bar_x + (((float)i - 3.5f) * LINE_PITCH_MM) * cosf(heading);
            raw[i] = tcrt_adc(sens_x - line_x);
        }
        float pos_mm;
        bool seen = line_est_update(&est, raw, &pos_mm);
        if (!seen) { res.lost_ticks++; pid.i_acc *= 0.95f; }  /* no windup in gaps */
        float steer = pid_step(&pid, pos_mm, DT);
        float base = seen ? BASE : BASE * 0.5f;
        float l, r;
        drive_mix(base, steer, &l, &r);

        /* first-order wheel dynamics */
        vl += (l * VMAX_MM_S - vl) * (DT / TAU_S);
        vr += (r * VMAX_MM_S - vr) * (DT / TAU_S);
        float v = (vl + vr) / 2, w = (vl - vr) / TRACK_MM;
        heading += w * DT;
        x += v * sinf(heading) * DT;
        s += v * cosf(heading) * DT;

        float err = x - trk(s);
        if (fabsf(trk(s)) < 1e5f) {              /* ignore gap section */
            if (settled_from < 0 && fabsf(err) < 3.0f) settled_from = k;
            if (settled_from >= 0 && k > settled_from + 100) {
                if (fabsf(err) > res.err_max_after_settle)
                    res.err_max_after_settle = fabsf(err);
            }
            res.err_rms += err * err;
            n++;
        }
    }
    res.err_rms = sqrtf(res.err_rms / (n ? n : 1));
    res.x_mm = s;
    printf("SIM %-9s: ran %.0f mm, rms err %.1f mm, max-after-settle %.1f mm, "
           "lost %d ticks\n", name, s, res.err_rms, res.err_max_after_settle,
           res.lost_ticks);
    return res;
}

int main(void) {
    int fails = 0;
    simres_t r;

    r = run_scenario(trk_straight, 1000, "straight");
    if (r.err_max_after_settle > 4.0f) { puts("FAIL straight: >4mm after settle"); fails++; }

    r = run_scenario(trk_step, 800, "step25mm");
    if (r.err_max_after_settle > 26.0f) { puts("FAIL step: never recovered"); fails++; }

    r = run_scenario(trk_curve, 600, "curveR800");
    if (r.err_rms > 8.0f) { puts("FAIL curve: rms err >8mm"); fails++; }

    r = run_scenario(trk_scurve, 1200, "s-curve");
    if (r.err_rms > 8.0f) { puts("FAIL s-curve: rms err >8mm"); fails++; }

    r = run_scenario(trk_gap, 800, "gap80mm");
    if (r.lost_ticks == 0) { puts("FAIL gap: loss never detected"); fails++; }
    if (r.err_rms > 12.0f) { puts("FAIL gap: did not reacquire"); fails++; }

    printf(fails ? "SIM RESULT: %d FAILURES\n" : "SIM RESULT: ALL SCENARIOS PASS\n", fails);
    return fails ? 1 : 0;
}
