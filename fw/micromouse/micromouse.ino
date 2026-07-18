// micromouse-pcb rev 6 -- sample firmware with LINE-FOLLOWING mode.
// Arduino-ESP32 core (board: "ESP32S3 Dev Module", USB CDC on boot: ON).
//
// Hardware contract (all gated against the board's netlist):
//   pins.h            GPIO map (checked by fw/check_pins.py)
//   control_core.c/h  the control logic -- the SAME file is compiled and
//                     exercised by the host simulation in fw/sim/
//
// Modes (buttons on the rear edge):
//   A (BOOT) short press : start / stop line following
//   B                    : line calibration sweep (hold near/over the line)
//   C                    : print telemetry snapshot over USB-CDC
//   RST                  : hardware reset; hold A while plugging USB = ROM
//                          downloader (flash without any button dance via
//                          the native USB-Serial-JTAG anyway)
//
// The wall/line indicator LEDs are HARDWARE-driven (comparator-free FET
// stages on the sense nets) -- no code here touches them; they always show
// the true sensor state.

#include <Arduino.h>
#include <Wire.h>
#include "driver/pulse_cnt.h"
#include "pins.h"
extern "C" {
#include "control_core.h"
}

// ---- tunables ---------------------------------------------------------------
static const uint32_t LOOP_HZ = 500;                  // control loop rate
static const float BASE_SPEED = LF_BASE_SPEED;        // gains live in
// control_core.h, shared with the host simulation -- tuned there first
static const int PWM_FREQ = 20000, PWM_RES = 10;      // LEDC: 20 kHz, 10-bit
// battery policy comes from pins.h: PACK_CUTOFF_V / CELL_CUTOFF_V (2S)

// ---- state ------------------------------------------------------------------
static line_estimator_t g_line;
static pid_t g_pid;
static bool g_running = false;
static pcnt_unit_handle_t g_enc1, g_enc2;

// ---- motor driver (rev 6: TB6612 IN/IN PWM mode) ------------------------------
// PWMA/PWMB/STBY are tied high on the board; all four IN pins carry LEDC.
//   forward: IN1 = PWM, IN2 = 0 (fast-decay/coast off-phase)
//   reverse: IN1 = 0,   IN2 = PWM
// The 6V rail is REGULATED (TPS54302), so PWM duty maps to a stable voltage
// across the whole 6.6-8.4V pack window.
static void motor_write(float left, float right) {
    auto ch = [](int in1, int in2, float v) {
        uint32_t duty = (uint32_t)(fabsf(v) * ((1 << PWM_RES) - 1));
        // Cap at 97%: never command DC into a possible stall (TEST_REPORT M2).
        uint32_t cap = (uint32_t)(0.97f * ((1 << PWM_RES) - 1));
        if (duty > cap) duty = cap;
        if (v >= 0) { ledcWrite(in2, 0);    ledcWrite(in1, duty); }
        else        { ledcWrite(in1, 0);    ledcWrite(in2, duty); }
    };
    ch(PIN_AIN1, PIN_AIN2, left);
    ch(PIN_BIN1, PIN_BIN2, right);
}

static void motors_enable(bool en) {
    // rev 6: no STBY GPIO -- the hardware kill is the MOT slide switch (6V
    // rail EN). Software "disable" = zero all four IN duties (driver coasts).
    if (!en) motor_write(0, 0);
}

// ---- encoders (PCNT hardware quadrature, x4 decoding) -----------------------
static pcnt_unit_handle_t enc_init(int pin_a, int pin_b) {
    pcnt_unit_config_t ucfg = {};
    ucfg.low_limit = -32768; ucfg.high_limit = 32767;
    ucfg.flags.accum_count = 1;
    pcnt_unit_handle_t unit;
    ESP_ERROR_CHECK(pcnt_new_unit(&ucfg, &unit));
    pcnt_chan_config_t c1 = {}; c1.edge_gpio_num = pin_a; c1.level_gpio_num = pin_b;
    pcnt_chan_config_t c2 = {}; c2.edge_gpio_num = pin_b; c2.level_gpio_num = pin_a;
    pcnt_channel_handle_t ch1, ch2;
    ESP_ERROR_CHECK(pcnt_new_channel(unit, &c1, &ch1));
    ESP_ERROR_CHECK(pcnt_new_channel(unit, &c2, &ch2));
    pcnt_channel_set_edge_action(ch1, PCNT_CHANNEL_EDGE_ACTION_DECREASE, PCNT_CHANNEL_EDGE_ACTION_INCREASE);
    pcnt_channel_set_level_action(ch1, PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_INVERSE);
    pcnt_channel_set_edge_action(ch2, PCNT_CHANNEL_EDGE_ACTION_INCREASE, PCNT_CHANNEL_EDGE_ACTION_DECREASE);
    pcnt_channel_set_level_action(ch2, PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_INVERSE);
    pcnt_unit_enable(unit);
    pcnt_unit_clear_count(unit);
    pcnt_unit_start(unit);
    return unit;
}

// ---- line array (CD74HC4067 scan) --------------------------------------------
static void mux_select(uint8_t ch) {
    digitalWrite(PIN_MUX_S0, ch & 1);
    digitalWrite(PIN_MUX_S1, (ch >> 1) & 1);
    digitalWrite(PIN_MUX_S2, (ch >> 2) & 1);
    digitalWrite(PIN_MUX_S3, (ch >> 3) & 1);   // rev 6: channels 8-15 live
}

static uint16_t mux_read_mv(uint8_t ch) {
    mux_select(ch);
    delayMicroseconds(8);                      // settle through 100k-class source Z
    return analogReadMilliVolts(PIN_MUX_SENSE);
}

static void line_scan(uint16_t raw[LINE_N]) {
    for (uint8_t ch = 0; ch < LINE_N; ch++) {
        mux_select(ch);                 // LINE1..8 = Y0..Y7
        delayMicroseconds(6);           // mux settle through 47k source Z
        raw[ch] = analogRead(PIN_MUX_SENSE);
    }
}

// ---- wall sensors (pulsed banks, ambient-subtracted) --------------------------
struct WallReading { uint16_t front_l, front_r, diag_l, diag_r, side_l, side_r; };

static WallReading wall_scan() {
    auto rd = [](int pin) { return (uint16_t)analogRead(pin); };
    WallReading amb = { rd(PIN_WALL1_SENSE), rd(PIN_WALL2_SENSE), rd(PIN_WALL3_SENSE),
                        rd(PIN_WALL4_SENSE), rd(PIN_WALL5_SENSE), rd(PIN_WALL6_SENSE) };
    WallReading out;
    digitalWrite(PIN_EMIT_FRONT, HIGH); delayMicroseconds(80);
    out.front_l = wall_cond(rd(PIN_WALL1_SENSE), amb.front_l);
    out.front_r = wall_cond(rd(PIN_WALL2_SENSE), amb.front_r);
    digitalWrite(PIN_EMIT_FRONT, LOW);
    digitalWrite(PIN_EMIT_DIAG, HIGH); delayMicroseconds(80);
    out.diag_l = wall_cond(rd(PIN_WALL3_SENSE), amb.diag_l);
    out.diag_r = wall_cond(rd(PIN_WALL4_SENSE), amb.diag_r);
    digitalWrite(PIN_EMIT_DIAG, LOW);
    digitalWrite(PIN_EMIT_SIDE, HIGH); delayMicroseconds(80);
    out.side_l = wall_cond(rd(PIN_WALL5_SENSE), amb.side_l);
    out.side_r = wall_cond(rd(PIN_WALL6_SENSE), amb.side_r);
    digitalWrite(PIN_EMIT_SIDE, LOW);
    return out;
}

// ---- battery telemetry (rev 6: via mux channels; per-cell 2S monitoring) -----
static float vpack_read()  { return mux_read_mv(MUXCH_VBAT) * VBAT_DIVIDER / 1000.0f; }
static float vcell1_read() { return mux_read_mv(MUXCH_BATMID) * BATMID_DIVIDER / 1000.0f; }
static bool  vbus_present() { return mux_read_mv(MUXCH_VBUS) > 1500; }

static bool battery_ok() {
    float pack = vpack_read(), c1 = vcell1_read(), c2 = pack - c1;
    return pack > PACK_CUTOFF_V && c1 > CELL_CUTOFF_V && c2 > CELL_CUTOFF_V;
}

// ---- IMU (BNO055, minimal register driver) ------------------------------------
static bool g_imu_ok = false;
static bool imu_write(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(IMU_I2C_ADDR);
    Wire.write(reg); Wire.write(val);
    return Wire.endTransmission() == 0;
}
static int imu_read16(uint8_t reg) {
    Wire.beginTransmission(IMU_I2C_ADDR);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return 0;
    if (Wire.requestFrom((int)IMU_I2C_ADDR, 2) != 2) return 0;
    int lo = Wire.read(), hi = Wire.read();
    return (int16_t)((hi << 8) | lo);
}
static void imu_init() {
    Wire.begin(PIN_IMU_SDA, PIN_IMU_SCL, 400000);
    Wire.beginTransmission(IMU_I2C_ADDR);
    if (Wire.endTransmission() != 0) { Serial.println("[mm] IMU: not found"); return; }
    imu_write(0x3D, 0x00);            // OPR_MODE = CONFIG
    delay(25);
    imu_write(0x3F, 0x00);            // SYS_TRIGGER: INTERNAL oscillator (rev 6.1: no crystal)
    delay(20);
    imu_write(0x3D, 0x0C);            // OPR_MODE = NDOF (fusion on-chip, 100Hz)
    delay(20);
    g_imu_ok = true;
    Serial.println("[mm] IMU: BNO055 NDOF up (internal osc)");
}
// yaw rate (gyro Z), deg/s -- the control-loop-grade signal for turns
static float imu_gyro_z() { return g_imu_ok ? imu_read16(0x18) / 16.0f : 0.0f; }
// fused heading, deg 0-360
static float imu_heading() { return g_imu_ok ? imu_read16(0x1A) / 16.0f : 0.0f; }

// ---- setup / loop --------------------------------------------------------------
void setup() {
    Serial.begin(115200);              // USB-CDC

    // rev 6 IN/IN mode: all four IN pins are LEDC channels
    ledcAttach(PIN_AIN1, PWM_FREQ, PWM_RES);
    ledcAttach(PIN_AIN2, PWM_FREQ, PWM_RES);
    ledcAttach(PIN_BIN1, PWM_FREQ, PWM_RES);
    ledcAttach(PIN_BIN2, PWM_FREQ, PWM_RES);
    motor_write(0, 0);

    pinMode(PIN_MUX_S0, OUTPUT); pinMode(PIN_MUX_S1, OUTPUT);
    pinMode(PIN_MUX_S2, OUTPUT); pinMode(PIN_MUX_S3, OUTPUT);
    pinMode(PIN_EMIT_FRONT, OUTPUT); pinMode(PIN_EMIT_DIAG, OUTPUT);
    pinMode(PIN_EMIT_SIDE, OUTPUT);  pinMode(PIN_EMIT_LINE, OUTPUT);
    digitalWrite(PIN_EMIT_LINE, LOW);

    pinMode(PIN_BTN_A, INPUT);         // 10k pull-up on the board (BOOT strap)
    pinMode(PIN_BTN_B, INPUT_PULLUP);  // internal pulls for B/C
    pinMode(PIN_BTN_C, INPUT_PULLUP);
    pinMode(PIN_IMU_INT, INPUT);

    analogReadResolution(12);

    g_enc1 = enc_init(PIN_ENC1_A, PIN_ENC1_B);
    g_enc2 = enc_init(PIN_ENC2_A, PIN_ENC2_B);

    line_est_init(&g_line);
    pid_init(&g_pid, LF_KP, LF_KI, LF_KD, LF_I_CLAMP, LF_D_ALPHA);

    imu_init();

    if (vbus_present())
        Serial.println("[mm] USB cable detected -- CDC telemetry live");
    Serial.println("[mm] A=run/stop  B=calibrate  C=telemetry");
}

void loop() {
    static uint32_t t_next = micros();
    static uint32_t loop_us = 1000000UL / LOOP_HZ;

    // --- buttons (edge-detected, crude debounce via loop rate) ---
    static bool a_prev = true, b_prev = true, c_prev = true;
    bool a = digitalRead(PIN_BTN_A), b = digitalRead(PIN_BTN_B), c = digitalRead(PIN_BTN_C);
    if (!a && a_prev) {
        g_running = !g_running;
        digitalWrite(PIN_EMIT_LINE, g_running ? HIGH : LOW);  // latched: HW
        motors_enable(g_running);                             // indicators live
        Serial.printf("[mm] %s\n", g_running ? "RUN" : "STOP");
        delay(30);
    }
    if (!b && b_prev) {                 // calibration sweep: 3 s, wiggle over line
        Serial.println("[mm] calibrating: sweep the array across the line...");
        digitalWrite(PIN_EMIT_LINE, HIGH);
        uint32_t t0 = millis();
        uint16_t raw[LINE_N];
        while (millis() - t0 < 3000) {
            line_scan(raw);
            line_est_calib_point(&g_line, raw, (millis() - t0) > 1500);
            delay(5);
        }
        digitalWrite(PIN_EMIT_LINE, g_running ? HIGH : LOW);
        Serial.println("[mm] calibration done");
    }
    if (!c && c_prev) {
        int e1 = 0, e2 = 0;
        pcnt_unit_get_count(g_enc1, &e1);
        pcnt_unit_get_count(g_enc2, &e2);
        WallReading w = wall_scan();
        float pack = vpack_read(), c1 = vcell1_read();
        Serial.printf("[mm] pack=%.2fV c1=%.2fV c2=%.2fV gz=%.1fdps hdg=%.1f "
                      "enc=%d/%d walls FL%u FR%u DL%u DR%u SL%u SR%u\n",
                      pack, c1, pack - c1, imu_gyro_z(), imu_heading(),
                      e1, e2, w.front_l, w.front_r, w.diag_l,
                      w.diag_r, w.side_l, w.side_r);
    }
    a_prev = a; b_prev = b; c_prev = c;

    // --- battery guard (2S: pack floor AND either-cell floor) ---
    static uint8_t bat_div = 0;
    if (g_running && ++bat_div >= 50) {        // 10Hz check; mux reads cost us
        bat_div = 0;
        if (!battery_ok()) {
            g_running = false;
            motors_enable(false);
            Serial.println("[mm] LOW BATTERY (pack or cell floor) -- stopped");
        }
    }

    // --- control loop ---
    if (g_running) {
        uint16_t raw[LINE_N];
        line_scan(raw);
        float pos_mm;
        bool seen = line_est_update(&g_line, raw, &pos_mm);
        if (!seen) g_pid.i_acc *= 0.95f;      // no integrator windup in gaps
        float steer = pid_step(&g_pid, pos_mm, 1.0f / LOOP_HZ);
        float base = seen ? BASE_SPEED : BASE_SPEED * 0.5f;   // slow when lost
        float l, r;
        drive_mix(base, steer, &l, &r);
        motor_write(l, r);
    }

    while ((int32_t)(micros() - t_next) < 0) { /* pace */ }
    t_next += loop_us;
}
