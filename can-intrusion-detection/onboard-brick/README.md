# onboard-brick

On-device port of the CAN IDS: a Custom Brick running inside the
`ADAS_ECU_Prototype_CAN_IDs` App Lab app, replacing the laptop-tethered
`detect.py` + serial-string protocol with Bridge RPC calls directly between
the sketch and the Python Brick.

## Known open items (verify empirically on first run)

1. **`Bridge.call()` multi-argument support**: the only officially confirmed
   example passes a single argument
   (`Bridge.call("set_led_state", led_state)`). `sketch.ino` here calls
   `Bridge.call("on_can_frame", id, len, b0..b7)` with 10 positional
   arguments as a best-effort extension -- if this doesn't work as written,
   pack the frame into a single array/struct argument instead.
2. **Docker build behavior**: this is the first real test of
   `brick_compose.yaml` + `Dockerfile` -- watch the App Lab Console during
   first Run for build errors.

## What's verified (not just assumed)

- The Brick's callback logic (window management, `0x555` exclusion, alert
  triggering via `Bridge.call("broadcast_alert", ...)`) was tested with a
  mocked `arduino.app_utils` module -- confirmed mechanically correct
  independent of real hardware.
- `classify()` and `IDSScorer` are unchanged from the already-hardware-
  validated `ids_core.py` -- detection/classification logic itself carries
  over with zero changes.
- The Bridge RPC pattern itself (`Bridge.provide`/`Bridge.call`,
  `Arduino_RouterBridge.h`) is taken directly from Arduino's own official
  "What is an App?" documentation, not guessed.
