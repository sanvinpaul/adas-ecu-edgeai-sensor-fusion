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

#define CAN_CS 10
MCP_CAN CAN(CAN_CS);

String cmd;

void broadcastAlert(uint8_t type, uint8_t score) {
  uint8_t p[3] = { 1, type, score };
  CAN.sendMsgBuf(0x555, 0, 3, p);
}

void handleSerialCommand() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      // Expect: ALERT,<type>,<score>
      if (cmd.startsWith("ALERT")) {
        int c1 = cmd.indexOf(',');
        int c2 = cmd.indexOf(',', c1 + 1);
        if (c1 > 0 && c2 > c1) {
          uint8_t type  = cmd.substring(c1 + 1, c2).toInt();
          uint8_t score = cmd.substring(c2 + 1).toInt();
          broadcastAlert(type, score);
        }
      }
      cmd = "";
    } else if (c != '\r') {
      cmd += c;
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
