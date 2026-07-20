#include "control_core.h"

void line_est_init(line_estimator_t *e) {
    for (int i = 0; i < LINE_N; i++) {
        e->cal_min[i] = 300;      // sane defaults before calibration:
        e->cal_max[i] = 1900;     // PT334/TCRT swing per the circuit analysis
    }
    e->last_pos_mm = 0;
    e->line_lost = true;
}

void line_est_calib_point(line_estimator_t *e, const uint16_t raw[LINE_N], bool on_line) {
    // call repeatedly while sweeping the robot over floor/line (button B mode)
    for (int i = 0; i < LINE_N; i++) {
        if (on_line) {
            if (raw[i] > e->cal_max[i]) e->cal_max[i] = raw[i];
        } else {
            if (raw[i] < e->cal_min[i]) e->cal_min[i] = raw[i];
        }
    }
}

bool line_est_update(line_estimator_t *e, const uint16_t raw[LINE_N], float *pos_mm) {
    // TCRT collector is PULLED LOW by white floor (PT conducting) and rises
    // on the black line -- higher ADC = more line under that channel.
    float wsum = 0, sum = 0;
    int strongest = -1;
    float strongest_v = 0;
    for (int i = 0; i < LINE_N; i++) {
        uint16_t lo = e->cal_min[i], hi = e->cal_max[i];
        float v = 0;
        if (raw[i] > lo && hi > lo)
            v = (float)(raw[i] - lo) / (float)(hi - lo);   // 0..1 "line-ness"
        if (v > 1) v = 1;
        // idle-channel deadband: with factory defaults (cal_min 300) a real
        // white floor of ~0.4V (496 counts, TEST_REPORT O2) leaves ~0.1 of
        // "line-ness" on EVERY channel, dragging the centroid toward zero
        // (host sim S2 finding: positions compressed ~0.55x). Channels below
        // 15% are floor, not line.
        if (v < 0.15f) v = 0;
        if (v > strongest_v) { strongest_v = v; strongest = i; }
        // channel i center offset from array middle, +ve to the right
        float x_mm = ((float)i - (LINE_N - 1) / 2.0f) * LINE_PITCH_MM;
        wsum += v * x_mm;
        sum += v;
    }
    (void)strongest;
    if (sum < 0.25f) {                       // no channel sees enough line
        e->line_lost = true;
        // HOLD the last valid position: any discontinuous "rail" value turns
        // into a huge D-term spike at the loss edge and the robot pirouettes
        // (host sim finding -- it drove backwards through a line gap).
        // Holding is continuous: the robot keeps its current gentle
        // correction and crosses straight gaps dead ahead.
        *pos_mm = e->last_pos_mm;
        return false;
    }
    e->line_lost = false;
    e->last_pos_mm = wsum / sum;
    *pos_mm = e->last_pos_mm;
    return true;
}

void pid_init(pid_t *p, float kp, float ki, float kd, float i_clamp, float d_alpha) {
    p->kp = kp; p->ki = ki; p->kd = kd;
    p->i_acc = 0; p->i_clamp = i_clamp;
    p->d_filt = 0; p->d_alpha = d_alpha;
    p->prev_err = 0;
}

float pid_step(pid_t *p, float err, float dt_s) {
    p->i_acc += err * dt_s;
    if (p->i_acc > p->i_clamp) p->i_acc = p->i_clamp;
    if (p->i_acc < -p->i_clamp) p->i_acc = -p->i_clamp;
    float d_raw = (err - p->prev_err) / (dt_s > 0 ? dt_s : 1e-3f);
    p->d_filt += p->d_alpha * (d_raw - p->d_filt);
    p->prev_err = err;
    return p->kp * err + p->ki * p->i_acc + p->kd * p->d_filt;
}

void drive_mix(float base, float steer, float *left, float *right) {
    float l = base + steer, r = base - steer;
    // preserve the differential when clamping (slow the fast wheel's pair)
    float over = 0;
    if (l > 1 && l - 1 > over) over = l - 1;
    if (r > 1 && r - 1 > over) over = r - 1;
    l -= over; r -= over;
    float under = 0;
    if (l < -1 && -1 - l > under) under = -1 - l;
    if (r < -1 && -1 - r > under) under = -1 - r;
    l += under; r += under;
    if (l > 1) l = 1;
    if (l < -1) l = -1;
    if (r > 1) r = 1;
    if (r < -1) r = -1;
    *left = l; *right = r;
}
