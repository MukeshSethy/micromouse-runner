// micromouse-pcb rev 6 -- GPIO map (single source: pcb/netlist.net; this
// header is GATED against the netlist by fw/check_pins.py, which fails the
// build chain if any assignment drifts from the board).
//
// Rev 6 deltas: TB6612 runs in IN/IN PWM mode (PWMA/PWMB tied high on the
// board -- the four IN pins ARE the PWM pins); STBY is tied high (motor kill
// = the MOT slide switch cutting the 6V rail); IO18/IO21 became the BNO055
// I2C bus; IO8 became the mux's 4th select; battery/VBUS telemetry moved
// onto mux channels 8-10; IO46 is a clean no-connect.
//
// All nets documented per-trace in pcb/CONNECTIONS.md.
#pragma once

// ---- analog inputs (ADC1: usable with WiFi active) -------------------------
#define PIN_WALL1_SENSE   1   // net WALL1_SENSE  (FRONT-L PT334-6B, 47k pull-up)
#define PIN_WALL2_SENSE   2   // net WALL2_SENSE  (FRONT-R)
#define PIN_WALL3_SENSE   3   // net WALL3_SENSE  (DIAG-L, exact 45 deg)
#define PIN_WALL4_SENSE   4   // net WALL4_SENSE  (DIAG-R)
#define PIN_WALL5_SENSE   5   // net WALL5_SENSE  (SIDE-L, exact 90 deg)
#define PIN_WALL6_SENSE   6   // net WALL6_SENSE  (SIDE-R)
#define PIN_MUX_SENSE     7   // net MUX_SENSE    (CD74HC4067 common Z)

// ---- motor driver (TB6612FNG, IN/IN PWM mode) -------------------------------
// PWMA/PWMB/STBY are tied high ON THE BOARD. Drive per Toshiba's IN/IN table:
//   forward: IN1 = PWM, IN2 = 0   (coast in the off-phase)
//   reverse: IN1 = 0,   IN2 = PWM
//   brake:   IN1 = IN2 = 1
#define PIN_AIN1          9   // net AIN1 (LEDC)
#define PIN_AIN2          10  // net AIN2 (LEDC)
#define PIN_BIN1          38  // net BIN1 (LEDC)
#define PIN_BIN2          45  // net BIN2 (LEDC; strap: 10k pulldown on board)

// ---- mux selects + emitter banks --------------------------------------------
#define PIN_MUX_S0        11  // net MUX_S0
#define PIN_MUX_S1        12  // net MUX_S1
#define PIN_MUX_S2        13  // net MUX_S2
#define PIN_MUX_S3        8   // net MUX_S3 (rev 6: channels 8-15 unlocked)
#define PIN_EMIT_FRONT    15  // net WALL_EMIT_FRONT (BSS138 bank gate)
#define PIN_EMIT_DIAG     16  // net WALL_EMIT_DIAG
#define PIN_EMIT_SIDE     17  // net WALL_EMIT_SIDE
#define PIN_EMIT_LINE     14  // net LINE_EMIT (latched ON in line mode so the
                              // hardware indicators read true floor state)

// ---- mux channel map (CD74HC4067) --------------------------------------------
#define MUXCH_LINE0       0   // LINE1_SENSE .. LINE8_SENSE on channels 0-7
#define MUXCH_VBAT        8   // VBAT_SENSE: pack/(100k:39k) -> V*39/139
#define MUXCH_BATMID      9   // BAT_MID_SENSE: cell-1/(100k:100k) -> V/2
#define MUXCH_VBUS        10  // VBUS_SENSE: 5V/(10k:15k) -> V*0.6

// ---- IMU (BNO055, I2C addr 0x28) ---------------------------------------------
#define PIN_IMU_SDA       18  // net IMU_SDA (4.7k pull-up on board)
#define PIN_IMU_SCL       21  // net IMU_SCL (4.7k pull-up on board)
#define PIN_IMU_INT       37  // net IMU_INT (BNO055 INT out)
#define IMU_I2C_ADDR      0x28   // internal osc (no external crystal)

// ---- encoders (PCNT hardware quadrature) ------------------------------------
#define PIN_ENC1_A        47  // net ENC1_A (motor A, 10k pull-up on board)
#define PIN_ENC1_B        48  // net ENC1_B
#define PIN_ENC2_A        44  // net ENC2_A_S3 side (1k UART0 guard on board)
#define PIN_ENC2_B        43  // net ENC2_B_S3 side (1k UART0 guard on board)

// ---- user I/O ----------------------------------------------------------------
#define PIN_BTN_A         0   // net on SW1: to GND, 10k pull-up (also BOOT strap)
#define PIN_BTN_B         35  // net on SW3: to GND, use INPUT_PULLUP (internal)
#define PIN_BTN_C         36  // net on SW4: to GND, use INPUT_PULLUP (internal)

// ---- battery policy (2S) -------------------------------------------------------
#define VBAT_DIVIDER      (139.0f / 39.0f)   // pack divider inverse
#define BATMID_DIVIDER    2.0f               // midpoint divider inverse
#define PACK_CUTOFF_V     6.6f               // 3.3V/cell floor
#define CELL_CUTOFF_V     3.3f               // per-cell floor (either cell)

// USB D-/D+ are the S3's native pins IO19/IO20 (flashing + CDC console).
// JTAG header J8: TCK=39 TDO=40 TDI=41 TMS=42. IO46 is NC (rev 6).
