// micromouse-pcb rev 5.3 -- GPIO map (single source: pcb/netlist.net; this
// header is GATED against the netlist by fw/check_pins.py, which fails the
// build chain if any assignment drifts from the board).
//
// All nets documented per-trace in pcb/CONNECTIONS.md.
#pragma once

// ---- analog inputs (ADC1: usable with WiFi active) -------------------------
#define PIN_WALL1_SENSE   1   // net WALL1_SENSE  (FRONT-L PT334-6B, 47k pull-up)
#define PIN_WALL2_SENSE   2   // net WALL2_SENSE  (FRONT-R)
#define PIN_WALL3_SENSE   3   // net WALL3_SENSE  (DIAG-L)
#define PIN_WALL4_SENSE   4   // net WALL4_SENSE  (DIAG-R)
#define PIN_WALL5_SENSE   5   // net WALL5_SENSE  (SIDE-L)
#define PIN_WALL6_SENSE   6   // net WALL6_SENSE  (SIDE-R)
#define PIN_MUX_SENSE     7   // net MUX_SENSE    (CD74HC4067 common Z: line array)
#define PIN_VBAT_SENSE    8   // net VBAT_SENSE   (22k/33k divider: Vbat*0.6)

// ---- motor driver (TB6612FNG) ----------------------------------------------
#define PIN_AIN1          9   // net AIN1
#define PIN_AIN2          10  // net AIN2
#define PIN_PWMA          18  // net PWMA  (LEDC)
#define PIN_BIN1          38  // net BIN1
#define PIN_BIN2          45  // net BIN2  (strap: 10k pulldown on board)
#define PIN_PWMB          21  // net PWMB  (LEDC)
#define PIN_STBY          46  // net STBY  (strap: 10k pulldown; low = outputs Hi-Z)

// ---- line mux selects + emitter banks ---------------------------------------
#define PIN_MUX_S0        11  // net MUX_S0
#define PIN_MUX_S1        12  // net MUX_S1
#define PIN_MUX_S2        13  // net MUX_S2 (S3 select is hard-grounded: 8 ch)
#define PIN_EMIT_FRONT    14  // net WALL_EMIT_FRONT (BSS138 bank gate)
#define PIN_EMIT_DIAG     15  // net WALL_EMIT_DIAG
#define PIN_EMIT_SIDE     16  // net WALL_EMIT_SIDE
#define PIN_EMIT_LINE     17  // net LINE_EMIT (latched ON in line mode so the
                              // hardware indicators read true floor state)

// ---- encoders (PCNT hardware quadrature) ------------------------------------
#define PIN_ENC1_A        47  // net ENC1_A (motor A, 10k pull-up on board)
#define PIN_ENC1_B        48  // net ENC1_B
#define PIN_ENC2_A        44  // net ENC2_A_S3 side (1k UART0 guard on board)
#define PIN_ENC2_B        43  // net ENC2_B_S3 side (1k UART0 guard on board)

// ---- user I/O ----------------------------------------------------------------
#define PIN_BTN_A         0   // net on SW1: to GND, 10k pull-up (also BOOT strap)
#define PIN_BTN_B         35  // net on SW3: to GND, use INPUT_PULLUP (internal)
#define PIN_BTN_C         36  // net on SW4: to GND, use INPUT_PULLUP (internal)
#define PIN_VBUS_SENSE    37  // net VBUS_SENSE (USB cable detect, 10k/15k divider)

// USB D-/D+ are the S3's native pins IO19/IO20 (flashing + CDC console).
// JTAG header J8: TCK=39 TDO=40 TDI=41 TMS=42.
