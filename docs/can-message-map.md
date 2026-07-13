# CAN message map

Bus: 500 kbps · MCP2515 @ 8 MHz · standard 11-bit IDs.

| CAN ID | Sender | Feature | DLC | Payload layout |
|--------|--------|---------|-----|----------------|
| `0x101` | Camera ECU (Giga #1) | Sensor Fusion Baseline | 2 | `[0]` visual-cue flag, `[1]` avg brightness (0–255) |
| `0x102` | Sensor node (Giga #2) | Sensor Fusion Baseline | 3 | `[0]` proximity flag, `[1..2]` distance cm (big-endian) |
| `0x000` | Infotainment (Giga #2), **malicious** | CAN Intrusion Detection | 1 | flood/DoS payload (highest priority ID) |
| `0x555` | IDS gateway (Uno Q) | CAN Intrusion Detection | 3 | `[0]` alert active, `[1]` attack type, `[2]` anomaly score |
| `0x201` | Audio node (Giga), **planned** | Acoustic-Visual Emergency Detection | 2 | `[0]` siren detected, `[1]` confidence (0–255) |
| `0x202` | Fusion/action, **planned** | Acoustic-Visual Emergency Detection | 2 | `[0]` action code, `[1]` target volume level |

Attack type codes (0x555 byte 1): `0` none · `1` spoof · `2` flood · `3` replay · `4` fuzz.

Nominal timing (used by the CAN Intrusion Detection anomaly detector as the "normal" baseline):
`0x101` ≈ every 500 ms, `0x102` ≈ every 100 ms.
