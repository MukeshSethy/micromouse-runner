# Firmware

Firmware for the micromouse, split across the two socketed compute modules on the
carrier board (see [`../pcb`](../pcb)):

- **STM32 (NUCLEO-G431KB)** — real-time control: motor PWM via the TB6612,
  quadrature-encoder odometry, the 14-sensor IR array (stepped through the two
  HEF4067 muxes), maze solving, and motion planning.
- **ESP32 (Arduino Nano ESP32)** — wireless telemetry and a UART relay used to
  flash the STM32 over its ROM bootloader.

## Interface (from the board design)

| Link | Nets |
|---|---|
| ESP32 ↔ STM32 | `D0/RX ← USART1_TX`, `D1/TX → USART1_RX`, `D2 → STM32 NRST` |
| Sensor array | `MUX_S0..S3` select, `MUX_SENSE` (ADC), `LED_PULSE` |
| Motors | `PWMA/AIN1/AIN2`, `PWMB/BIN1/BIN2`, `STBY`; encoders `ENC1_A/B`, `ENC2_A/B` |
| Battery | `VBAT_CELL1_SENSE`, `VBAT_PACK_SENSE` (ADC), `USER_BTN` |

The full pin/GPIO allocation table lives in
[`../pcb/PROJECT_NOTES.md`](../pcb/PROJECT_NOTES.md) and the per-net rationale in
[`../pcb/CONNECTIONS.md`](../pcb/CONNECTIONS.md).

_Not yet implemented — placeholder for the firmware sources._
