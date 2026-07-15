# CAN Intrusion Detection (WiFi infotainment attack surface + autoencoder IDS)

Adds an AI-based intrusion-detection layer and a realistic attack surface. The infotainment head unit
hosts a WiFi access point; an attacker who reaches it injects spoofed CAN frames,
and a separate gateway ECU running an **autoencoder** detects the anomaly and warns
the driver. This mirrors the 2015 Jeep Cherokee attack path (infotainment → CAN).

![architecture](../docs/architecture-can-intrusion-detection.png)

> Export the architecture diagram to `docs/architecture-can-intrusion-detection.png`.

## Nodes

| Node | Firmware / code | Role |
|------|-----------------|------|
| Camera ECU (Giga #1) | `firmware/giga1_camera_ecu/` | Unchanged from the Sensor Fusion Baseline feature — legit `0x101` baseline traffic |
| Infotainment (Giga #2) | `firmware/giga2_infotainment/` | WiFi AP + web dashboard; injects `spoof/flood/replay/fuzz`; shows the alert |
| WiFi AP checkpoint | `firmware/phase1_wifi_ap_test/` | Standalone test to prove the AP before integration |
| IDS gateway (Uno Q) | `firmware/unoq_can_forwarder/` + `ids/` | MCU streams frames to Linux; Python autoencoder scores them and broadcasts `0x555` |

## Why an autoencoder

Real attacks are open-ended and unlabeled. The autoencoder trains only on *normal*
traffic and flags anything that reconstructs poorly — so it generalises to attacks
it never saw. Detection leans on timing/frequency features (a spoofed `0x101`
doubles its rate and breaks its regular period).

## Host-side pipeline (`ids/`)

| Script | Purpose |
|--------|---------|
| `features.py` | Shared window feature extraction (identical in train + detect) |
| `capture.py` | Log CAN frames to labeled CSV |
| `train.py` | Train the autoencoder on normal data, pick a threshold |
| `detect.py` | Live inference; sends `ALERT,type,score` to the MCU on anomaly |

## Run it

```bash
# 1) flash all four firmware sketches (start with phase1_wifi_ap_test on Giga #2)
# 2) capture data on the Uno Q Linux side
cd ids && pip install -r requirements.txt
python capture.py --port /dev/ttyACM0 --label normal --out ../data/normal.csv
python capture.py --port /dev/ttyACM0 --label spoof  --out ../data/attack_spoof.csv
# 3) train
python train.py --normal ../data/normal.csv --attacks ../data/attack_spoof.csv
# 4) detect live
python detect.py --port /dev/ttyACM0
```

Connect a laptop to the `CarInfotainment` AP, trigger an injection from the
dashboard, and watch the alert reach the head unit's OLED and web page.

## Results

### v1 -- Initial training run

First real hardware capture: ~16 minutes of normal traffic (78 training
windows, WINDOW_SIZE=50 frames), plus one capture per attack type triggered
by clicking each dashboard injection link 5-10 times during a ~1 minute
window.

Threshold (99.5th pct of normal error): 1.46265

| Attack | Detection rate | Windows evaluated |
|--------|----------------|--------------------|
| Spoof  | 40.0%          | 35 |
| Flood  | 100.0%         | 7  |
| Replay | 100.0%         | 8  |
| Fuzz   | 100.0%         | 8  |

**Flood, replay, and fuzz were detected perfectly.** Each produces a large,
unambiguous statistical shift -- a 200-frame burst, a duplicated timing
pattern, or entirely foreign CAN IDs -- all of which stand out sharply against
the learned "normal" baseline.

**Spoof detection was weak (40%), and that's the attack that matters most**
for this project's threat model -- it's the one modeled directly on the real
Jeep Cherokee case study (https://www.wired.com/2015/07/hackers-remotely-kill-jeep-highway/)
that motivates the whole design (an attacker impersonating a legitimate ECU).
The likely cause: injectSpoof() sends exactly **one** extra 0x101 frame
per click, versus 200 frames per flood click or continuous foreign traffic
for fuzz. With only 5-10 clicks spread across a full minute of otherwise
normal traffic, the perturbation to the 0x101 timing/frequency features was
genuinely subtle -- arguably realistic for how a careful real-world attacker
would behave, but hard for a model trained on only ~78 normal windows to
separate confidently from natural jitter.

This is a legitimate, documented finding in CAN IDS research more broadly:
volume-based attacks (flooding, fuzzing) are inherently easier to detect via
timing/frequency features than stealthy identity-spoofing attacks that mimic
legitimate traffic patterns closely.

**Next step:** recapture spoof traffic with much more aggressive injection
(rapid repeated clicks rather than spread out) to give the model a stronger
signal, then retrain. Results below once that's complete.

### v2 -- Improved spoof detection (pending)

_To be filled in after recapturing spoof data with a stronger injection
signal and retraining._

| Attack | Detection rate | Windows evaluated |
|--------|----------------|--------------------|
| Spoof  | - | - |
| Flood  | - | - |
| Replay | - | - |
| Fuzz   | - | - |
