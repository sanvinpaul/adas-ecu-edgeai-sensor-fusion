# bricks/can_ids_scorer/__init__.py
"""
Custom Brick: on-device CAN intrusion detection, using Bridge RPC.

Registers on_can_frame() to be called by the sketch (Arduino_RouterBridge)
every time a CAN frame arrives, maintains a rolling window, and scores it
using the same IDSScorer/ids_core.py logic already validated on the
laptop-tethered detect.py. On an anomaly, calls broadcast_alert() (registered
by the sketch) via Bridge.call(), exactly replacing the old
"ALERT,<type>,<score>\n" serial string protocol with a real RPC call.
"""

from arduino.app_utils import Bridge, brick, Logger
import collections
import time

from features import WINDOW_SIZE
from ids_core import IDSScorer, ATTACK_NAMES

logger = Logger("CANIDSBrick")


@brick
class CANIDSScorer:
    def __init__(self, cooldown=3.0):
        self.cooldown = cooldown
        self.window = collections.deque(maxlen=WINDOW_SIZE)
        self.last_alert = 0.0
        self.n = 0
        self.scorer = None

    def start(self):
        logger.info("Loading IDS model...")
        self.scorer = IDSScorer()
        logger.info(f"Threshold = {self.scorer.threshold:.5f}")
        Bridge.provide("on_can_frame", self._on_can_frame)

    def stop(self):
        pass

    def _on_can_frame(self, can_id, dlc, b0, b1, b2, b3, b4, b5, b6, b7):
        if can_id == 0x555:
            return

        data = [b0, b1, b2, b3, b4, b5, b6, b7][:dlc]
        frame = {"t": time.time() * 1_000_000, "id": can_id, "dlc": dlc, "d": data}
        self.window.append(frame)

        if len(self.window) < WINDOW_SIZE:
            return

        self.n += 1
        if self.n % 10:
            return

        frames = list(self.window)
        is_anomaly, err, atype, feat = self.scorer.score_window(frames)

        if is_anomaly and (time.time() - self.last_alert) > self.cooldown:
            score = min(255, int(err / self.scorer.threshold * 50))
            Bridge.call("broadcast_alert", atype, score)
            logger.info(f"ANOMALY err={err:.4f} type={atype} ({ATTACK_NAMES[atype]}) score={score}")
            self.last_alert = time.time()

    def loop(self):
        pass
