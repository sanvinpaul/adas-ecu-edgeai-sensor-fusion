/*
 * Node: Infotainment head unit  (Arduino GIGA R1 #2)  --  ATTACK SURFACE + HMI
 * Roles:
 *   1. Legitimate ECU: reads ultrasonic distance, broadcasts 0x102, drives OLED.
 *   2. WiFi Access Point + web dashboard (the "infotainment" system).
 *   3. Compromised-head-unit simulation: web endpoints inject malicious CAN
 *      frames onto the bus (spoof / flood / replay / fuzz).
 *   4. Alert display: listens for the IDS alert frame (0x555) from the Uno Q and
 *      shows a warning banner on the OLED + the web page.
 *
 * NOTE: the Giga uses WiFi.beginAP() (mbed core) -- NOT WiFi.softAP() (ESP-only).
 *
 * Wiring: MCP2515 on default SPI (ICSP), CS = D10, 8 MHz, 500 kbps.
 *         OLED SSD1306 on I2C. Ultrasonic TRIG=D2, ECHO=D3.
 */

#include <SPI.h>
#include <mcp_can.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <WiFi.h>

// ---------- CAN ----------
#define CAN_CS 10
MCP_CAN CAN(CAN_CS);

// ---------- OLED ----------
U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE);

// ---------- Ultrasonic ----------
#define TRIG_PIN 2
#define ECHO_PIN 3
long ultrasonicDistance = 0;
unsigned long lastUltraMillis = 0;
const unsigned long ULTRA_INTERVAL_MS = 500;

// ---------- WiFi AP ----------
char ap_ssid[] = "CarInfotainment";
char ap_pass[] = "drive1234";       // must be >= 8 chars
WiFiServer server(80);

// ---------- Alert state (set when 0x555 received) ----------
bool alertActive = false;
uint8_t alertType = 0;              // 0=none 1=spoof 2=flood 3=replay 4=fuzz 5=unknown
uint8_t alertScore = 0;
unsigned long alertUntil = 0;       // auto-clear timestamp

// ---------- Replay buffer (last legit 0x101 seen) ----------
uint8_t replayBuf[8];
uint8_t replayLen = 0;
bool replayReady = false;

const char* attackName(uint8_t t) {
  switch (t) {
    case 1: return "SPOOF";
    case 2: return "FLOOD";
    case 3: return "REPLAY";
    case 4: return "FUZZ";
    case 5: return "UNKNOWN";
    default: return "-";
  }
}

long readUltrasonic() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return -1;
  return duration * 0.034 / 2;
}

// ---------- Injection attacks (simulate compromised head unit) ----------
void injectSpoof() {
  // Impersonate the camera ECU: a second 0x101 source at max brightness.
  uint8_t p[2] = {1, 255};
  CAN.sendMsgBuf(0x101, 0, 2, p);
}
void injectFlood() {
  // Bus DoS: hammer the highest-priority ID.
  uint8_t z[1] = {0};
  for (int i = 0; i < 200; i++) CAN.sendMsgBuf(0x000, 0, 1, z);
}
void injectReplay() {
  if (replayReady) CAN.sendMsgBuf(0x101, 0, replayLen, replayBuf);
}
void injectFuzz() {
  uint32_t id = random(0, 0x7FF);
  uint8_t len = random(1, 9);
  uint8_t d[8];
  for (int i = 0; i < len; i++) d[i] = random(0, 256);
  CAN.sendMsgBuf(id, 0, len, d);
}

// ---------- Web dashboard ----------
void sendDashboard(WiFiClient& client) {
  // Build the entire HTML body in one buffer, then send it in a single write.
  // Many separate client.print()/println() calls each incur their own
  // network-write latency; while a client is connected and auto-refreshing,
  // that blocking time inside handleClient() delays the next scheduled 0x102
  // CAN send, disrupting its timing enough to be flagged as anomalous by the
  // IDS. Consolidating output -- and lengthening the refresh interval below
  // -- both reduce how much this feature disrupts CAN timing.
  String body;
  body.reserve(900);
  body += "<!DOCTYPE html><html><head><meta charset='utf-8'>";
  body += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  body += "<meta http-equiv='refresh' content='5'>";   // was 2s -- fewer serve cycles per minute
  body += "<title>Car Infotainment</title></head><body style='font-family:sans-serif;text-align:center'>";
  body += "<h2>Vehicle Infotainment</h2>";

  if (alertActive) {
    body += "<div style='background:#c0392b;color:#fff;padding:16px;font-size:20px;border-radius:8px'>";
    body += "&#9888; INTRUSION DETECTED &mdash; ";
    body += attackName(alertType);
    body += " (score ";
    body += alertScore;
    body += ")</div>";
  } else {
    body += "<div style='background:#27ae60;color:#fff;padding:16px;border-radius:8px'>System nominal</div>";
  }

  body += "<p>Distance: ";
  body += ultrasonicDistance;
  body += " cm</p>";

  body += "<hr><h3>Diagnostics (inject test frames)</h3>";
  body += "<p><a href='/inject/spoof'>Spoof 0x101</a> | ";
  body += "<a href='/inject/flood'>Flood 0x000</a> | ";
  body += "<a href='/inject/replay'>Replay</a> | ";
  body += "<a href='/inject/fuzz'>Fuzz</a></p>";
  body += "</body></html>";

  client.print("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n");
  client.print(body);
}

void handleClient() {
  WiFiClient client = server.available();
  if (!client) return;

  String reqLine = client.readStringUntil('\r');
  while (client.available()) client.read();   // drain the rest of the request

  int s = reqLine.indexOf(' ');
  int e = reqLine.indexOf(' ', s + 1);
  String path = (s >= 0 && e > s) ? reqLine.substring(s + 1, e) : "/";

  bool isInject = (path == "/inject/spoof" || path == "/inject/flood" ||
                    path == "/inject/replay" || path == "/inject/fuzz");

  if (isInject) {
    if      (path == "/inject/spoof")  injectSpoof();
    else if (path == "/inject/flood")  injectFlood();
    else if (path == "/inject/replay") injectReplay();
    else if (path == "/inject/fuzz")   injectFuzz();

    // Post/Redirect/Get: send the browser back to "/" instead of serving
    // content directly at the /inject/* URL. Otherwise the browser's address
    // bar stays on e.g. /inject/spoof, and a later page refresh silently
    // re-sends that exact request -- re-triggering the same injection with
    // no click at all.
    client.print("HTTP/1.1 303 See Other\r\nLocation: /\r\nConnection: close\r\n\r\n");
  } else {
    sendDashboard(client);
  }

  delay(2);
  client.stop();
}

void updateDisplay() {
  display.clearBuffer();
  display.setFont(u8g2_font_6x10_tf);

  if (alertActive) {
    display.drawBox(0, 0, 128, 14);
    display.setDrawColor(0);
    display.drawStr(4, 11, "! INTRUSION !");
    display.setDrawColor(1);
    display.drawStr(0, 30, "Type:");
    display.drawStr(40, 30, attackName(alertType));
    display.drawStr(0, 44, "Score:");
    char sc[6]; snprintf(sc, sizeof(sc), "%d", alertScore);
    display.drawStr(45, 44, sc);
  } else {
    display.drawStr(0, 10, "Infotainment / Node 2");
    display.drawLine(0, 13, 128, 13);
    display.drawStr(0, 28, "Status: OK");
    display.drawStr(0, 44, "Distance:");
    char d[12]; snprintf(d, sizeof(d), "%ld cm", ultrasonicDistance);
    display.drawStr(65, 44, d);
    display.drawStr(0, 60, "AP: CarInfotainment");
  }
  display.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  randomSeed(analogRead(A0));

  display.begin();
  display.clearBuffer();
  display.setFont(u8g2_font_6x10_tf);
  display.drawStr(0, 30, "Booting...");
  display.sendBuffer();

  // SPI1.begin();
  if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) != CAN_OK) {
    Serial.println("CAN init FAILED"); while (1) {}
  }
  CAN.setMode(MCP_NORMAL);
  Serial.println("CAN init OK");

  if (WiFi.beginAP(ap_ssid, ap_pass) != WL_AP_LISTENING) {
    Serial.println("AP failed"); while (1) {}
  }
  server.begin();
  Serial.print("AP IP: "); Serial.println(WiFi.localIP());
  Serial.println("Infotainment ready");
}

void loop() {
  // 1) Receive CAN: capture 0x101 for replay, react to 0x555 alert.
  while (CAN.checkReceive() == CAN_MSGAVAIL) {
    unsigned long id; uint8_t len = 0; uint8_t buf[8];
    CAN.readMsgBuf(&id, &len, buf);

    if (id == 0x101 && len >= 1) {
      replayLen = len; replayReady = true;
      for (int i = 0; i < len; i++) replayBuf[i] = buf[i];
    }
    if (id == 0x555 && len >= 3) {
      alertActive = (buf[0] == 1);
      alertType   = buf[1];
      alertScore  = buf[2];
      alertUntil  = millis() + 5000;   // hold banner 5 s after last alert
    }
  }
  if (alertActive && millis() > alertUntil) alertActive = false;

  // 2) Ultrasonic -> 0x102 (legit periodic traffic)
  if (millis() - lastUltraMillis >= ULTRA_INTERVAL_MS) {
    long d = readUltrasonic();
    if (d >= 0) {
      ultrasonicDistance = d;
      int di = (int)d;
      uint8_t p[3] = { (uint8_t)(d > 0 && d < 30), (uint8_t)(di >> 8), (uint8_t)(di & 0xFF) };
      CAN.sendMsgBuf(0x102, 0, 3, p);
    }
    lastUltraMillis = millis();
  }

  // 3) Serve web / handle injections
  handleClient();

  // 4) OLED refresh
  static unsigned long lastDisp = 0;
  if (millis() - lastDisp >= 200) { updateDisplay(); lastDisp = millis(); }

  // 5) CAN recovery
  if (CAN.checkError() == CAN_CTRLERROR) {
    CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ);
    CAN.setMode(MCP_NORMAL);
  }
}
