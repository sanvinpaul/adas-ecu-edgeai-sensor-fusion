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


def classify(feat, window):
    """Heuristic label for the anomaly (the autoencoder only says 'anomalous').

    Takes the raw window frames too (not just the feature vector) so it can
    check for injectSpoof()'s exact payload signature directly, which is what
    distinguishes spoof from replay -- both disrupt 0x101 timing identically
    in feature space, so feat alone can't tell them apart.
    """
    f = dict(zip(FEATURE_NAMES, feat))
    if f["frames_per_sec"] > 2000 or f["n_unique_ids"] <= 2 and f["count_0x101"] == 0 and f["count_0x102"] == 0:
        return FLOOD
    # injectFuzz() sends exactly ONE random-ID frame per click, which bumps
    # n_unique_ids from 2 to 3 -- not 6. The original >=6 threshold never
    # realistically triggered given how the injector actually behaves.
    if f["n_unique_ids"] >= 3 or f["id_entropy"] > 1.3:
        return FUZZ
    # Thresholds grounded in observed training data (two independent capture
    # sessions): count_0x101 never exceeded 27, iat_std_0x101 never exceeded
    # ~6.6ms. The original ">20" / "std > mean" checks were both essentially
    # always-true or always-false under real traffic, causing nearly every
    # anomaly (regardless of actual cause) to get labeled SPOOF/REPLAY.
    if f["count_0x101"] > 30 or f["iat_std_0x101"] > 15:
        # Disrupted 0x101 timing -- spoof always sends the fixed [1, 255]
        # payload; replay re-sends a previously genuine (and thus more
        # varied) captured payload. Check for spoof's known signature byte
        # directly in the raw window rather than guessing from aggregates.
        has_spoof_signature = any(
            fr["id"] == 0x101 and len(fr.get("d", [])) >= 2 and fr["d"][1] == 255
            for fr in window
        )
        return SPOOF if has_spoof_signature else REPLAY
    return SPOOF


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
                f = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not all(k in f for k in ("t", "id", "dlc")):
                continue
            window.append(f)

            if len(window) < WINDOW_SIZE:
                continue

            n += 1
            if n % 10:            # score every 10th frame to keep it light
                continue

            feat = window_features(list(window))
            X = scaler.transform([feat])
            err = float(np.mean((X - model.predict(X, verbose=0)) ** 2))

            if err > threshold and (time.time() - last_alert) > args.cooldown:
                atype = classify(feat, list(window))
                score = min(255, int(err / threshold * 50))
                if not args.dry_run:
                    ser.write(f"ALERT,{atype},{score}\n".encode())
                print(f"  ANOMALY  err={err:.4f}  type={atype}  score={score}"
                      + ("  [dry-run, no write sent]" if args.dry_run else ""))
                resid = (X - model.predict(X, verbose=0))[0] ** 2
                top = sorted(zip(FEATURE_NAMES, resid), key=lambda kv: -kv[1])[:3]
                print("    top contributors: " + ", ".join(f"{n}={v:.2f}" for n, v in top))
                print("    raw feature vector: " + ", ".join(f"{n}={round(x,2)}" for n, x in zip(FEATURE_NAMES, feat)))
                last_alert = time.time()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
