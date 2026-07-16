/*
 * Node: IDS front-end MCU  (Arduino UNO Q -- STM32U585 side)
 * Role: bridge between the CAN bus and the Linux/Python IDS.
 *   - Reads EVERY CAN frame and prints it as one JSON line per frame over Serial.
 *     The Python detector on the Qualcomm/Linux side consumes this stream.
 *   - Listens on Serial for "ALERT,<type>,<score>" from Python and broadcasts the
 *     IDS alert frame 0x555 so the infotainment head unit can warn the driver.
 *
 * Frame line format (one per received CAN frame):
 *   {"t":<micros>,"id":<dec>,"dlc":<n>,"d":[b0,...]}
 *
 * Wiring: MCP2515 on default SPI, CS = D10, 8 MHz, 500 kbps.
 *
 * In Arduino App Lab this sketch runs on the MCU; the Python app talks to it over
 * the MPU<->MCU bridge (exposed as a serial device on the Linux side).
 */

#include <SPI.h>
#include <mcp_can.h>
#include <string.h>
#include <stdlib.h>

#define CAN_CS 10
MCP_CAN CAN(CAN_CS);

#define CMD_BUF_SIZE 32
char cmdBuf[CMD_BUF_SIZE];
uint8_t cmdLen = 0;

void broadcastAlert(uint8_t type, uint8_t score) {
  uint8_t p[3] = { 1, type, score };
  CAN.sendMsgBuf(0x555, 0, 3, p);
}

void handleSerialCommand() {
  // Fixed-size buffer, no String/heap allocation. detect.py's --dry-run
  // testing proved that a String-based version of this (cmd += c on every
  // character) could disrupt CAN frame forwarding timing -- Arduino String
  // concatenation reallocates on the heap, and after hours of continuous
  // uptime with repeated alert processing, fragmentation could cause
  // unpredictable stalls right here, delaying the CAN receive loop above.
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      cmdBuf[cmdLen] = '\0';
      // Expect: ALERT,<type>,<score>
      if (strncmp(cmdBuf, "ALERT", 5) == 0) {
        char* p1 = strchr(cmdBuf, ',');
        char* p2 = p1 ? strchr(p1 + 1, ',') : nullptr;
        if (p1 && p2) {
          uint8_t type  = (uint8_t)atoi(p1 + 1);
          uint8_t score = (uint8_t)atoi(p2 + 1);
          broadcastAlert(type, score);
        }
      }
      cmdLen = 0;
    } else if (c != '\r' && cmdLen < CMD_BUF_SIZE - 1) {
      cmdBuf[cmdLen++] = c;
    }
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) != CAN_OK) {
    Serial.println("{\"status\":\"CAN init FAILED\"}");
    while (1) {}
  }
  CAN.setMode(MCP_NORMAL);
  Serial.println("{\"status\":\"forwarder ready\"}");
}

void loop() {
  while (CAN.checkReceive() == CAN_MSGAVAIL) {
    unsigned long id; uint8_t len = 0; uint8_t buf[8];
    CAN.readMsgBuf(&id, &len, buf);

    Serial.print("{\"t\":");   Serial.print(micros());
    Serial.print(",\"id\":");  Serial.print(id);
    Serial.print(",\"dlc\":"); Serial.print(len);
    Serial.print(",\"d\":[");
    for (int i = 0; i < len; i++) {
      Serial.print(buf[i]);
      if (i < len - 1) Serial.print(",");
    }
    Serial.println("]}");
  }

  handleSerialCommand();

  if (CAN.checkError() == CAN_CTRLERROR) {
    CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ);
    CAN.setMode(MCP_NORMAL);
  }
}
