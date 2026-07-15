"""
train.py -- train an autoencoder anomaly detector on NORMAL CAN traffic only.

Approach (unsupervised): the autoencoder learns to reconstruct feature vectors
drawn from normal traffic. At inference, an anomalous window reconstructs poorly,
so a high reconstruction error (MSE) flags an intrusion. We never train on attack
data -- that is the point, since real attacks are open-ended and unlabeled.

Usage:
    python train.py --normal ../data/normal.csv \
                    --attacks ../data/attack_spoof.csv ../data/attack_flood.csv

Outputs (loaded by detect.py):
    model.keras      the trained autoencoder
    scaler.joblib    the fitted StandardScaler
    threshold.json   reconstruction-error cutoff
"""

import argparse
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from features import frames_to_windows, FEATURE_NAMES, WINDOW_SIZE


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


def build_autoencoder(n_features):
    inp = keras.Input(shape=(n_features,))
    x = layers.Dense(8, activation="relu")(inp)
    x = layers.Dense(4, activation="relu")(x)          # bottleneck
    x = layers.Dense(8, activation="relu")(x)
    out = layers.Dense(n_features, activation="linear")(x)
    ae = keras.Model(inp, out)
    ae.compile(optimizer="adam", loss="mse")
    return ae


def recon_error(model, X):
    pred = model.predict(X, verbose=0)
    return np.mean((X - pred) ** 2, axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--normal", required=True)
    ap.add_argument("--attacks", nargs="*", default=[])
    ap.add_argument("--epochs", type=int, default=120)
    args = ap.parse_args()

    print(f"Window size: {WINDOW_SIZE} frames | features: {len(FEATURE_NAMES)}")

    X_norm = np.array(frames_to_windows(csv_to_frames(args.normal)), dtype=float)
    print(f"Normal windows: {len(X_norm)}")

    X_tr, X_val = train_test_split(X_norm, test_size=0.2, random_state=42)

    scaler = StandardScaler().fit(X_tr)

    # A short, single-session capture can make a feature look far more
    # consistent than it really is in general operation (e.g. iat_mean_0x101
    # measured ~0.1ms std here, when tens of ms of jitter is completely
    # normal in practice). StandardScaler divides by that tiny std, so any
    # realistic live deviation gets amplified into an astronomical z-score.
    # Floor each feature's scale at 2% of its own mean magnitude (with a
    # small absolute floor for near-zero-mean features) so normalization
    # stays proportionate instead of runaway-sensitive to under-sampled
    # low-variance features.
    min_scale = np.maximum(0.02 * np.abs(scaler.mean_), 1e-3)
    scaler.scale_ = np.maximum(scaler.scale_, min_scale)

    X_tr_s, X_val_s = scaler.transform(X_tr), scaler.transform(X_val)

    ae = build_autoencoder(X_tr_s.shape[1])
    ae.fit(
        X_tr_s, X_tr_s,
        validation_data=(X_val_s, X_val_s),
        epochs=args.epochs, batch_size=16, verbose=2,
        callbacks=[keras.callbacks.EarlyStopping(patience=15, restore_best_weights=True)],
    )

    # Threshold: 99.5th percentile of reconstruction error on normal validation data.
    val_err = recon_error(ae, X_val_s)
    threshold = float(np.percentile(val_err, 99.5))
    print(f"Threshold (99.5th pct of normal error): {threshold:.5f}")

    # Report detection rate on any attack captures provided.
    for path in args.attacks:
        Xa = np.array(frames_to_windows(csv_to_frames(path)), dtype=float)
        if len(Xa) == 0:
            continue
        err = recon_error(ae, scaler.transform(Xa))
        rate = float(np.mean(err > threshold))
        print(f"  {path}: detection rate = {rate:.1%} ({len(Xa)} windows)")

    ae.save("model.keras")
    joblib.dump(scaler, "scaler.joblib")
    with open("threshold.json", "w") as fh:
        json.dump({"threshold": threshold, "window": WINDOW_SIZE}, fh)
    print("Saved model.keras, scaler.joblib, threshold.json")


if __name__ == "__main__":
    main()
