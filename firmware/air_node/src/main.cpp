#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>

#define NO_OTA_PORT
#include <ArduinoOTA.h>

// ===== WiFi =====
const char* ssid = "SSID";
const char* password = "PASSWD";

// ===== Server =====
const char* serverName = "http://SERVER_Name:8001/mq135";

// ===== MQ135 =====
#define MQ135_PIN A0

unsigned long lastSend = 0;
unsigned long interval = 60000; // 1 минута

void setup() {
  Serial.begin(115200);
  delay(100);

  Serial.println("\nMQ135 Node starting...");

  pinMode(MQ135_PIN, INPUT);

  // WiFi connect
  WiFi.begin(ssid, password);

  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.println(WiFi.localIP());

  // OTA setup
  ArduinoOTA.setHostname("wemos-mq135.local");

  ArduinoOTA.onStart([]() {
    Serial.println("OTA Start");
  });

  ArduinoOTA.onEnd([]() {
    Serial.println("\nOTA End");
    ESP.restart();
  });

  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
  });

  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("Error[%u]: ", error);
    if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
    else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
    else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
    else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
    else if (error == OTA_END_ERROR) Serial.println("End Failed");
  });

  ArduinoOTA.begin();

  Serial.println("OTA ready");
}

void loop() {
  ArduinoOTA.handle();

  if (millis() - lastSend > interval) {
    lastSend = millis();

    int mqRaw = analogRead(MQ135_PIN);

    Serial.print("MQ135 raw: ");
    Serial.println(mqRaw);

    if (WiFi.status() == WL_CONNECTED) {

      WiFiClient client;
      HTTPClient http;

      String url = String(serverName) +
                   "?id=2" +
                   "&air=" + String(mqRaw) +
                   "&rssi=" + String(WiFi.RSSI());

      Serial.println("URL: " + url);

      http.begin(client, url);

      int httpCode = http.GET();

      Serial.print("HTTP code: ");
      Serial.println(httpCode);

      String payload = http.getString();
      Serial.println(payload);

      http.end();
    }
  }
}
