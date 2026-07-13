/*
 * Node: Camera ECU  (Arduino GIGA R1 #1)
 * Role: legitimate "known-good" ECU. Emits a periodic frame on CAN ID 0x101
 *       carrying a visual-cue flag + average brightness from the OV7670 camera.
 *
 * This node is intentionally left almost unchanged from the original working
 * sketch. In the IDS project it provides the *baseline* periodic traffic that
 * the anomaly detector learns as "normal". When the infotainment node spoofs
 * 0x101, a SECOND source of the same ID appears on the bus and the timing of
 * 0x101 is disrupted -- that is what the model is trained to catch.
 *
 * Wiring: MCP2515 on SPI1, CS = D10, 8 MHz crystal, bus @ 500 kbps.
 */

#include "camera.h"
#include "ov767x.h"
#include <SPI.h>
#include <mcp_can.h>

#define CAN_CS 10
MCP_CAN CAN(&SPI1, CAN_CS);

OV7670 ov767x;
Camera cam(ov767x);
FrameBuffer fb;

unsigned long lastSendMillis = 0;
const unsigned long SEND_INTERVAL_MS = 500;   // 0x101 nominal period == the "normal" timing

void setup() {
  Serial.begin(115200);
  while (!Serial) {}

  if (!cam.begin(CAMERA_R320x240, CAMERA_GRAYSCALE, 30)) {
    Serial.println("Camera init FAILED");
    while (1) {}
  }
  Serial.println("Camera init OK");

  SPI1.begin();
  if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) == CAN_OK) {
    Serial.println("CAN init OK");
  } else {
    Serial.println("CAN init FAILED");
    while (1) {}
  }
  CAN.setMode(MCP_NORMAL);
  Serial.println("Camera ECU ready");
}

void loop() {
  if (cam.grabFrame(fb, 3000) == 0) {
    uint8_t* buf = fb.getBuffer();
    int frameSize = cam.frameSize();
    long total = 0;
    for (int i = 0; i < frameSize; i++) total += buf[i];

    int avgBrightness = total / frameSize;
    bool brightCueDetected = avgBrightness > 128;

    if (millis() - lastSendMillis >= SEND_INTERVAL_MS) {
      uint8_t payload[2] = {
        (uint8_t)brightCueDetected,
        (uint8_t)min(avgBrightness, 255)
      };
      CAN.sendMsgBuf(0x101, 0, 2, payload);
      lastSendMillis = millis();
    }
  } else {
    Serial.println("Frame grab FAILED");
  }

  // CAN controller error recovery
  if (CAN.checkError() == CAN_CTRLERROR) {
    CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ);
    CAN.setMode(MCP_NORMAL);
    delay(500);
  }
}
