/*
 * Stage 1 -- ADAS baseline
 * Node: Aggregator  (Arduino UNO Q -- MCU side)
 * Role: passively listens to every CAN frame and prints a consolidated vehicle
 *       state as JSON over Serial every 500 ms. Acts as the diagnostic/telemetry
 *       tap for the bus.
 *
 * Wiring: MCP2515 on default SPI, CS = D10, 8 MHz, 500 kbps.
 */

#include <SPI.h>
#include <mcp_can.h>

#define CAN_CS 10
MCP_CAN CAN(CAN_CS);

bool visualCueDetected = false;
int  avgBrightness = 0;
int  ultrasonicDistCm = -1;
bool proximityFlag = false;

unsigned long lastBoard1Millis = 0;
unsigned long lastBoard2Millis = 0;
unsigned long lastPrintMillis = 0;
const unsigned long PRINT_INTERVAL_MS = 500;

void setup() {
  Serial.begin(115200);
  while (!Serial) {}

  if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) == CAN_OK) {
    Serial.println("{\"status\":\"CAN init OK\"}");
  } else {
    Serial.println("{\"status\":\"CAN init FAILED\"}");
    while (1) {}
  }
  CAN.setMode(MCP_NORMAL);
}

void loop() {
  while (CAN.checkReceive() == CAN_MSGAVAIL) {
    unsigned long id; uint8_t len = 0; uint8_t buf[8];
    CAN.readMsgBuf(&id, &len, buf);

    if (id == 0x101 && len >= 2) {
      visualCueDetected = buf[0];
      avgBrightness     = buf[1];
      lastBoard1Millis  = millis();
    }
    if (id == 0x102 && len >= 3) {
      proximityFlag    = buf[0];
      ultrasonicDistCm = (buf[1] << 8) | buf[2];
      lastBoard2Millis = millis();
    }
  }

  if (millis() - lastPrintMillis >= PRINT_INTERVAL_MS) {
    bool b1 = (millis() - lastBoard1Millis) < 2000;
    bool b2 = (millis() - lastBoard2Millis) < 2000;

    Serial.print("{");
    Serial.print("\"cam_ecu\":");   Serial.print(b1 ? "true" : "false"); Serial.print(",");
    Serial.print("\"sensor_node\":"); Serial.print(b2 ? "true" : "false"); Serial.print(",");
    Serial.print("\"visual_cue\":"); Serial.print(visualCueDetected ? "true" : "false"); Serial.print(",");
    Serial.print("\"brightness\":"); Serial.print(avgBrightness); Serial.print(",");
    Serial.print("\"distance_cm\":"); Serial.print(ultrasonicDistCm); Serial.print(",");
    Serial.print("\"proximity\":"); Serial.print(proximityFlag ? "true" : "false");
    Serial.println("}");

    lastPrintMillis = millis();
  }

  if (CAN.checkError() == CAN_CTRLERROR) {
    Serial.println("{\"status\":\"CAN error - reinitializing\"}");
    CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ);
    CAN.setMode(MCP_NORMAL);
    delay(500);
  }
}
