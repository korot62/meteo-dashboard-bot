#include <Arduino.h>


#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include "DHT.h"
#define NO_OTA_PORT
#include "ArduinoOTA.h"
#define DHTPIN D4
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);

const char* ssid = "SSID";
const char* password = "PASSWD";

// IP компьютера с Python логгером
const char* serverName = "http://SERVER_ADD:8001/sensor";

unsigned long lastSend = 0;
unsigned long interval = 60000; // 1 минута

void setup() {
  Serial.begin(115200);

  dht.begin();

  WiFi.begin(ssid, password);
  
  
  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected");
  Serial.println(WiFi.localIP());

  ArduinoOTA.setHostname("wemos-weather.local");
  ArduinoOTA.onStart([]() {
    Serial.println("OTA Start");
  } );
  ArduinoOTA.onEnd(
    []() {
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
    Serial.println("OTA ready_1");
}

void loop() {
  ArduinoOTA.handle();
  if (millis() - lastSend > interval) {

    lastSend = millis();

    float temp = dht.readTemperature();
    float hum = dht.readHumidity();

    if (isnan(temp) || isnan(hum)) {
      Serial.println("DHT error");
      return;
    }

    Serial.println("Sending data");

    if (WiFi.status() == WL_CONNECTED) {

      WiFiClient client;
      HTTPClient http;

      String url = String(serverName) +
                   "?id=2" +
                   "&temp=" + String(temp) +
                   "&hum=" + String(hum) +
                   "&rssi=" + String(WiFi.RSSI());

      Serial.print("URL: " + url);

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
