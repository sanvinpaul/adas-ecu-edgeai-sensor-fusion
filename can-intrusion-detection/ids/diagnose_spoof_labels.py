"""
diagnose_spoof_labels.py -- check whether the file-level "spoof" label in
attack_spoof.csv matches per-window ground truth, and report a corrected
detection rate.

train.py's reported detection rate labels EVERY window in an attack file as
an attack. But injectSpoof() only fires when the dashboard link is clicked --
the camera ECU keeps transmitting its own legitimate 0x101 the whole time too,
so many windows in a "spoof" capture may contain zero actually-injected
frames. Those windows are indistinguishable from normal traffic because they
ARE normal traffic; scoring them as missed detections understates the model.

Heuristic for "this 0x101 frame was injected": injectSpoof() always sends
payload [1, 255] (visual-cue flag + max brightness). Genuine camera readings
hitting exactly 255 are rare, so d1==255 is a reasonable proxy for "injected".

Usage (run from can-intrusion-detection/ids, after train.py has produced
model.keras / scaler.joblib / threshold.json):
    python diagnose_spoof_labels.py --csv ../data/attack_spoof.csv
"""

import argparse
import json

import joblib
import numpy as np
import pandas as pd
from tensorflow import keras

from features import window_features, WINDOW_SIZE


def csv_to_frames(path):
    df = pd.read_csv(path)
    frames = []
    for _, r in df.iterrows():
        dlc = int(r["dlc"])
        frames.append({
            "t": int(r["t"]),
            "id": int(r["id"]),
            "dlc": dlc,
            "d": [int(r[f"d{i}"]) for i in range(dlc)],
        })
    return frames


def window_has_injection(frames):
    """True if any 0x101 frame in this window looks like an injectSpoof() frame."""
    for f in frames:
        if f["id"] == 0x101 and len(f["d"]) >= 2 and f["d"][1] == 255:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    args = ap.parse_args()

    frames = csv_to_frames(args.csv)
    model = keras.models.load_model("model.keras")
    scaler = joblib.load("scaler.joblib")
    threshold = json.load(open("threshold.json"))["threshold"]

    n_windows = len(frames) // WINDOW_SIZE
    tp = fp = tn = fn = 0

    for i in range(n_windows):
        w = frames[i * WINDOW_SIZE: (i + 1) * WINDOW_SIZE]
        truth_attack = window_has_injection(w)

        feat = window_features(w)
        X = scaler.transform([feat])
        err = float(np.mean((X - model.predict(X, verbose=0)) ** 2))
        pred_attack = err > threshold

        if truth_attack:
            tp += int(pred_attack)
            fn += int(not pred_attack)
        else:
            fp += int(pred_attack)
            tn += int(not pred_attack)

    n_attack = tp + fn
    n_clean = fp + tn

    print(f"Total windows: {n_windows}")
    print(f"  Windows with >=1 injected frame (true attack): {n_attack}")
    print(f"  Windows with 0 injected frames (mislabeled 'spoof', actually normal): {n_clean}")
    print()
    if n_attack:
        print(f"Corrected detection rate (recall on TRUE attack windows only): "
              f"{tp}/{n_attack} = {100 * tp / n_attack:.1f}%")
    else:
        print("No windows contained an injected frame -- cannot compute detection rate.")
    if n_clean:
        print(f"False alarm rate on windows mislabeled 'spoof' but actually clean: "
              f"{fp}/{n_clean} = {100 * fp / n_clean:.1f}%")


if __name__ == "__main__":
    main()
