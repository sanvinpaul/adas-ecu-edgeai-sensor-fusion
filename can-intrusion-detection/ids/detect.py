"""
detect.py -- live CAN intrusion detection on the Uno Q Linux side.

Reads the per-frame JSON stream from the MCU forwarder, maintains a rolling
window, computes features, and runs the trained autoencoder. When the
reconstruction error exceeds the learned threshold, it flags an intrusion and
sends "ALERT,<type>,<score>" back to the MCU, which broadcasts frame 0x555 so the
infotainment head unit warns the driver.

Usage:
    python detect.py --port /dev/ttyACM0

Requires model.keras, scaler.joblib, threshold.json from train.py.
"""

import argparse
import collections
import json
import time

import joblib
import numpy as np
import serial
from tensorflow import keras

from features import window_features, WINDOW_SIZE, FEATURE_NAMES

# Attack-type codes shared with the firmware.
NONE, SPOOF, FLOOD, REPLAY, FUZZ = 0, 1, 2, 3, 4


def classify(feat):
    """Heuristic label for the anomaly (the autoencoder only says 'anomalous')."""
    f = dict(zip(FEATURE_NAMES, feat))
    if f["frames_per_sec"] > 2000 or f["n_unique_ids"] <= 2 and f["count_0x101"] == 0 and f["count_0x102"] == 0:
        return FLOOD
    if f["n_unique_ids"] >= 6 or f["id_entropy"] > 2.5:
        return FUZZ
    if f["count_0x101"] > 20 or f["iat_std_0x101"] > f["iat_mean_0x101"]:
        return SPOOF   # includes replay; both inflate/disrupt 0x101 timing
    return SPOOF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--cooldown", type=float, default=3.0, help="seconds between alerts")
    args = ap.parse_args()

    model = keras.models.load_model("model.keras")
    scaler = joblib.load("scaler.joblib")
    threshold = json.load(open("threshold.json"))["threshold"]
    print(f"Loaded model. Threshold = {threshold:.5f}")

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
                window.append(json.loads(line))
            except json.JSONDecodeError:
                continue

            if len(window) < WINDOW_SIZE:
                continue

            n += 1
            if n % 10:            # score every 10th frame to keep it light
                continue

            feat = window_features(list(window))
            X = scaler.transform([feat])
            err = float(np.mean((X - model.predict(X, verbose=0)) ** 2))

            if err > threshold and (time.time() - last_alert) > args.cooldown:
                atype = classify(feat)
                score = min(255, int(err / threshold * 50))
                ser.write(f"ALERT,{atype},{score}\n".encode())
                print(f"  ANOMALY  err={err:.4f}  type={atype}  score={score}")
                last_alert = time.time()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
