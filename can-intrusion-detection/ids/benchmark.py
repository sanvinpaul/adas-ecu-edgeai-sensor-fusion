"""
benchmark.py -- measure inference latency and model footprint, for the
portfolio "Results" line. Run this on the actual target (the Uno Q, inside
the Brick's container, or at minimum on the same machine/environment that
will run inference) for numbers that are honestly reportable as "on target."

Usage:
    python benchmark.py
"""

import os
import time

import numpy as np
from ids_core import IDSScorer
from features import WINDOW_SIZE

MODEL_DIR = "."  # adjust if model.keras/scaler.joblib/threshold.json live elsewhere


def footprint_kb():
    total_bytes = 0
    for fname in ["model.keras", "scaler.joblib", "threshold.json"]:
        path = os.path.join(MODEL_DIR, fname)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  {fname}: {size / 1024:.1f} KB")
            total_bytes += size
        else:
            print(f"  {fname}: NOT FOUND at {path}")
    return total_bytes / 1024


def latency_ms(scorer, n_runs=100):
    frames = []
    t = 1_000_000
    for i in range(WINDOW_SIZE):
        t += 250_000
        if i % 2 == 0:
            frames.append({"t": t, "id": 0x101, "dlc": 2, "d": [0, 120]})
        else:
            frames.append({"t": t, "id": 0x102, "dlc": 3, "d": [0, 0, 25]})

    scorer.score_window(frames)  # warm-up run

    times = []
    for _ in range(n_runs):
        start = time.perf_counter()
        scorer.score_window(frames)
        times.append((time.perf_counter() - start) * 1000)

    return times


def main():
    print("=== Model footprint ===")
    total_kb = footprint_kb()
    print(f"  TOTAL: {total_kb:.1f} KB")

    print("\n=== Loading model ===")
    load_start = time.perf_counter()
    scorer = IDSScorer(
        model_path=os.path.join(MODEL_DIR, "model.keras"),
        scaler_path=os.path.join(MODEL_DIR, "scaler.joblib"),
        threshold_path=os.path.join(MODEL_DIR, "threshold.json"),
    )
    load_time = (time.perf_counter() - load_start) * 1000
    print(f"  Model load time: {load_time:.1f} ms (one-time cost, not per-inference)")

    print("\n=== Inference latency (100 runs) ===")
    times = latency_ms(scorer, n_runs=100)
    times_arr = np.array(times)
    print(f"  Mean:   {times_arr.mean():.3f} ms")
    print(f"  Median: {np.median(times_arr):.3f} ms")
    print(f"  p95:    {np.percentile(times_arr, 95):.3f} ms")
    print(f"  Min:    {times_arr.min():.3f} ms")
    print(f"  Max:    {times_arr.max():.3f} ms")

    print("\n=== Summary for portfolio ===")
    print(f"  Inference latency: {np.median(times_arr):.2f} ms (median, on-device)")
    print(f"  Model footprint:   {total_kb:.1f} KB")


if __name__ == "__main__":
    main()
