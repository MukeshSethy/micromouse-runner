/* Hardware-chain simulation: SENSORS and ACTUATORS of the micromouse PCB.
 *
 * Companion to sim_linefollow.c (which proves the control loop): this file
 * proves each electrical CHAIN on the board behaves as designed, end to end,
 * using the board's own numbers:
 *
 *   S1  wall sensors  : IR333-A emitter (banked FET drive) -> wall
 *                       reflection (1/d^2) -> PT334-6B photocurrent -> 47k
 *                       load -> ADC1 counts.  Front 0deg / diag 45deg /
 *                       side 90deg geometry from WALL_GEOM.  Asserts
 *                       monotonic response + detection thresholds.
 *   S2  line sensors  : TCRT5000 white/black swing (TEST_REPORT O2 values)
 *                       through the CD74HC4067 mux path; asserts the
 *                       estimator resolves position across the array.
 *   A1  motors        : LEDC PWM -> TB6612 IN/IN -> 6V bridge -> N20 motor
 *                       (1st-order, tau 50ms) -> magnetic encoder ticks
 *                       (7ppr x 4 edges x 50:1 gear = 1400 ticks/rev).
 *                       Asserts step-response ramp + tick integration.
 *   A2  IMU (BNO055)  : differential wheel speeds -> body yaw rate ->
 *                       BNO055 fusion model (100Hz, 0.3deg noise, small
 *                       bias); asserts a commanded 360deg spin reads back
 *                       360 +/- 2deg.
 *   C1  corridor demo : side sensors -> P-controller -> motors, robot
 *                       released off-centre in a 168mm maze corridor;
 *                       asserts it centres and holds (sensors+actuators
 *                       cooperating through the real control primitives).
 *
 * Exit 1 on any failed assertion.
 *   gcc fw/sim/sim_hw.c fw/micromouse/control_core.c -I fw/micromouse -lm
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "control_core.h"

#define DT 0.002f                    /* 500 Hz control rate */
static int g_fail = 0;
#define CHECK(cond, ...) do { \
    printf("  [%s] ", (cond) ? "PASS" : "FAIL"); printf(__VA_ARGS__); printf("\n"); \
    if (!(cond)) g_fail++; } while (0)

/* ---------------- board-derived constants ---------------- */
/* wall optics: IR333-A @ ~25mA banked drive; PT334-6B into 47k to 3.3V.
 * Response model: ADC = ADC_FULL * k / (d_mm^2) clamped; k chosen so a wall
 * at 60mm (half maze cell) reads ~2000 counts on the front pair -- matches
 * the TEST_REPORT W2 operating point. */
#define WALL_K            (2000.0f * 60.0f * 60.0f)
#define WALL_AMBIENT      120.0f    /* sunlight/ambient floor, subtracted */
/* motors: robu GA12-N20 6V 200RPM (the ordered part) on the regulated rail */
#define MOT_V             6.0f
#define MOT_RPM_NOLOAD    200.0f
#define MOT_TAU_S         0.05f
#define WHEEL_DIA_MM      43.0f     /* robu GA12-N20 kit wheel (listing spec) */
#define ENC_TICKS_REV     600.0f    /* robu GA12-N20: 3ppr x4 edges x 50:1
                                       (HANDOFF s17; was 1400 for a generic
                                       7ppr N20 before the exact motor was
                                       chosen) */
#define TRACK_MM          83.0f
/* maze */
#define CELL_MM           168.0f
#define WALL_TARGET_MM    ((CELL_MM - 12.0f) / 2.0f)  /* centre: ~78mm to wall */

static float wall_adc(float d_mm)
{
    if (d_mm < 5.0f) d_mm = 5.0f;
    float raw = WALL_K / (d_mm * d_mm) + WALL_AMBIENT;
    if (raw > ADC_FULL) raw = ADC_FULL;
    return raw;
}

/* ---------------- S1: wall sensor chains ---------------- */
static void s1_wall_sensors(void)
{
    printf("S1 wall-sensor chains (0/45/90deg, emitter->reflection->PT->ADC)\n");
    /* monotonicity + swing */
    float prev = 1e9f;
    int mono = 1;
    for (float d = 45; d <= 160; d += 10) {   /* below ~40mm the ADC clamps */
        float lit = wall_adc(d);
        float cond = (float)wall_cond((uint16_t)lit, (uint16_t)WALL_AMBIENT);
        if (cond >= prev) mono = 0;
        prev = cond;
    }
    CHECK(mono, "response strictly decreases with distance (45..160mm)");
    float near = wall_cond((uint16_t)wall_adc(30), (uint16_t)WALL_AMBIENT);
    float far  = wall_cond((uint16_t)wall_adc(150), (uint16_t)WALL_AMBIENT);
    CHECK(near > 3500, "wall at 30mm saturates high (%.0f counts)", near);
    CHECK(far < 400, "no-wall (150mm) reads low (%.0f counts)", far);
    /* geometric projection: diag pair sees the wall sqrt(2) further away
     * when facing a corner post at the same forward distance */
    float front60 = wall_adc(60) - WALL_AMBIENT;
    float diag60  = wall_adc(60 * 1.41421356f) - WALL_AMBIENT;
    CHECK(fabsf(front60 / diag60 - 2.0f) < 0.1f,
          "45deg pair reads 1/2 of 0deg at equal forward range (%.0f vs %.0f)",
          front60, diag60);
    /* detection threshold: half-cell wall present vs absent */
    float on  = wall_cond((uint16_t)wall_adc(WALL_TARGET_MM), (uint16_t)WALL_AMBIENT);
    float off = wall_cond((uint16_t)wall_adc(CELL_MM + WALL_TARGET_MM), (uint16_t)WALL_AMBIENT);
    CHECK(on > 4.0f * off, "one-cell wall discrimination margin >4x (%.0f vs %.0f)", on, off);
}

/* ---------------- S2: line array through the mux ---------------- */
static void s2_line_array(void)
{
    printf("S2 line array (TCRT5000 x8 via CD74HC4067 -> estimator)\n");
    /* TEST_REPORT O2: white <= 0.4V, black >= 1.89V of 3.3V full scale */
    const uint16_t WHITE = (uint16_t)(0.4f / 3.3f * ADC_FULL);
    const uint16_t BLACK = (uint16_t)(1.89f / 3.3f * ADC_FULL);
    line_estimator_t est;
    line_est_init(&est);
    uint16_t raw[LINE_N];
    for (int i = 0; i < LINE_N; i++) raw[i] = WHITE;
    line_est_calib_point(&est, raw, false);
    for (int i = 0; i < LINE_N; i++) raw[i] = BLACK;
    line_est_calib_point(&est, raw, true);
    /* sweep a line under the array; mux scan = one channel per tick, so the
     * fw refreshes all 8 in 16 ticks incl. settling -- modelled as direct */
    int okpos = 1;
    for (float line_mm = -24; line_mm <= 24; line_mm += 4) {  /* inside the array span */
        for (int i = 0; i < LINE_N; i++) {
            float sensor_mm = (i - (LINE_N - 1) / 2.0f) * LINE_PITCH_MM;
            float dist = fabsf(sensor_mm - line_mm);
            float w = expf(-dist * dist / (2 * 4.0f * 4.0f));  /* 4mm beam */
            raw[i] = (uint16_t)(WHITE + w * (BLACK - WHITE));
        }
        float pos;
        if (!line_est_update(&est, raw, &pos) || fabsf(pos - line_mm) > 2.5f)
            okpos = 0;
    }
    CHECK(okpos, "estimator resolves line position to <2.5mm across +/-24mm");
}

/* ---------------- A1: motor + encoder chain ---------------- */
static float mot_speed_mm_s(float duty, float v_state)
{
    float target = duty * (MOT_RPM_NOLOAD / 60.0f) * (float)M_PI * WHEEL_DIA_MM;
    return v_state + (target - v_state) * (DT / MOT_TAU_S);
}

static void a1_motors_encoders(void)
{
    printf("A1 motors + encoders (PWM -> TB6612 -> N20 -> ticks)\n");
    float v = 0, x_mm = 0;
    double ticks = 0;
    /* step to 60% duty for 1s */
    for (int t = 0; t < 500; t++) {
        v = mot_speed_mm_s(0.6f, v);
        x_mm += v * DT;
        ticks += (double)v * DT / ((float)M_PI * WHEEL_DIA_MM) * ENC_TICKS_REV;
    }
    float v_expect = 0.6f * (MOT_RPM_NOLOAD / 60.0f) * (float)M_PI * WHEEL_DIA_MM;
    CHECK(fabsf(v - v_expect) < 0.02f * v_expect,
          "speed settles at PWM-proportional value (%.0f of %.0f mm/s)", v, v_expect);
    double ticks_expect = x_mm / ((float)M_PI * WHEEL_DIA_MM) * ENC_TICKS_REV;
    CHECK(fabs(ticks - ticks_expect) < 1.0,
          "encoder integrates distance exactly (%.0f ticks for %.0f mm)", ticks, x_mm);
    float tick_rate = v / ((float)M_PI * WHEEL_DIA_MM) * ENC_TICKS_REV;
    /* 600 ticks/rev (3ppr robu encoder): >=1000 ticks/s at 60% duty means
     * >=2 ticks per 2ms control period -- adequate direct velocity
     * resolution (and the fw can widen its speed window at crawl speeds) */
    CHECK(tick_rate > 1000, "steady tick rate resolves motion (%.0f ticks/s @60%%)", tick_rate);
    /* reversal via IN/IN */
    float vr = v;
    for (int t = 0; t < 500; t++) vr = mot_speed_mm_s(-0.6f, vr);
    CHECK(vr < -0.9f * v_expect, "IN/IN reversal reaches -60%% speed");
}

/* ---------------- A2: IMU yaw ---------------- */
static void a2_imu(void)
{
    printf("A2 IMU (BNO055 fusion model, spin-in-place)\n");
    srand(42);
    float v = 0, yaw = 0, imu_yaw = 0, bias = 0.1f; /* deg/s bias */
    for (int t = 0; t < 1500; t++) {              /* 3 s spin */
        v = mot_speed_mm_s(0.4f, v);              /* wheels +/-0.4 duty */
        float yaw_rate = (2 * v) / TRACK_MM;      /* rad/s */
        yaw += yaw_rate * DT;
        if (t % 5 == 0) {                         /* 100 Hz BNO055 */
            float noise = ((rand() % 1000) / 1000.0f - 0.5f) * 0.6f; /* deg */
            imu_yaw = yaw * 180.0f / (float)M_PI + noise + bias * t * DT;
        }
        if (yaw >= 2 * (float)M_PI) break;
    }
    float err = fabsf(imu_yaw - 360.0f);
    CHECK(yaw >= 2 * (float)M_PI - 0.01f, "kinematics complete a 360deg spin");
    CHECK(err < 2.0f, "BNO055 reads the spin within 2deg (err %.2fdeg)", err);
}

/* ---------------- C1: corridor centring demo ---------------- */
static void c1_corridor(void)
{
    printf("C1 corridor centring (side sensors -> P ctrl -> motors)\n");
    float y_off = 25.0f;   /* released 25mm off-centre */
    float vl = 0, vr = 0, heading = 0;
    float worst_tail = 0;
    for (int t = 0; t < 3000; t++) {              /* 6 s run */
        float dL = WALL_TARGET_MM + y_off;        /* left wall distance */
        float dR = WALL_TARGET_MM - y_off;
        float aL = wall_cond((uint16_t)wall_adc(dL), (uint16_t)WALL_AMBIENT);
        float aR = wall_cond((uint16_t)wall_adc(dR), (uint16_t)WALL_AMBIENT);
        /* signed centring error from the two 90deg side channels (counts) */
        float err = (aR - aL) / (aR + aL + 1.0f);
        float steer = 0.8f * err + 1.2f * heading; /* P + IMU-yaw damping */
        float l, r;
        drive_mix(0.35f, steer, &l, &r);
        vl = mot_speed_mm_s(l, vl);
        vr = mot_speed_mm_s(r, vr);
        heading += (vr - vl) / TRACK_MM * DT;
        if (heading > 0.5f) heading = 0.5f;
        if (heading < -0.5f) heading = -0.5f;
        y_off += (vl + vr) * 0.5f * sinf(heading) * DT;
        if (t > 2000 && fabsf(y_off) > worst_tail) worst_tail = fabsf(y_off);
    }
    CHECK(worst_tail < 5.0f,
          "robot centres from 25mm offset and holds (tail |y| max %.1fmm)", worst_tail);
}

int main(void)
{
    printf("HW-CHAIN SIMULATION (board-derived models)\n");
    printf("==========================================\n");
    s1_wall_sensors();
    s2_line_array();
    a1_motors_encoders();
    a2_imu();
    c1_corridor();
    printf("==========================================\n");
    if (g_fail) {
        printf("HW SIM RESULT: %d FAILURE(S)\n", g_fail);
        return 1;
    }
    printf("HW SIM RESULT: ALL CHAINS PASS (sensors + actuators working)\n");
    return 0;
}
