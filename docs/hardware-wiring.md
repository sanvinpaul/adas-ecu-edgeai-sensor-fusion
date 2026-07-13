# Hardware wiring

## CAN (all three nodes)

Each node uses an MCP2515 + transceiver module on the SPI/ICSP header:

| MCP2515 pin | Connects to |
|-------------|-------------|
| VCC | 5 V (module logic; ensure the module is 3.3 V-logic safe for the GIGA/UNO Q) |
| GND | GND |
| CS  | D10 |
| SO  | MISO |
| SI  | MOSI |
| SCK | SCK |
| INT | (polled in firmware; not required) |

- Giga #1 uses **SPI1** for CAN (`MCP_CAN CAN(&SPI1, 10)`).
- Giga #2 and Uno Q use the **default SPI** bus (`MCP_CAN CAN(10)`).
- Bus: 500 kbps, MCP2515 8 MHz crystal. CAN_H/CAN_L daisy-chained across all
  nodes with 120 Ω termination at both ends of the bus.

## Giga #1 — Camera ECU
- OV7670 camera on the GIGA Arducam connector.

## Giga #2 — Sensor / Infotainment
- SSD1306 OLED on I2C (SDA/SCL).
- HC-SR04 ultrasonic: TRIG = D2, ECHO = D3.
- CAN Intrusion Detection feature: u.FL WiFi antenna on **J14** (required for usable AP range).

## Uno Q — Aggregator / IDS
- CAN via MCP2515 on the STM32 MCU side.
- CAN Intrusion Detection feature: Python detector runs on the Qualcomm/Linux side, reaching the MCU as a
  serial device (`ls /dev/tty*`).

## Acoustic-Visual Emergency Detection (planned)
- I2S MEMS microphone (e.g. INMP441) on one GIGA: SCK, WS, SD, plus VCC/GND.
