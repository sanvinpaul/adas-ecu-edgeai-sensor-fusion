# Acoustic-Visual Emergency Detection (siren + camera fusion, infotainment actuation) 🚧

> **Status: roadmap / not yet experimented.** This folder documents the planned
> design and commit sequence. Code lands here as each part is built.

## Goal

Add an **audio modality** to one GIGA R1 (an I2S MEMS microphone) and use it
alongside the existing camera to detect **emergency-vehicle sirens**, then act on
that detection in multiple ways — not only alerting the driver but also
**ducking the infotainment volume** while a siren is present.

## Planned use cases

1. **Siren detection** — classify siren vs non-siren from live audio on the edge.
2. **Camera + audio fusion** — combine the visual cue (the Sensor Fusion Baseline's brightness/flash
   proxy, later upgraded to light-bar detection) with audio for a more robust,
   lower-false-alarm emergency-vehicle warning.
3. **Driver alert** — OLED + infotainment banner when a siren is detected.
4. **Infotainment volume ducking** — automatically lower or mute music/media volume
   while a siren is active, then restore it afterwards.

## Planned CAN additions

| CAN ID | Sender | Payload |
|--------|--------|---------|
| `0x201` | Audio node | `[0]` siren detected, `[1]` confidence (0–255) |
| `0x202` | Fusion/action | `[0]` action code, `[1]` target volume level |

## Planned approach

- **Audio capture:** I2S MEMS mic (e.g. INMP441) into a GIGA; frame audio into
  short windows.
- **Features:** log-mel spectrogram / MFCCs per window.
- **Model:** a small siren classifier. Two viable routes —
  (a) **Edge Impulse / TinyML** deployed directly on the GIGA's Cortex-M7, or
  (b) train in Python and run inference on the **Uno Q Linux side** (consistent
  with the CAN Intrusion Detection feature's architecture).
- **Fusion:** simple rule or lightweight model combining `0x101` visual cue +
  `0x201` audio confidence into a single emergency-vehicle decision.
- **Actuation:** the infotainment node reacts to `0x202` by ducking media volume.

## Open questions to resolve during experimentation

- Mic placement and noise robustness (road/engine noise).
- On-GIGA TinyML vs Uno Q Python inference — latency and accuracy trade-off.
- Dataset: record local siren samples + negatives; consider public siren datasets.

## Planned phases

See the repository root sequence document for the full commit plan for this feature.
