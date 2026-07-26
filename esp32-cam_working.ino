#include <Arduino.h>
#include <EEPROM.h>
#include <FS.h>
#include <SD_MMC.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include "esp_camera.h"

// ==========================================
//  1. CONFIGURATION & NETWORK SETTINGS
// ==========================================
#ifndef WIFI_SSID_VALUE
#define WIFI_SSID_VALUE "Kessie"
#endif
#ifndef WIFI_PASSWORD_VALUE
#define WIFI_PASSWORD_VALUE "Kessie1011"
#endif
#ifndef BACKEND_BASE_URL_VALUE
#define BACKEND_BASE_URL_VALUE "http://10.166.109.71:5000"
#endif
#ifndef API_KEY_VALUE
#define API_KEY_VALUE "e52dc64913f9bbca16f37e4a27af776dee4b797db06e53abe99a9f5bc308e480"
#endif

const char *WIFI_SSID = WIFI_SSID_VALUE;
const char *WIFI_PASSWORD = WIFI_PASSWORD_VALUE;
const char *BACKEND_BASE_URL = BACKEND_BASE_URL_VALUE;
const char *API_KEY = API_KEY_VALUE;

constexpr bool SAVE_TO_SD = true;
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 20000;
constexpr uint32_t HTTP_TIMEOUT_MS = 10000;
constexpr size_t EEPROM_SIZE = 8;

// Hardware pin definitions for AI-Thinker ESP32-CAM
#define TRIGGER_PIN 13
#define FLASH_LED_PIN 4

#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

// Tracking variables
uint32_t pictureNumber = 0;
bool sdAvailable = false;

// Function prototypes
bool connectWiFi();
bool initializeCamera();
void saveFrameToSd(camera_fb_t *frame);
bool sendCameraHeartbeat(const String &status);
bool uploadFrameToRecognition(camera_fb_t *frame);
void captureAndUpload();

// ==========================================
//  2. MAIN SETUP & LOOP
// ==========================================

void setup()
{
  Serial.begin(115200);
  delay(500);

  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);
  pinMode(TRIGGER_PIN, INPUT);

  EEPROM.begin(EEPROM_SIZE);
  EEPROM.get(0, pictureNumber);
  if (pictureNumber == 0xFFFFFFFF)
  {
    pictureNumber = 0;
  }

  if (!initializeCamera())
  {
    Serial.println("[System Error] Camera initialization failed.");
    return;
  }

  if (SAVE_TO_SD)
  {
    sdAvailable = SD_MMC.begin("/sdcard", true);
    Serial.println(sdAvailable ? "[SD Card] Mounted successfully." : "[SD Card] Mount failed / disabled.");
  }

  if (!connectWiFi())
  {
    Serial.println("[Wi-Fi] Camera will retry on the next trigger.");
  }

  Serial.println("\n--- ESP32-CAM Sentry Node Active ---");
  Serial.println("[Status] Waiting for trigger pulses on GPIO 13...");
}

void loop()
{
  if (digitalRead(TRIGGER_PIN) == HIGH)
  {
    delay(30);
    if (digitalRead(TRIGGER_PIN) == HIGH)
    {
      captureAndUpload();
      while (digitalRead(TRIGGER_PIN) == HIGH)
      {
        delay(10);
      }
    }
  }

  delay(10);
}

// ==========================================
//  3. NETWORK & FLASK API PAYLOAD LOGIC
// ==========================================

bool connectWiFi()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    return true;
  }

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.disconnect(true);
  delay(100);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[Wi-Fi] Connecting");

  uint32_t startedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startedAt < WIFI_CONNECT_TIMEOUT_MS)
  {
    delay(250);
    Serial.print('.');
  }

  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println("\n[Wi-Fi] Connection failed.");
    return false;
  }

  Serial.printf("\n[Wi-Fi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
  return true;
}

bool sendCameraHeartbeat(const String &status)
{
  if (!connectWiFi())
  {
    return false;
  }

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);

  String endpoint = String(BACKEND_BASE_URL) + "/api/telemetry";
  if (!http.begin(client, endpoint))
  {
    Serial.println("[Telemetry] Could not open endpoint.");
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  http.addHeader("Accept", "application/json");

  String payload = "{";
  payload += "\"device_name\":\"ESP32-CAM\",";
  payload += "\"status\":\"" + status + "\",";
  payload += "\"metric_name\":\"capture_status\",";
  payload += "\"metric_value\":1.0,";
  payload += "\"metric_unit\":\"binary\",";
  payload += "\"metadata\":{\"source\":\"esp32-cam\",\"trigger\":\"capture\"}";
  payload += "}";

  int statusCode = http.POST(payload);
  if (statusCode > 0)
  {
    String response = http.getString();
    Serial.printf("[Heartbeat] Response %d: %s\n", statusCode, response.c_str());
  }
  else
  {
    Serial.printf("[Heartbeat] Failed: %s\n", http.errorToString(statusCode).c_str());
  }

  http.end();
  return (statusCode >= 200 && statusCode < 300);
}

bool uploadFrameToRecognition(camera_fb_t *frame)
{
  if (frame == nullptr || frame->buf == nullptr || frame->len == 0)
  {
    Serial.println("[Upload] Frame buffer empty.");
    return false;
  }

  if (!connectWiFi())
  {
    return false;
  }

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);

  String endpoint = String(BACKEND_BASE_URL) + "/api/v1/facial-recognition/";
  if (!http.begin(client, endpoint))
  {
    Serial.println("[Upload] Could not open Flask endpoint.");
    return false;
  }

  String boundary = "----SentryVisionBoundaryTag";
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  http.addHeader("X-API-Key", API_KEY);
  http.addHeader("Accept", "application/json");

  String bodyPrefix = "";
  bodyPrefix += "--" + boundary + "\r\n";
  bodyPrefix += "Content-Disposition: form-data; name=\"trigger_source\"\r\n\r\nmotion\r\n";
  bodyPrefix += "--" + boundary + "\r\n";
  bodyPrefix += "Content-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\n";
  bodyPrefix += "Content-Type: image/jpeg\r\n\r\n";

  String bodySuffix = "\r\n--" + boundary + "--\r\n";

  size_t totalPayloadLen = bodyPrefix.length() + frame->len + bodySuffix.length();
  uint8_t *payloadBuffer = (uint8_t *)malloc(totalPayloadLen);
  if (payloadBuffer == nullptr)
  {
    Serial.println("[Upload] Out of memory creating HTTP buffer.");
    http.end();
    return false;
  }

  memcpy(payloadBuffer, bodyPrefix.c_str(), bodyPrefix.length());
  memcpy(payloadBuffer + bodyPrefix.length(), frame->buf, frame->len);
  memcpy(payloadBuffer + bodyPrefix.length() + frame->len, bodySuffix.c_str(), bodySuffix.length());

  Serial.printf("[Upload] Transmitting %u bytes to Flask...\n", static_cast<unsigned>(totalPayloadLen));

  int statusCode = http.POST(payloadBuffer, totalPayloadLen);
  free(payloadBuffer);

  if (statusCode > 0)
  {
    String response = http.getString();
    Serial.printf("[Upload] Response %d: %s\n", statusCode, response.c_str());
  }
  else
  {
    Serial.printf("[Upload] Failed: %s\n", http.errorToString(statusCode).c_str());
  }

  http.end();
  return (statusCode >= 200 && statusCode < 300);
}

// ==========================================
//  4. CAMERA HARDWARE & CAPTURE
// ==========================================

bool initializeCamera()
{
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound())
  {
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 10;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
  }
  else
  {
    config.frame_size = FRAMESIZE_CIF;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK)
  {
    Serial.printf("[Camera] Init failed: 0x%x\n", err);
    return false;
  }

  return true;
}

void captureAndUpload()
{
  Serial.println("\n--- Trigger Received: Frame capture starting ---");

  digitalWrite(FLASH_LED_PIN, HIGH);
  delay(100);

  camera_fb_t *staleFrame = esp_camera_fb_get();
  if (staleFrame != nullptr)
  {
    esp_camera_fb_return(staleFrame);
  }

  camera_fb_t *frame = esp_camera_fb_get();
  digitalWrite(FLASH_LED_PIN, LOW);

  if (frame == nullptr)
  {
    Serial.println("[Camera] Failed to grab frame.");
    return;
  }

  Serial.printf("[Camera] Captured %u byte frame\n", static_cast<unsigned>(frame->len));

  saveFrameToSd(frame);
  sendCameraHeartbeat("Online");
  uploadFrameToRecognition(frame);

  esp_camera_fb_return(frame);
}

void saveFrameToSd(camera_fb_t *frame)
{
  if (!SAVE_TO_SD || !sdAvailable || frame == nullptr)
  {
    return;
  }

  pictureNumber++;
  EEPROM.put(0, pictureNumber);
  EEPROM.commit();

  String path = "/capture_" + String(pictureNumber) + ".jpg";
  File file = SD_MMC.open(path.c_str(), FILE_WRITE);
  if (!file)
  {
    Serial.printf("[SD Card] Failed to open %s\n", path.c_str());
    return;
  }

  file.write(frame->buf, frame->len);
  file.close();
  Serial.printf("[SD Card] Saved %s (%u bytes)\n", path.c_str(), static_cast<unsigned>(frame->len));
}