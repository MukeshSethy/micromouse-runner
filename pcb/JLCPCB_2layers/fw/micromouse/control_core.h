// Pure control logic for the micromouse -- NO ESP32 dependencies, so the
// exact code that ships on the robot also runs inside fw/sim's host
// simulation (same .c file compiled with gcc). See control_core.c.
#pragma once
#include <stdint.h>
#include <stdbool.h>

#define LINE_N            8       // TCRT5000 channels, LINE1..LINE8 = mux Y0..Y7
#define LINE_PITCH_MM     9.525f  // QTR array pitch on the board
#define ADC_FULL          4095    // 12-bit

// Default line-follow tuning (shared by firmware and the host simulation;
// tuned IN the simulation -- the first cut lost a 400mm-radius curve).
// Gains map position error in mm directly to wheel differential (0..1).
#define LF_KP             0.014f
#define LF_KI             0.05f
#define LF_KD             0.0018f
#define LF_I_CLAMP        4.0f
#define LF_D_ALPHA        0.30f
#define LF_BASE_SPEED     0.45f

// Line position estimator: weighted centroid over calibrated channels with
// line-lost hysteresis (remembers the last seen side).
typedef struct {
    uint16_t cal_min[LINE_N];    // per-channel calibration (white floor)
    uint16_t cal_max[LINE_N];    // per-channel calibration (on the line)
    float last_pos_mm;           // last valid position (for lost-line memory)
    bool line_lost;
} line_estimator_t;

void line_est_init(line_estimator_t *e);
void line_est_calib_point(line_estimator_t *e, const uint16_t raw[LINE_N], bool on_line);
// raw ADC -> position of the line under the array, mm, +ve = line to the
// robot's RIGHT. Returns false while the line is lost (pos then holds the
// railed last-seen side so the controller steers back).
bool line_est_update(line_estimator_t *e, const uint16_t raw[LINE_N], float *pos_mm);

// PD controller with derivative filtering + integral clamp.
typedef struct {
    float kp, ki, kd;
    float i_acc, i_clamp;
    float d_filt, d_alpha;       // one-pole derivative filter
    float prev_err;
} pid_t;

void pid_init(pid_t *p, float kp, float ki, float kd, float i_clamp, float d_alpha);
float pid_step(pid_t *p, float err, float dt_s);

// Differential drive mixing: base speed +/- steer, clamped to [-1, 1] per
// wheel, preserving the differential when one side saturates.
void drive_mix(float base, float steer, float *left, float *right);

// Wall sensor conditioning: emitter-on minus ambient, clamped at 0.
static inline uint16_t wall_cond(uint16_t lit, uint16_t ambient) {
    return lit > ambient ? (uint16_t)(lit - ambient) : 0;
}
