// micromouse-pcb 2-LAYER JLCPCB edition -- GPIO map (single source of truth:
// pcb/JLCPCB_2layers/design/netlist.net; this header is GATED against that
// netlist by fw/check_pins.py, which fails the build chain if any assignment
// drifts from the board).
//
// Deltas vs the 4-layer rev-7.2 board:
//   * line-sensor array (TCRT5000 x8) + CD74HC4067 mux + per-line indicator
//     LEDs REMOVED -> no PIN_MUX_*, no PIN_EMIT_LINE, no mux channel map.
//   * battery / VBUS telemetry moved OFF the mux onto DIRECT ADC1 inputs
//     (IO7/IO8/IO9).
//   * AIN1 moved IO9 -> IO11 (IO9 now carries VBUS_SENSE).
//   * JTAG header (J8) removed -> IO39-42 are NC; flashing + debug are over
//     the ESP32-S3 native USB-Serial-JTAG only (IO19/IO20 via the USB-C port).
//   * added ESP-driven indicators: STATUS_LED (IO12) + WS2812B RGB (IO14).
// Two-switch scheme unchanged: SW5 = ALL logic rails, SW6 = 6V motor rail.
//
// All nets documented per-trace in the design's CONNECTIONS.md.
#pragma once

// ---- analog wall sensors (ADC1: GPIO1-10, usable with WiFi active) ----------
#define PIN_WALL1_SENSE   1   // net WALL1_SENSE  (FRONT-L PT334-6B, 47k pull-up)
#define PIN_WALL2_SENSE   2   // net WALL2_SENSE  (FRONT-R)
#define PIN_WALL3_SENSE   3   // net WALL3_SENSE  (DIAG-L, exact 45 deg)
#define PIN_WALL4_SENSE   4   // net WALL4_SENSE  (DIAG-R)
#define PIN_WALL5_SENSE   5   // net WALL5_SENSE  (SIDE-L, exact 90 deg)
#define PIN_WALL6_SENSE   6   // net WALL6_SENSE  (SIDE-R)

// ---- battery / bus telemetry (DIRECT ADC1 -- mux removed on 2-layer) --------
#define PIN_VBAT_SENSE    7   // net VBAT_SENSE     pack / (100k:39k)  = V*39/139
#define PIN_BATMID_SENSE  8   // net BAT_MID_SENSE  cell-1 / (100k:100k) = V/2
#define PIN_VBUS_SENSE    9   // net VBUS_SENSE     5V / (10k:15k)     = V*0.6

// ---- motor driver (TB6612FNG, IN/IN PWM mode) -------------------------------
// PWMA/PWMB/STBY are tied high ON THE BOARD. Drive per Toshiba's IN/IN table:
//   forward: IN1 = PWM, IN2 = 0   (coast in the off-phase)
//   reverse: IN1 = 0,   IN2 = PWM
//   brake:   IN1 = IN2 = 1
#define PIN_AIN1          11  // net AIN1 (LEDC)   [moved IO9 -> IO11; IO9 = VBUS_SENSE]
#define PIN_AIN2          10  // net AIN2 (LEDC)
#define PIN_BIN1          38  // net BIN1 (LEDC)
#define PIN_BIN2          45  // net BIN2 (LEDC; strap: 10k pulldown on board -> VDD_SPI 3.3V)

// ---- IR wall-emitter banks (BSS138 low-side gates, pulsed) ------------------
#define PIN_EMIT_FRONT    15  // net WALL_EMIT_FRONT
#define PIN_EMIT_DIAG     16  // net WALL_EMIT_DIAG
#define PIN_EMIT_SIDE     17  // net WALL_EMIT_SIDE

// ---- IMU (BNO055, I2C addr 0x28) --------------------------------------------
#define PIN_IMU_SDA       18  // net IMU_SDA (4.7k pull-up on board)
#define PIN_IMU_SCL       21  // net IMU_SCL (4.7k pull-up on board)
#define PIN_IMU_INT       37  // net IMU_INT (BNO055 INT out)
#define IMU_I2C_ADDR      0x28   // internal osc (no external crystal)

// ---- encoders (PCNT hardware quadrature) ------------------------------------
#define PIN_ENC1_A        47  // net ENC1_A (motor A, 10k pull-up on board)
#define PIN_ENC1_B        48  // net ENC1_B
#define PIN_ENC2_A        44  // net ENC2_A_S3 side (1k UART0 guard on board)
#define PIN_ENC2_B        43  // net ENC2_B_S3 side (1k UART0 guard on board)

// ---- ESP-driven indicators (2-layer additions) -----------------------------
#define PIN_STATUS_LED    12  // net STATUS_LED (1k -> D31 SMD status LED; dev-board heartbeat)
#define PIN_RGB_DATA      14  // net RGB_DATA   (D32 WS2812B addressable RGB; 3.3V data OK)
// D30 power LED is hardwired to +3V3 and D33 motor LED to VM_6V -- no GPIO.

// ---- user I/O ---------------------------------------------------------------
#define PIN_BTN_A         0   // net USER_BTN  on SW1 -> GND, 10k pull-up (also BOOT strap)
#define PIN_BTN_B         35  // net USER_BTN2 on SW3 -> GND, use INPUT_PULLUP (internal)
#define PIN_BTN_C         36  // net USER_BTN3 on SW4 -> GND, use INPUT_PULLUP (internal)
#define PIN_BUZZER        46  // net BUZZ_CTRL: 220R -> MMBT2222A base -> CMT-8504 magnetic
                              // buzzer (4kHz rated). Strap-safe: the base load only ever
                              // pulls IO46 LOW (its boot default); LEDC ~4kHz square = beep.

// ---- battery policy (2S) ----------------------------------------------------
#define VBAT_DIVIDER      (139.0f / 39.0f)   // pack divider inverse (100k:39k)
#define BATMID_DIVIDER    2.0f               // midpoint divider inverse (100k:100k)
#define VBUS_DIVIDER      (25.0f / 15.0f)    // VBUS divider inverse (10k:15k)
#define PACK_CUTOFF_V     6.6f               // 3.3V/cell floor
#define CELL_CUTOFF_V     3.3f               // per-cell floor (either cell)
#define BALANCE_ABSENT_V  0.5f               // cell-1 below this = J9 balance lead not
                                             // plugged (R75/R76 drain the sense node to
                                             // ~0V) -> pack-only monitoring

// USB D-/D+ are the S3 native pins IO19/IO20 (flashing + CDC console).
// 2-layer: NO JTAG header -- IO39-42 are NC; debug is over native USB only.
