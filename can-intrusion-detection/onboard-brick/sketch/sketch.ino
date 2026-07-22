/*
 * Node: IDS front-end MCU  (Arduino UNO Q -- STM32 side, running inside the
 * ADAS_ECU_Prototype_CAN_IDs App Lab app)
 *
 * Replaces the standalone unoq_can_forwarder.ino sketch. Instead of printing
 * JSON lines over Serial for a laptop-tethered Python script to parse, this
 * pushes each CAN frame directly to the Python Brick via Bridge RPC, and
 * receives alert broadcasts back the same way -- no string parsing needed on
 * either side.
 *
 * Wiring: MCP2515 on default SPI, CS = D10, 8 MHz, 500 kbps (unchanged).
 */

#include "Arduino_RouterBridge.h"
#include <SPI.h>
#include <mcp_can.h>

#define CAN_CS 10
MCP_CAN CAN(CAN_CS);

void broadcastAlert(uint8_t type, uint8_t score) {
  uint8_t p[3] = { 1, type, score };
  CAN.sendMsgBuf(0x555, 0, 3, p);
}

void setup() {
  Bridge.begin();
  Bridge.provide("broadcast_alert", broadcastAlert);

  if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) != CAN_OK) {
    Monitor.println("CAN init FAILED");
    while (1) {}
  }
  CAN.setMode(MCP_NORMAL);
  Monitor.println("CAN init OK, forwarder ready");
}

void loop() {
  while (CAN.checkReceive() == CAN_MSGAVAIL) {
    unsigned long id; uint8_t len = 0; uint8_t buf[8];
    CAN.readMsgBuf(&id, &len, buf);

    Bridge.call("on_can_frame", (uint32_t)id, len,
                buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7]);
  }

  if (CAN.checkError() == CAN_CTRLERROR) {
    CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ);
    CAN.setMode(MCP_NORMAL);
  }
}
