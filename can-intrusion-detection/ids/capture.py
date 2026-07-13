"""
capture.py -- record raw CAN frames to CSV for training/evaluation.

Reads the per-frame JSON stream printed by the Uno Q forwarder sketch and writes
one CSV row per frame. Run once for normal traffic, then once per attack while
you trigger injections from the infotainment web page.

Usage:
    python capture.py --port /dev/ttyACM0 --label normal   --out ../data/normal.csv
    python capture.py --port /dev/ttyACM0 --label spoof    --out ../data/attack_spoof.csv

On the Uno Q the MCU is reachable as a serial device on the Linux side (check
`ls /dev/tty*`). On a laptop it is the Uno Q's USB serial port.

Press Ctrl-C to stop.
"""

import argparse
import csv
import json
import sys
import serial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--label", default="normal", help="label written to every row")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=1)
    print(f"Logging '{args.label}' -> {args.out}  (Ctrl-C to stop)")

    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t", "id", "dlc"] + [f"d{i}" for i in range(8)] + ["label"])
        n = 0
        try:
            while True:
                line = ser.readline().decode(errors="ignore").strip()
                if not line.startswith("{") or '"id"' not in line:
                    continue
                try:
                    f = json.loads(line)
                except json.JSONDecodeError:
                    continue
                data = f.get("d", [])
                data = (data + [0] * 8)[:8]
                w.writerow([f["t"], f["id"], f["dlc"]] + data + [args.label])
                n += 1
                if n % 200 == 0:
                    print(f"  {n} frames", end="\r")
        except KeyboardInterrupt:
            print(f"\nStopped. Wrote {n} frames.")


if __name__ == "__main__":
    sys.exit(main())
