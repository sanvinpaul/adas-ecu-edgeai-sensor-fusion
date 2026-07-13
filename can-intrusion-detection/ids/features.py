"""
Shared feature extraction for the CAN IDS.

Both training (train.py) and live detection (detect.py) MUST use these exact
functions, otherwise the model sees different feature distributions at inference
time than it was trained on. Keep all feature logic here.

A "frame" is a dict: {"t": <micros:int>, "id": <int>, "dlc": <int>, "d": [int,...]}

We slide a fixed-size window over the frame stream and turn each window into a
fixed-length feature vector. Injection attacks are visible mostly through
*timing / frequency* changes, so the features focus on inter-arrival times,
per-ID rates, and ID-set entropy.
"""

import math
from collections import defaultdict

# IDs we explicitly track (the legitimate periodic ECUs on the bus).
TRACKED_IDS = [0x101, 0x102]

WINDOW_SIZE = 50          # frames per window
FEATURE_NAMES = (
    [f"count_{hex(i)}" for i in TRACKED_IDS]
    + [f"iat_mean_{hex(i)}" for i in TRACKED_IDS]
    + [f"iat_std_{hex(i)}" for i in TRACKED_IDS]
    + ["n_unique_ids", "id_entropy", "frames_per_sec", "mean_payload_delta"]
)


def _inter_arrival_stats(times_us):
    """Mean/std of gaps (in ms) between consecutive timestamps for one ID."""
    if len(times_us) < 2:
        return 0.0, 0.0
    gaps = [(times_us[i] - times_us[i - 1]) / 1000.0 for i in range(1, len(times_us))]
    mean = sum(gaps) / len(gaps)
    var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
    return mean, math.sqrt(var)


def window_features(frames):
    """Turn a list of frame dicts (one window) into a fixed-length feature list."""
    per_id_times = defaultdict(list)
    per_id_last_payload = {}
    payload_deltas = []
    id_counts = defaultdict(int)

    for f in frames:
        fid = f["id"]
        per_id_times[fid].append(f["t"])
        id_counts[fid] += 1

        payload = tuple(f.get("d", []))
        if fid in per_id_last_payload:
            prev = per_id_last_payload[fid]
            n = min(len(prev), len(payload))
            delta = sum(abs(payload[i] - prev[i]) for i in range(n))
            payload_deltas.append(delta)
        per_id_last_payload[fid] = payload

    feats = []

    # Per-tracked-ID: message count in window
    for tid in TRACKED_IDS:
        feats.append(id_counts.get(tid, 0))

    # Per-tracked-ID: inter-arrival mean and std (ms)
    iat = {tid: _inter_arrival_stats(sorted(per_id_times.get(tid, []))) for tid in TRACKED_IDS}
    for tid in TRACKED_IDS:
        feats.append(iat[tid][0])
    for tid in TRACKED_IDS:
        feats.append(iat[tid][1])

    # Global: unique ID count
    feats.append(len(id_counts))

    # Global: Shannon entropy of the ID distribution
    total = sum(id_counts.values()) or 1
    entropy = -sum((c / total) * math.log2(c / total) for c in id_counts.values())
    feats.append(entropy)

    # Global: frames per second across the window
    all_t = [f["t"] for f in frames]
    span_s = (max(all_t) - min(all_t)) / 1_000_000.0 if len(all_t) > 1 else 0.0
    feats.append(len(frames) / span_s if span_s > 0 else 0.0)

    # Global: mean payload byte-change magnitude
    feats.append(sum(payload_deltas) / len(payload_deltas) if payload_deltas else 0.0)

    return feats


def frames_to_windows(frames, window=WINDOW_SIZE, step=None):
    """Slide a window over an ordered frame list, yielding feature vectors."""
    step = step or window  # non-overlapping by default for training
    out = []
    for start in range(0, len(frames) - window + 1, step):
        out.append(window_features(frames[start:start + window]))
    return out
