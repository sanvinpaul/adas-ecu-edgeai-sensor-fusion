"""
ids_core.py -- reusable CAN intrusion detection scoring logic.

This is the portable core extracted from detect.py: model loading, window
scoring, and attack classification, with no CLI/argparse/serial-port
dependencies. Used by:
  - detect.py (laptop-tethered mode, reading over USB serial)
  - the App Lab Custom Brick (on-device mode, reading over the Bridge)

Both call the same IDSScorer class, so detection behavior is guaranteed
identical between laptop testing and on-device deployment -- there is only
one copy of the model-loading, scoring, and classification logic to keep in
sync, rather than two implementations that could silently drift apart.
"""

import json

import joblib
import numpy as np
from tensorflow import keras

from features import window_features, FEATURE_NAMES

# Attack-type codes, shared with the firmware's attackName() switch.
NONE, SPOOF, FLOOD, REPLAY, FUZZ, UNKNOWN = 0, 1, 2, 3, 4, 5

ATTACK_NAMES = {
    NONE: "NONE",
    SPOOF: "SPOOF",
    FLOOD: "FLOOD",
    REPLAY: "REPLAY",
    FUZZ: "FUZZ",
    UNKNOWN: "UNKNOWN",
}


def classify(feat, window):
    """Heuristic label for the anomaly (the autoencoder only says 'anomalous').

    Takes the raw window frames too (not just the feature vector) so it can
    check for injectSpoof()'s exact payload signature directly, which is what
    distinguishes spoof from replay -- both disrupt 0x101 timing identically
    in feature space, so feat alone can't tell them apart.
    """
    f = dict(zip(FEATURE_NAMES, feat))
    # injectFlood() sends 200 frames of 0x000 in a fast burst -- but real
    # testing showed most of that burst never reaches Python at all: CAN
    # frames arrive roughly every ~260us at 500kbps, while printing one JSON
    # line over serial takes several milliseconds, so the Uno Q can't keep up
    # and drops most flood frames at the CAN-controller level. What survives
    # to a scored window is often just 1-2 frames -- volume-based detection
    # (counting foreign-ID frames) can't reliably distinguish that from a
    # single fuzz click. Instead, check for the specific ID directly:
    # injectFlood() always targets exactly 0x000, while injectFuzz() picks a
    # random ID across 0-0x7FF (only a 1-in-2048 chance of ever coinciding
    # with 0x000), so presence of 0x000 at all is a reliable flood signature
    # regardless of how many frames actually survived the pipeline.
    has_flood_id = any(fr["id"] == 0x000 for fr in window)
    if f["frames_per_sec"] > 2000 or has_flood_id:
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
    # None of the above matched -- this is a real, model-flagged anomaly
    # (e.g. mean_payload_delta spiking from rapid ultrasonic variation like
    # fast hand-waving, well beyond anything in training) but it doesn't
    # match any known attack's signature. Labeling it SPOOF by default was
    # actively misleading; UNKNOWN is honest about what the heuristic
    # actually knows here -- the autoencoder detected something abnormal,
    # but classify() can't identify it as a specific attack type.
    return UNKNOWN


class IDSScorer:
    """Loads a trained model/scaler/threshold once, scores windows repeatedly.

    Usage:
        scorer = IDSScorer()
        is_anomaly, err, atype, feat = scorer.score_window(frames)
    """

    def __init__(self, model_path="model.keras", scaler_path="scaler.joblib",
                 threshold_path="threshold.json"):
        self.model = keras.models.load_model(model_path)
        self.scaler = joblib.load(scaler_path)
        with open(threshold_path) as fh:
            self.threshold = json.load(fh)["threshold"]

    def score_window(self, frames):
        """Score one window of CAN frames (list of dicts with t/id/dlc/d).

        Returns (is_anomaly: bool, err: float, attack_type: int, feat: list).
        Does not apply any alert cooldown -- cooldown policy differs between
        laptop and on-device use, so that's left to the caller.
        """
        feat = window_features(frames)
        X = self.scaler.transform([feat])
        pred = self.model.predict(X, verbose=0)
        err = float(np.mean((X - pred) ** 2))

        is_anomaly = err > self.threshold
        attack_type = classify(feat, frames) if is_anomaly else NONE

        return is_anomaly, err, attack_type, feat

    def top_contributors(self, feat, n=3):
        """Return the top-n highest-residual features, for diagnostics."""
        X = self.scaler.transform([feat])
        pred = self.model.predict(X, verbose=0)
        resid = (X - pred)[0] ** 2
        pairs = sorted(zip(FEATURE_NAMES, resid), key=lambda kv: -kv[1])
        return pairs[:n]
