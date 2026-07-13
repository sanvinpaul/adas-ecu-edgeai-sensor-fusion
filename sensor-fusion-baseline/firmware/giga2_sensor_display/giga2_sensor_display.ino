/*
 * Stage 1 -- ADAS baseline
 * Node: Sensor + Display  (Arduino GIGA R1 #2)
 * Role: receives the camera ECU's brightness/visual-cue frame (0x101), reads a
 *       local ultrasonic distance sensor, broadcasts proximity/distance (0x102),
 *       and shows the combined vehicle state on an OLED.
 *
 * This is the original working node -- no WiFi, no AI. It establishes the
 * multi-node CAN network that later stages build on.
 *
 * Wiring: MCP2515 on default SPI (ICSP), CS = D10, 8 MHz, 500 kbps.
 *         OLED SSD1306 on I2C. Ultrasonic TRIG = D2, ECHO = D3.
 */

#include <SPI.h>
#include <mcp_can.h>
#include <U8g2lib.h>
#include <Wire.h>

#define CAN_CS 10
MCP_CAN CAN(CAN_CS);

U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE);

#define TRIG_PIN 2
#define ECHO_PIN 3

// Received from camera ECU (0x101)
bool visualCueDetected = false;
int  avgBrightness = 0;
unsigned long lastReceiveMillis = 0;

// Local ultrasonic
long ultrasonicDistance = 0;
unsigned long lastUltraMillis = 0;
const unsigned long ULTRA_INTERVAL_MS = 100;

long readUltrasonic() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);   // 30 ms timeout (~5 m)
  if (duration == 0) return -1;
  return duration * 0.034 / 2;
}

void updateDisplay() {
  display.clearBuffer();
  display.setFont(u8g2_font_6x10_tf);

  display.drawStr(0, 10, "ADAS Monitor / Node 2");
  display.drawLine(0, 13, 128, 13);

  bool dataFresh = (millis() - lastReceiveMillis) < 2000;
  display.drawStr(0, 24, "Cam ECU:");
  display.drawStr(55, 24, dataFresh ? "Connected" : "No signal");

  display.drawStr(0, 36, "Brightness:");
  char b[8]; snprintf(b, sizeof(b), "%d", avgBrightness);
  display.drawStr(75, 36, b);

  display.drawStr(0, 48, "Visual cue:");
  display.drawStr(75, 48, visualCueDetected ? "YES" : "NO");

  display.drawStr(0, 60, "Distance:");
  char d[12]; snprintf(d, sizeof(d), "%ld cm", ultrasonicDistance);
  display.drawStr(75, 60, d);

  display.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {}

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  display.begin();
  display.clearBuffer();
  display.setFont(u8g2_font_6x10_tf);
  display.drawStr(0, 30, "Waiting for CAN...");
  display.sendBuffer();

  if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) != CAN_OK) {
    Serial.println("CAN init FAILED"); while (1) {}
  }
  CAN.setMode(MCP_NORMAL);
  Serial.println("Node 2 ready -- listening and sensing");
}

void loop() {
  // 1) Receive camera ECU data (0x101)
  if (CAN.checkReceive() == CAN_MSGAVAIL) {
    unsigned long id; uint8_t len = 0; uint8_t buf[8];
    CAN.readMsgBuf(&id, &len, buf);
    if (id == 0x101 && len >= 2) {
      visualCueDetected = buf[0];
      avgBrightness     = buf[1];
      lastReceiveMillis = millis();
    }
  }

  // 2) Ultrasonic -> broadcast 0x102
  if (millis() - lastUltraMillis >= ULTRA_INTERVAL_MS) {
    long d = readUltrasonic();
    if (d >= 0) {
      ultrasonicDistance = d;
      int di = (int)d;
      uint8_t payload[3] = {
        (uint8_t)(d > 0 && d < 30),   // proximity flag
        (uint8_t)(di >> 8),
        (uint8_t)(di & 0xFF)
      };
      CAN.sendMsgBuf(0x102, 0, 3, payload);
    }
    lastUltraMillis = millis();
  }

  // 3) OLED refresh
  static unsigned long lastDisp = 0;
  if (millis() - lastDisp >= 200) { updateDisplay(); lastDisp = millis(); }

  // 4) CAN recovery
  if (CAN.checkError() == CAN_CTRLERROR) {
    CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ);
    CAN.setMode(MCP_NORMAL);
    delay(500);
  }
}
