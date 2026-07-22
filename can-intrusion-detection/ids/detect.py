"""
detect.py -- live CAN intrusion detection on the Uno Q Linux side, laptop-
tethered mode (reads over USB serial).

This is now a thin CLI wrapper around ids_core.IDSScorer -- the actual
model-loading, scoring, and classification logic lives in ids_core.py, shared
with the on-device Custom Brick, so the two can never silently drift apart.

Usage:
    python detect.py --port /dev/ttyACM0

Requires model.keras, scaler.joblib, threshold.json from train.py.
"""

import argparse
import collections
import json
import time

import serial

from features import WINDOW_SIZE, FEATURE_NAMES
from ids_core import IDSScorer, ATTACK_NAMES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--cooldown", type=float, default=3.0, help="seconds between alerts")
    ap.add_argument("--dry-run", action="store_true",
                     help="compute and print anomalies but never write ALERT back to the "
                          "serial port -- isolates whether the write itself disrupts CAN "
                          "frame timing on the Uno Q")
    args = ap.parse_args()

    scorer = IDSScorer()
    print(f"Loaded model. Threshold = {scorer.threshold:.5f}")

    ser = serial.Serial(args.port, args.baud, timeout=1)
    window = collections.deque(maxlen=WINDOW_SIZE)
    last_alert = 0.0
    n = 0

    print("Detecting... (Ctrl-C to stop)")
    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if not line.startswith("{") or '"id"' not in line:
                continue
            try:
                f = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not all(k in f for k in ("t", "id", "dlc")):
                continue
            if f["id"] == 0x555:
                continue
            window.append(f)

            if len(window) < WINDOW_SIZE:
                continue

            n += 1
            if n % 10:
                continue

            frames = list(window)
            is_anomaly, err, atype, feat = scorer.score_window(frames)

            if is_anomaly and (time.time() - last_alert) > args.cooldown:
                score = min(255, int(err / scorer.threshold * 50))
                if not args.dry_run:
                    ser.write(f"ALERT,{atype},{score}\n".encode())
                print(f"  ANOMALY  err={err:.4f}  type={atype} ({ATTACK_NAMES[atype]})  score={score}"
                      + ("  [dry-run, no write sent]" if args.dry_run else ""))
                top = scorer.top_contributors(feat)
                print("    top contributors: " + ", ".join(f"{n}={v:.2f}" for n, v in top))
                print("    raw feature vector: " + ", ".join(f"{n}={round(x,2)}" for n, x in zip(FEATURE_NAMES, feat)))
                last_alert = time.time()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
