# ADAS_ECU_EdgeAI_Sensor_Fusion

**Multi-ECU Sensor Fusion with Autoencoder-Based Intrusion Detection and
Acoustic-Visual Emergency Vehicle Co-Detection with Infotainment Actuation**

A hands-on embedded-systems learning project that grows an automotive ADAS
prototype through a sequence of features, from a plain multi-node CAN sensor
network into an AI-enabled edge system. Built on real hardware: two Arduino
GIGA R1 WiFi boards (vehicle ECUs) and an Arduino UNO Q (Linux + MCU) on a
shared CAN bus.

The CAN bus is wired with **MCP2515 + transceiver** modules on the SPI/ICSP
header (the GIGA's built-in CAN controller is intentionally not used). Bus runs at
**500 kbps**, MCP2515 with an **8 MHz** crystal, chip-select on **D10** on every node.

## Features

| Feature | Folder | What it adds | Status |
|---------|--------|---------------|--------|
| Sensor Fusion Baseline | [`sensor-fusion-baseline/`](sensor-fusion-baseline/) | Multi-node CAN sensor network (camera + ultrasonic + aggregator) | ✅ Complete |
| CAN Intrusion Detection | [`can-intrusion-detection/`](can-intrusion-detection/) | WiFi infotainment attack surface + autoencoder-based CAN-bus IDS | ✅ Complete |
| Acoustic-Visual Emergency Detection | [`acoustic-visual-emergency-detection/`](acoustic-visual-emergency-detection/) | Audio siren detection + camera fusion + infotainment volume actuation | 🚧 Roadmap |

Each feature folder is a **self-contained, flashable project** with its own README,
firmware, and (where relevant) host-side code — so the progression is easy to read
on the GitHub timeline. Each feature was developed on its own branch and merged
into `main` once complete (see branch history / merge commits).

## Hardware

- 2× Arduino GIGA R1 WiFi (STM32H747, dual-core; Murata WiFi/BLE; u.FL antenna)
- 1× Arduino UNO Q (Qualcomm Dragonwing Linux MPU + STM32U585 MCU)
- 3× MCP2515 CAN controller + transceiver modules
- OV7670 camera, SSD1306 OLED, HC-SR04 ultrasonic
- Planned (Acoustic-Visual Emergency Detection): I2S MEMS microphone

## Shared references

- [`docs/can-message-map.md`](docs/can-message-map.md) — every CAN ID and payload layout
- [`docs/hardware-wiring.md`](docs/hardware-wiring.md) — pin assignments and bus wiring

## Glossary

| Term | Meaning in this project |
|------|--------------------------|
| **IVN** (In-Vehicle Network) | The formal term for the CAN bus connecting all ECUs in this prototype |
| **ECU** (Electronic Control Unit) | Each board (camera ECU, sensor/infotainment ECU, IDS gateway) acts as one |
| **Attack surface** | The infotainment node's WiFi AP — the wireless entry point an attacker uses to reach the CAN bus (CAN Intrusion Detection feature), mirroring the 2015 Jeep Cherokee case study |
| **Unsupervised anomaly detection** | The autoencoder trains only on normal traffic and flags anything that doesn't fit, rather than learning attack-specific signatures |
| **Reconstruction error thresholding** | The specific detection mechanism: a window's autoencoder reconstruction MSE above a learned threshold triggers an alert |
| **Sensor fusion** | The baseline feature performs early fusion (combining camera + ultrasonic signals into one vehicle-state view); the emergency-detection feature performs decision-level fusion (combining independent audio and visual verdicts into one emergency-vehicle decision) |
| **Actuation** | The emergency-detection feature's response goes beyond alerting — it changes system behavior (ducking infotainment volume) based on the fused detection |
| **Edge AI** | All inference (autoencoder, siren classifier) runs on-device (Uno Q's Linux side or GIGA's Cortex-M7), not in the cloud |

## Disclaimer

For education and defensive research on hardware you own. Do not connect to or test
against a real vehicle you are not authorised to work on.
