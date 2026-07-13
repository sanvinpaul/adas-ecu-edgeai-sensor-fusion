# Sensor Fusion Baseline (multi-node CAN sensor network)

The foundation: three nodes cooperating over a CAN bus, no WiFi and no AI. This
feature proves the hardware, the bus, and a simple sensor-fusion display — the
platform every later feature builds on.

## Nodes

| Node | Firmware | Role |
|------|----------|------|
| Camera ECU (Giga #1) | `firmware/giga1_camera_ecu/` | Averages OV7670 frame brightness, sends visual-cue + brightness on `0x101` (~500 ms) |
| Sensor + Display (Giga #2) | `firmware/giga2_sensor_display/` | Reads ultrasonic distance → `0x102`; receives `0x101`; shows combined state on OLED |
| Aggregator (Uno Q) | `firmware/unoq_aggregator/` | Listens to all frames, prints consolidated JSON telemetry over Serial every 500 ms |

See [`../docs/can-message-map.md`](../docs/can-message-map.md) and
[`../docs/hardware-wiring.md`](../docs/hardware-wiring.md).

## What this demonstrates

- Multi-master CAN communication between heterogeneous boards.
- A basic ADAS pattern: a "visual cue" (brightness proxy) and a proximity warning
  combined into one vehicle-state view.
- A clean telemetry tap (the Uno Q JSON stream) that the CAN Intrusion Detection
  feature reuses to feed the AI.

## Run it

1. Flash each node with its matching sketch (Arduino IDE / CLI).
2. Power the bus; the OLED shows camera-connection status, brightness, visual cue,
   and distance.
3. Open the Uno Q serial monitor at 115200 baud to watch the JSON telemetry.

## Result

_Fill in with a photo of the OLED and a sample of the Uno Q JSON output._
