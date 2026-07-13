/*
 * Phase 1 test sketch -- WiFi Access Point on GIGA R1 #2
 *
 * Purpose: prove the AP works in isolation before merging it into the full
 * infotainment sketch (giga2_infotainment.ino). Once you can connect a laptop
 * to "CarInfotainment" and load the test page below, this phase is done.
 *
 * IMPORTANT: attach the u.FL antenna to J14 before powering the board --
 * without it the AP will start but range will be extremely short.
 *
 * Board: Arduino GIGA R1 WiFi
 */

#include <WiFi.h>

char ssid[] = "CarInfotainment";
char pass[] = "drive1234";     // WPA2 passwords must be 8+ characters
WiFiServer server(80);

void setup() {
  Serial.begin(115200);
  // Don't hang forever waiting for Serial -- lets the board still boot the AP
  // when powered without a USB host attached.
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 3000) {}

  Serial.println("Starting AP...");
  if (WiFi.beginAP(ssid, pass) != WL_AP_LISTENING) {
    Serial.println("AP failed to start");
    while (1) {}
  }

  server.begin();
  Serial.println("AP started");
  Serial.print("SSID: "); Serial.println(ssid);
  Serial.print("AP IP: "); Serial.println(WiFi.localIP());
  Serial.println("Connect a laptop/phone to the SSID above, then browse to the IP.");
}

void loop() {
  WiFiClient client = server.available();
  if (!client) return;

  // Drain the HTTP request (we don't need to parse it for this test)
  while (client.connected() && client.available()) {
    client.read();
  }

  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: text/html");
  client.println("Connection: close");
  client.println();
  client.println("<!DOCTYPE html><html><body style='font-family:sans-serif;text-align:center'>");
  client.println("<h2>GIGA R1 Access Point</h2>");
  client.println("<p>If you can see this page, the WiFi AP is working.</p>");
  client.print("<p>Uptime: "); client.print(millis() / 1000); client.println(" s</p>");
  client.println("</body></html>");

  delay(2);
  client.stop();
}
