// micromouse-pcb 2-LAYER JLCPCB edition -- sample firmware.
// WALL-FOLLOWING maze runner. (The TCRT5000 line array + CD74HC4067 mux were
// removed on this board, so line-following is gone; the 6 IR wall sensors +
// BNO055 IMU drive the run.)  Arduino-ESP32 core 3.x (board: "ESP32S3 Dev
// Module", USB CDC on boot: ON).
//
// Hardware contract (all gated against the board's netlist):
//   pins.h            GPIO map (checked by fw/check_pins.py)
//   control_core.c/h  reusable control logic (pid / drive_mix / wall_cond) --
//                     the SAME file is compiled + exercised by fw/sim/
//
// FLASH + DEBUG over ONE cable: the ESP32-S3 NATIVE USB-Serial-JTAG (IO19/IO20
// on the USB-C port) is both the flash / CDC-console endpoint AND a full
// OpenOCD/gdb JTAG TAP -- no external probe and no JTAG header (removed on this
// board). Verified in fw/sim_flash.py (stages 2 + 6).
//
// Buttons (rear edge):
//   A (BOOT) short press : start / stop the run
//   B                    : re-zero heading + re-baseline the RGB to idle
//   C                    : print a telemetry snapshot over USB-CDC
//   RST                  : hardware reset (hold A while tapping RST = ROM
//                          downloader; the USB-Serial-JTAG also auto-resets)
//
// The wall indicator LEDs are HARDWARE-driven off the sense nets -- no code
// here touches them; they always show the true sensor state.

#include <Arduino.h>
#include <Wire.h>
#include "driver/pulse_cnt.h"
#include "pins.h"
extern "C" {
#include "control_core.h"
}

// ---- tunables ---------------------------------------------------------------
static const uint32_t LOOP_HZ = 500;                  // control loop rate
static const int PWM_FREQ = 20000, PWM_RES = 10;      // LEDC: 20 kHz, 10-bit
// Wall-follow gains: steer from the side-wall imbalance (centre the corridor),
// slow + pivot when a front wall closes in. Reuses the shared pid_t so the
// controller math is the same code the host sim exercises.
static const float WF_KP = 0.010f, WF_KI = 0.0f, WF_KD = 0.0016f;
static const float WF_I_CLAMP = 3.0f, WF_D_ALPHA = 0.30f;
static const float WF_BASE_SPEED = 0.40f;
static const uint16_t WALL_FRONT_STOP = 900;   // conditioned front reading => wall ahead
// battery policy comes from pins.h: PACK_CUTOFF_V (2S pack floor)

// ---- state ------------------------------------------------------------------
static pid_t g_pid;
static bool g_running = false;
static pcnt_unit_handle_t g_enc1, g_enc2;
static float g_hdg_zero = 0.0f;

// ---- motor driver (TB6612 IN/IN PWM mode) -----------------------------------
// PWMA/PWMB/STBY are tied high on the board; all four IN pins carry LEDC.
//   forward: IN1 = PWM, IN2 = 0 (fast-decay/coast off-phase)
//   reverse: IN1 = 0,   IN2 = PWM
// The 6V rail is REGULATED (TPS54302), so PWM duty maps to a stable voltage
// across the whole 6.6-8.4V pack window.
// STALL WATCHDOG (sim_preflight M2): N20 stall is 1.6A but the TB6612 channel
// rating is 1.2A CONTINUOUS (3.2A peak). If a wheel is commanded hard (>60%
// duty) but its encoder shows no motion for STALL_MS, cut both motors until
// the command drops -- protects the driver in crashes/blocked wheels.
static const uint32_t STALL_MS = 800;
static uint32_t stall_t0[2] = {0, 0};
static bool stall_latched = false;
static bool stall_check(int idx, float v, int32_t enc_delta, uint32_t now_ms) {
    if (fabsf(v) > 0.60f && enc_delta == 0) {
        if (stall_t0[idx] == 0) stall_t0[idx] = now_ms;
        if (now_ms - stall_t0[idx] > STALL_MS) stall_latched = true;
    } else {
        stall_t0[idx] = 0;
        if (fabsf(v) < 0.10f) stall_latched = false;   // release on low command
    }
    return stall_latched;
}

static void motor_write(float left, float right) {
    if (stall_latched) { left = 0; right = 0; }
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
    // no STBY GPIO -- the hardware kill is the MOT slide switch (SW6, 6V rail
    // EN). Software "disable" = zero all four IN duties (driver coasts).
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

// ---- wall sensors (pulsed banks, ambient-subtracted) ------------------------
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

// ---- battery telemetry (2-layer: DIRECT ADC, PACK-LEVEL only) ---------------
// Per-cell/balance monitoring removed (no J9 connector / BAT_MID divider). The
// 2S pack floor guards the pack; a balance-charged LiPo stays cell-matched.
static float vpack_read()  { return analogReadMilliVolts(PIN_VBAT_SENSE) * VBAT_DIVIDER / 1000.0f; }
static bool  vbus_present() { return analogReadMilliVolts(PIN_VBUS_SENSE) > 1500; }  // raw >1.5V = cable

static bool battery_ok() { return vpack_read() > PACK_CUTOFF_V; }

// ---- buzzer (IO46 -> 220R -> MMBT2222A -> CMT-8504, 4kHz rated) -------------
static void buzz_init() {
    ledcAttach(PIN_BUZZER, 4000, 8);   // 4kHz = the transducer's rated frequency
    ledcWrite(PIN_BUZZER, 0);          // silent (NPN off)
}
// short blocking beeps -- used at rare events only (boot/run/stop/warnings),
// never inside the 500Hz control path
static void beep(uint16_t ms, uint8_t n = 1) {
    for (uint8_t i = 0; i < n; i++) {
        ledcWrite(PIN_BUZZER, 128);    // 50% duty square
        delay(ms);
        ledcWrite(PIN_BUZZER, 0);
        if (i + 1 < n) delay(60);
    }
}

// ---- indicators: STATUS heartbeat LED + WS2812B RGB (ESP-driven) ------------
static void led_init() {
    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);
}
// single WS2812B via the ESP32 core helper (no external library needed)
static void rgb_set(uint8_t r, uint8_t g, uint8_t b) { rgbLedWrite(PIN_RGB_DATA, r, g, b); }

// ---- IMU (BNO055, minimal register driver) ----------------------------------
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
static int imu_read8(uint8_t reg) {
    Wire.beginTransmission(IMU_I2C_ADDR);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return -1;
    if (Wire.requestFrom((int)IMU_I2C_ADDR, 1) != 1) return -1;
    return Wire.read();
}
// IMU FUNCTIONAL SELF-TEST (gated by fw/sim_preflight.py I6):
// 1. CHIP_ID (0x00) must read 0xA0 -- the BNO055 needs ~400ms from cold power
//    to answer, so retry rather than fail on the first read.
// 2. ST_RESULT (0x36) bits 0-3 are the chip's power-on self-test verdicts for
//    ACC/MAG/GYR/MCU -- all four must be 1.
static bool imu_selftest() {
    int id = -1;
    for (int i = 0; i < 10 && id != 0xA0; i++) {
        id = imu_read8(0x00);
        if (id != 0xA0) delay(50);
    }
    if (id != 0xA0) {
        Serial.printf("[mm] IMU SELF-TEST FAIL: CHIP_ID 0x%02X (want 0xA0)\n", id);
        return false;
    }
    int st = imu_read8(0x36);
    if ((st & 0x0F) != 0x0F) {
        Serial.printf("[mm] IMU SELF-TEST FAIL: POST 0x%X (want 0xF = MCU|GYR|MAG|ACC)\n",
                      st & 0x0F);
        return false;
    }
    return true;
}
static void imu_init() {
    Wire.begin(PIN_IMU_SDA, PIN_IMU_SCL, 400000);
    Wire.beginTransmission(IMU_I2C_ADDR);
    if (Wire.endTransmission() != 0) {
        Serial.println("[mm] IMU: not found on I2C 0x28");
        beep(60, 4);                  // distinct 4-chirp = IMU problem
        return;
    }
    if (!imu_selftest()) { beep(60, 4); return; }
    imu_write(0x3D, 0x00);            // OPR_MODE = CONFIG
    delay(25);
    imu_write(0x3F, 0x00);            // SYS_TRIGGER: INTERNAL oscillator (XIN32 is NC on this board)
    delay(20);
    imu_write(0x3D, 0x0C);            // OPR_MODE = NDOF (fusion on-chip, 100Hz)
    delay(20);
    // fusion sanity: SYS_STATUS (0x39) = 5 "fusion running", SYS_ERR (0x3A) = 0.
    // NDOF startup can take a few tens of ms -- poll briefly.
    int sys = 0, err = 0;
    for (int i = 0; i < 20; i++) {
        sys = imu_read8(0x39);
        err = imu_read8(0x3A);
        if (sys == 5 && err == 0) break;
        delay(25);
    }
    if (sys != 5 || err != 0) {
        Serial.printf("[mm] IMU: fusion not running (SYS_STATUS=%d SYS_ERR=%d)\n", sys, err);
        beep(60, 4);
        return;                       // g_imu_ok stays false -> yaw reads 0, run degraded
    }
    g_imu_ok = true;
    Serial.println("[mm] IMU: BNO055 self-test PASS, NDOF fusion up (internal osc)");
}
// yaw rate (gyro Z), deg/s -- the control-loop-grade signal for turns
static float imu_gyro_z() { return g_imu_ok ? imu_read16(0x18) / 16.0f : 0.0f; }
// fused heading, deg 0-360
static float imu_heading() { return g_imu_ok ? imu_read16(0x1A) / 16.0f : 0.0f; }

// ---- setup / loop -----------------------------------------------------------
void setup() {
    Serial.begin(115200);              // USB-CDC (native USB-Serial-JTAG)

    // IN/IN mode: all four IN pins are LEDC channels
    ledcAttach(PIN_AIN1, PWM_FREQ, PWM_RES);
    ledcAttach(PIN_AIN2, PWM_FREQ, PWM_RES);
    ledcAttach(PIN_BIN1, PWM_FREQ, PWM_RES);
    ledcAttach(PIN_BIN2, PWM_FREQ, PWM_RES);
    motor_write(0, 0);

    pinMode(PIN_EMIT_FRONT, OUTPUT); pinMode(PIN_EMIT_DIAG, OUTPUT);
    pinMode(PIN_EMIT_SIDE, OUTPUT);
    digitalWrite(PIN_EMIT_FRONT, LOW);
    digitalWrite(PIN_EMIT_DIAG, LOW);
    digitalWrite(PIN_EMIT_SIDE, LOW);

    pinMode(PIN_BTN_A, INPUT);         // 10k pull-up on the board (BOOT strap)
    pinMode(PIN_BTN_B, INPUT_PULLUP);  // internal pulls for B/C
    pinMode(PIN_BTN_C, INPUT_PULLUP);
    pinMode(PIN_IMU_INT, INPUT);

    analogReadResolution(12);

    g_enc1 = enc_init(PIN_ENC1_A, PIN_ENC1_B);
    g_enc2 = enc_init(PIN_ENC2_A, PIN_ENC2_B);

    pid_init(&g_pid, WF_KP, WF_KI, WF_KD, WF_I_CLAMP, WF_D_ALPHA);

    led_init();
    rgb_set(16, 16, 16);               // dim white = booting
    buzz_init();                       // before imu_init: its fail-beep needs LEDC live
    imu_init();
    g_hdg_zero = imu_heading();

    if (vbus_present())
        Serial.println("[mm] USB cable detected -- CDC telemetry live");
    Serial.println("[mm] A=run/stop  B=zero-heading  C=telemetry");
    rgb_set(0, g_imu_ok ? 24 : 0, g_imu_ok ? 0 : 0);   // green idle, red if IMU down
    if (!g_imu_ok) rgb_set(24, 0, 0);
    digitalWrite(PIN_STATUS_LED, HIGH);
    beep(60, 2);                       // ready
}

void loop() {
    static uint32_t t_next = micros();
    static uint32_t loop_us = 1000000UL / LOOP_HZ;

    // --- STATUS LED heartbeat (2 Hz idle, 8 Hz running) ---
    static uint32_t hb_next = 0; static bool hb = false;
    uint32_t now = millis();
    if (now >= hb_next) {
        hb = !hb;
        digitalWrite(PIN_STATUS_LED, hb);
        hb_next = now + (g_running ? 60 : 250);
    }

    // --- buttons (edge-detected, crude debounce via loop rate) ---
    static bool a_prev = true, b_prev = true, c_prev = true;
    bool a = digitalRead(PIN_BTN_A), b = digitalRead(PIN_BTN_B), c = digitalRead(PIN_BTN_C);
    if (!a && a_prev) {
        g_running = !g_running;
        motors_enable(g_running);
        rgb_set(g_running ? 0 : 0, g_running ? 0 : 24, g_running ? 40 : 0);  // blue run / green idle
        Serial.printf("[mm] %s\n", g_running ? "RUN" : "STOP");
        beep(g_running ? 40 : 120);   // short = run, long = stop
        delay(30);
    }
    if (!b && b_prev) {                 // re-zero heading + RGB back to idle
        g_hdg_zero = imu_heading();
        rgb_set(0, 24, 0);
        Serial.printf("[mm] heading zeroed at %.1f deg\n", g_hdg_zero);
        beep(40);
    }
    if (!c && c_prev) {
        int e1 = 0, e2 = 0;
        pcnt_unit_get_count(g_enc1, &e1);
        pcnt_unit_get_count(g_enc2, &e2);
        WallReading w = wall_scan();
        float pack = vpack_read();
        Serial.printf("[mm] pack=%.2fV gz=%.1fdps hdg=%.1f "
                      "enc=%d/%d walls FL%u FR%u DL%u DR%u SL%u SR%u\n",
                      pack, imu_gyro_z(), imu_heading() - g_hdg_zero,
                      e1, e2, w.front_l, w.front_r, w.diag_l,
                      w.diag_r, w.side_l, w.side_r);
    }
    a_prev = a; b_prev = b; c_prev = c;

    // --- battery guard (2S: pack floor AND either-cell floor) ---
    static uint8_t bat_div = 0;
    if (g_running && ++bat_div >= 50) {        // 10Hz check
        bat_div = 0;
        if (!battery_ok()) {
            g_running = false;
            motors_enable(false);
            rgb_set(40, 0, 0);        // solid red = low battery
            Serial.println("[mm] LOW BATTERY (pack or cell floor) -- stopped");
            beep(250, 3);             // unmistakable: land the bot, swap the pack
        }
    }

    // --- wall-following control loop ---
    if (g_running) {
        WallReading w = wall_scan();
        bool front_blocked = ((uint32_t)w.front_l + w.front_r) / 2 > WALL_FRONT_STOP;
        // side error: brighter (closer) wall on one side -> steer away from it.
        // +err = left wall closer -> +steer = turn right (away). Fold the
        // diagonals in for earlier corner reaction.
        float err = ((float)w.side_l - (float)w.side_r)
                    + 0.5f * ((float)w.diag_l - (float)w.diag_r);
        float steer = pid_step(&g_pid, err, 1.0f / LOOP_HZ);
        float base = WF_BASE_SPEED;
        if (front_blocked) {
            // wall ahead: stop forward, pivot toward the more open side
            base = 0.0f;
            steer = (w.side_l > w.side_r) ? 0.6f : -0.6f;
        } else {
            // IMU yaw assist: damp uncommanded rotation on the straights
            steer -= 0.004f * imu_gyro_z();
        }
        float l, r;
        drive_mix(base, steer, &l, &r);
        // stall watchdog: hard command + frozen encoder = cut drive (M2)
        static int se1p = 0, se2p = 0;
        int se1 = 0, se2 = 0;
        pcnt_unit_get_count(g_enc1, &se1);
        pcnt_unit_get_count(g_enc2, &se2);
        uint32_t now_ms = millis();
        stall_check(0, l, se1 - se1p, now_ms);
        stall_check(1, r, se2 - se2p, now_ms);
        se1p = se1; se2p = se2;
        static bool stall_beeped = false;
        if (stall_latched && !stall_beeped) {
            rgb_set(40, 8, 0);        // amber = stall watchdog tripped
            beep(80, 2);              // motors were just cut by the watchdog
            stall_beeped = true;
        } else if (!stall_latched) {
            stall_beeped = false;
        }
        motor_write(l, r);
    }

    while ((int32_t)(micros() - t_next) < 0) { /* pace */ }
    t_next += loop_us;
}
