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
#define WIFI_SSID_VALUE "SnowChild"
#endif
#ifndef WIFI_PASSWORD_VALUE
#define WIFI_PASSWORD_VALUE "ay_carico"
#endif
#ifndef BACKEND_BASE_URL_VALUE
#define BACKEND_BASE_URL_VALUE "http://192.168.8.100:5000"
#endif
#ifndef API_KEY_VALUE
#define API_KEY_VALUE "e52dc64913f9bbca16f37e4a27af776dee4b797db06e53abe99a9f5bc308e480"
#endif

const char *WIFI_SSID = WIFI_SSID_VALUE;
const char *WIFI_PASSWORD = WIFI_PASSWORD_VALUE;
const char *BACKEND_BASE_URL = BACKEND_BASE_URL_VALUE;
const char *API_KEY = API_KEY_VALUE;

constexpr bool SAVE_TO_SD = true;
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;
constexpr uint32_t HTTP_TIMEOUT_MS = 8000;
constexpr size_t EEPROM_SIZE = 8;

// Hardware pin definitions (Trigger moved to GPIO 14)
#define TRIGGER_PIN 14
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
String saveFrameToSd(camera_fb_t *frame);
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
  pinMode(TRIGGER_PIN, INPUT_PULLDOWN);

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
  Serial.println("[Status] Waiting for trigger pulses on GPIO 14...");
}

void loop()
{
  if (digitalRead(TRIGGER_PIN) == HIGH)
  {
    delay(15);
    if (digitalRead(TRIGGER_PIN) == HIGH)
    {
      captureAndUpload();
      
      // Clear out remaining trigger state immediately to prepare for next capture
      while (digitalRead(TRIGGER_PIN) == HIGH)
      {
        yield();
      }
    }
  }
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
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  uint32_t startedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startedAt < WIFI_CONNECT_TIMEOUT_MS)
  {
    delay(100);
  }

  if (WiFi.status() != WL_CONNECTED)
  {
    return false;
  }

  return true;
}

bool sendCameraHeartbeat(const String &status)
{
  if (!connectWiFi()) return false;

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);

  if (!http.begin(client, String(BACKEND_BASE_URL) + "/api/telemetry")) return false;

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  http.addHeader("Accept", "application/json");

  String payload = "{\"device_name\":\"ESP32-CAM\",\"status\":\"" + status + "\",\"metric_name\":\"capture_status\",\"metric_value\":1.0,\"metric_unit\":\"binary\",\"metadata\":{\"source\":\"esp32-cam\",\"trigger\":\"capture\"}}";

  int statusCode = http.POST(payload);
  http.end();
  return (statusCode >= 200 && statusCode < 300);
}

bool uploadFrameToRecognition(camera_fb_t *frame)
{
  if (frame == nullptr || frame->buf == nullptr || frame->len == 0) return false;
  if (!connectWiFi()) return false;

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);

  if (!http.begin(client, String(BACKEND_BASE_URL) + "/api/v1/facial-recognition/")) return false;

  String boundary = "----SentryVisionBoundaryTag";
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  http.addHeader("X-API-Key", API_KEY);
  http.addHeader("Accept", "application/json");

  String bodyPrefix = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"trigger_source\"\r\n\r\nmotion\r\n--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
  String bodySuffix = "\r\n--" + boundary + "--\r\n";

  size_t totalPayloadLen = bodyPrefix.length() + frame->len + bodySuffix.length();
  uint8_t *payloadBuffer = (uint8_t *)malloc(totalPayloadLen);
  if (payloadBuffer == nullptr)
  {
    http.end();
    return false;
  }

  memcpy(payloadBuffer, bodyPrefix.c_str(), bodyPrefix.length());
  memcpy(payloadBuffer + bodyPrefix.length(), frame->buf, frame->len);
  memcpy(payloadBuffer + bodyPrefix.length() + frame->len, bodySuffix.c_str(), bodySuffix.length());

  int statusCode = http.POST(payloadBuffer, totalPayloadLen);
  free(payloadBuffer);
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

  return (esp_camera_init(&config) == ESP_OK);
}

void captureAndUpload()
{
  // 1. Fire flash instantly on capture trigger
  digitalWrite(FLASH_LED_PIN, HIGH);

  // 2. Clear stale buffer and capture new frame immediately
  camera_fb_t *stale = esp_camera_fb_get();
  if (stale) esp_camera_fb_return(stale);

  camera_fb_t *frame = esp_camera_fb_get();
  
  // Turn off flash right after capturing frame data
  digitalWrite(FLASH_LED_PIN, LOW);

  if (frame == nullptr) return;

  // 3. Save to SD card and get path for conditional deletion
  String sdPath = saveFrameToSd(frame);

  // 4. Send telemetry & upload frame to server
  bool success = uploadFrameToRecognition(frame);
  sendCameraHeartbeat("Online");

  // Free memory buffer back to driver immediately
  esp_camera_fb_return(frame);

  // 5. If successfully posted to server, clean up and delete local SD copy
  if (success && sdPath.length() > 0 && sdAvailable)
  {
    if (SD_MMC.remove(sdPath.c_str()))
    {
      Serial.printf("[SD Card] Successfully deleted uploaded frame: %s\n", sdPath.c_str());
    }
  }
}

String saveFrameToSd(camera_fb_t *frame)
{
  if (!SAVE_TO_SD || !sdAvailable || frame == nullptr) return "";

  pictureNumber++;
  EEPROM.put(0, pictureNumber);
  EEPROM.commit();

  String path = "/capture_" + String(pictureNumber) + ".jpg";
  File file = SD_MMC.open(path.c_str(), FILE_WRITE);
  if (!file) return "";

  file.write(frame->buf, frame->len);
  file.close();
  return path;
}