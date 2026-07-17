// micromouse-pcb rev 5.3 -- sample firmware with LINE-FOLLOWING mode.
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
static const float VBAT_MIN_V = 3.10f;                // soft cutoff per cell

// ---- state ------------------------------------------------------------------
static line_estimator_t g_line;
static pid_t g_pid;
static bool g_running = false;
static pcnt_unit_handle_t g_enc1, g_enc2;

// ---- motor driver -----------------------------------------------------------
static void motor_write(float left, float right) {
    // left = channel A, right = channel B (swap here if the build differs).
    auto ch = [](int in1, int in2, int pwm_pin, float v) {
        bool fwd = v >= 0;
        digitalWrite(in1, fwd ? HIGH : LOW);
        digitalWrite(in2, fwd ? LOW : HIGH);
        uint32_t duty = (uint32_t)(fabsf(v) * ((1 << PWM_RES) - 1));
        // Never command 100% duty into a possible stall: TB6612 at VM<4.5V
        // is only rated for sustained DC 0.4A without PWM (see TEST_REPORT
        // M2) -- cap at 97%.
        uint32_t cap = (uint32_t)(0.97f * ((1 << PWM_RES) - 1));
        if (duty > cap) duty = cap;
        ledcWrite(pwm_pin, duty);
    };
    ch(PIN_AIN1, PIN_AIN2, PIN_PWMA, left);
    ch(PIN_BIN1, PIN_BIN2, PIN_PWMB, right);
}

static void motors_enable(bool en) {
    digitalWrite(PIN_STBY, en ? HIGH : LOW);   // low = outputs Hi-Z (board
    if (!en) motor_write(0, 0);                // pulldown keeps it safe at boot)
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

static float vbat_read() {
    // 22k/33k divider: Vpin = Vbat * 33/55
    return analogReadMilliVolts(PIN_VBAT_SENSE) * (55.0f / 33.0f) / 1000.0f;
}

// ---- setup / loop --------------------------------------------------------------
void setup() {
    Serial.begin(115200);              // USB-CDC

    pinMode(PIN_STBY, OUTPUT);  digitalWrite(PIN_STBY, LOW);
    pinMode(PIN_AIN1, OUTPUT);  pinMode(PIN_AIN2, OUTPUT);
    pinMode(PIN_BIN1, OUTPUT);  pinMode(PIN_BIN2, OUTPUT);
    ledcAttach(PIN_PWMA, PWM_FREQ, PWM_RES);
    ledcAttach(PIN_PWMB, PWM_FREQ, PWM_RES);

    pinMode(PIN_MUX_S0, OUTPUT); pinMode(PIN_MUX_S1, OUTPUT); pinMode(PIN_MUX_S2, OUTPUT);
    pinMode(PIN_EMIT_FRONT, OUTPUT); pinMode(PIN_EMIT_DIAG, OUTPUT);
    pinMode(PIN_EMIT_SIDE, OUTPUT);  pinMode(PIN_EMIT_LINE, OUTPUT);
    digitalWrite(PIN_EMIT_LINE, LOW);

    pinMode(PIN_BTN_A, INPUT);         // 10k pull-up on the board (BOOT strap)
    pinMode(PIN_BTN_B, INPUT_PULLUP);  // internal pulls for B/C
    pinMode(PIN_BTN_C, INPUT_PULLUP);
    pinMode(PIN_VBUS_SENSE, INPUT);

    analogReadResolution(12);

    g_enc1 = enc_init(PIN_ENC1_A, PIN_ENC1_B);
    g_enc2 = enc_init(PIN_ENC2_A, PIN_ENC2_B);

    line_est_init(&g_line);
    pid_init(&g_pid, LF_KP, LF_KI, LF_KD, LF_I_CLAMP, LF_D_ALPHA);

    if (digitalRead(PIN_VBUS_SENSE))
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
        Serial.printf("[mm] vbat=%.2fV enc=%d/%d walls FL%u FR%u DL%u DR%u SL%u SR%u\n",
                      vbat_read(), e1, e2, w.front_l, w.front_r, w.diag_l,
                      w.diag_r, w.side_l, w.side_r);
    }
    a_prev = a; b_prev = b; c_prev = c;

    // --- battery guard ---
    if (g_running && vbat_read() < VBAT_MIN_V) {
        g_running = false;
        motors_enable(false);
        Serial.println("[mm] LOW BATTERY -- stopped");
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
