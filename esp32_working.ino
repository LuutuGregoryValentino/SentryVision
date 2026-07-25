#include <ESP32Servo.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ==========================================
// 📌 NETWORK & WEB APP CONFIGURATION
// ==========================================
const char* WIFI_SSID     = "Kessie";         // Replace with your Wi-Fi name
const char* WIFI_PASSWORD = "Kessie1011";     // Replace with your Wi-Fi password

const char* BACKEND_BASE_URL = "http://10.166.109.71:5000"; // Replace with your Flask server IP/URL
const char* API_KEY          = "e52dc64913f9bbca16f37e4a27af776dee4b797db06e53abe99a9f5bc308e480";   // Replace with your raw key

unsigned long lastHttpPostTime  = 0;
const int httpPostInterval      = 1000; // Throttle cloud telemetry to 1 second

// Non-blocking Wi-Fi retry management
unsigned long lastWifiRetryTime = 0;
const int wifiRetryInterval     = 10000; // Check Wi-Fi reconnection every 10 seconds

// ==========================================
// 📌 1. EXACT PIN DEFINITIONS (RETAINED)
// ==========================================
const int LED_RED         = 33;
const int LED_GREEN       = 32;
const int BUZZER          = 14;
const int TRIG_PIN        = 26;
const int ECHO_PIN        = 25;
const int RCWL_PIN        = 27;
const int SERVO1_PIN      = 13;     
const int SERVO2_PIN      = 12;     
const int CAM_TRIGGER_PIN = 4;  

// Hardware instances
Servo servo1;
Servo servo2;

// ==========================================
// 📌 2. CONSTANTS & SYSTEM TRACKERS
// ==========================================
const float MIN_DISTANCE = 0.5;   
const float MAX_DISTANCE = 500.0;

// Non-blocking Timing Intervals
unsigned long lastBlinkTime         = 0;
unsigned long lastServoTime         = 0;
unsigned long lastCamTriggerTime    = 0; 
unsigned long lastGuiLogTime        = 0;
unsigned long lastMotionTriggerTime = 0;

const int blinkInterval        = 250;     
const int alarmCaptureInterval = 2000;
const int guiLogInterval       = 100;        
const int motionHoldDuration   = 1500;  

// 🎯 CONSTANT NORMAL SPEED SERVO CONFIGURATION
const int sweepInterval        = 15;   
const int angleStep            = 2;

int currentAngle               = 0;                 
bool sweepingForward           = true;          
bool alarmState                = false;

// Forward Declarations
void setupHardware();
float readDistance();
bool checkMotion();
void streamGuiLog(bool motionDetected, float distanceCm);
void handleSystemStates(bool motionDetected, float distanceCm);
void sendTelemetryOnline(bool motionDetected, float distanceCm, bool isAlarm, int angle);
void sendFacialRecognitionTrigger(String detectedLabel);
void maintainWiFiConnection();

// ==========================================
// 📌 3. MAIN STANDARD FUNCTIONS
// ==========================================

void setup() {
  Serial.begin(115200);
  delay(500);
  
  setupHardware();
  
  // Initialize Wi-Fi in Station mode without blocking setup execution
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  Serial.println("--- System Core Live: Hardware Active & Backend-Linked ---");
}

void loop() {
  // 1. Maintain background Wi-Fi connection non-blockingly
  maintainWiFiConnection();

  // 2. Gather Sensor Data
  float distance = readDistance();
  bool motion = checkMotion();
  
  // 3. Stream formatted telemetry data locally to Serial GUI
  streamGuiLog(motion, distance);
  
  // 4. Process System Logic & Actuator Control (Servos, LEDs, Buzzer, Camera)
  handleSystemStates(motion, distance);

  // 5. Transmit Cloud Telemetry (Instantly bypassed if offline)
  bool insideAlarmZone = (distance > MIN_DISTANCE && distance <= 100.0);
  bool threatActive = (motion || insideAlarmZone);
  sendTelemetryOnline(motion, distance, threatActive, currentAngle);
  
  delay(5); // Minor stability tick
}

// ==========================================
// 📌 4. NETWORK & BACKEND MANAGEMENT
// ==========================================

void maintainWiFiConnection() {
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiRetryTime >= wifiRetryInterval) {
      lastWifiRetryTime = millis();
      Serial.println("[Wi-Fi] Attempting background reconnection...");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  }
}

void sendTelemetryOnline(bool motionDetected, float distanceCm, bool isAlarm, int angle) {
  if (WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastHttpPostTime < httpPostInterval) return;
  
  lastHttpPostTime = millis();

  HTTPClient http;
  http.setTimeout(500); // Prevent loop freeze on slow network

  String endpoint = String(BACKEND_BASE_URL) + "/api/telemetry";

  if (http.begin(endpoint)) {
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", API_KEY); 

    String jsonPayload = "{";
    jsonPayload += "\"motion\":" + String(motionDetected ? "true" : "false") + ",";
    jsonPayload += "\"distance\":" + String(distanceCm) + ",";
    jsonPayload += "\"alarm\":" + String(isAlarm ? "true" : "false") + ",";
    jsonPayload += "\"servo_angle\":" + String(angle);
    jsonPayload += "}";

    int httpResponseCode = http.POST(jsonPayload);
    if (httpResponseCode > 0) {
      Serial.printf("[WEB] Telemetry Response: %d\n", httpResponseCode);
    } else {
      Serial.printf("[WEB] Telemetry POST failed: %s\n", http.errorToString(httpResponseCode).c_str());
    }
    http.end();
  }
}

void sendFacialRecognitionTrigger(String detectedLabel) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.setTimeout(800);

  String endpoint = String(BACKEND_BASE_URL) + "/api/v1/facial-recognition/";

  if (http.begin(endpoint)) {
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", API_KEY);

    String jsonPayload = "{\"label\":\"" + detectedLabel + "\"}";

    int httpResponseCode = http.POST(jsonPayload);
  if (httpResponseCode >= 200 && httpResponseCode < 300) {
        String response = http.getString();
      Serial.printf("[FACIAL RECOG] Server Response (%d): %s\n", httpResponseCode, response.c_str());
    } else {
      Serial.printf("[FACIAL RECOG] Request failed: %s\n", http.errorToString(httpResponseCode).c_str());
    }
    http.end();
  }
}

// ==========================================
// 📌 5. INDEPENDENT HARDWARE FUNCTIONS
// ==========================================

void setupHardware() {
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(CAM_TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RCWL_PIN, INPUT);
  
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  
  servo1.setPeriodHertz(50);
  servo1.attach(SERVO1_PIN, 500, 2400);
  
  servo2.setPeriodHertz(50);
  servo2.attach(SERVO2_PIN, 500, 2400);
  
  servo1.write(0);
  servo2.write(0);

  digitalWrite(BUZZER, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(CAM_TRIGGER_PIN, LOW);
  digitalWrite(LED_GREEN, HIGH); 
}

float readDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 15000); 
  float calculatedDistance = duration * 0.0343 / 2.0;
  
  if (calculatedDistance < MIN_DISTANCE || calculatedDistance > MAX_DISTANCE) {
    return -1.0; 
  }
  return calculatedDistance;
}

bool checkMotion() {
  bool rawReading = (digitalRead(RCWL_PIN) == HIGH);
  
  if (rawReading) {
    lastMotionTriggerTime = millis();
    return true;
  }
  
  if (millis() - lastMotionTriggerTime < motionHoldDuration) {
    return true; 
  }
  
  return false; 
}

void streamGuiLog(bool motionDetected, float distanceCm) {
  if (millis() - lastGuiLogTime >= guiLogInterval) {
    lastGuiLogTime = millis();
    
    Serial.print("GUI_DATA,");
    Serial.print(motionDetected ? "1," : "0,");
    Serial.println(distanceCm); 
  }
}

void handleSystemStates(bool motionDetected, float distanceCm) {
  bool insideAlarmZone = (distanceCm > MIN_DISTANCE && distanceCm <= 100.0);
  bool threatActive = (motionDetected || insideAlarmZone);

  // --- ALARM HARDWARE LOGIC ---
  if (threatActive) {
    digitalWrite(LED_GREEN, LOW);       
    
    // Trigger Camera Pin & Sync with Facial Recog API
    if (millis() - lastCamTriggerTime >= alarmCaptureInterval) {
      lastCamTriggerTime = millis();
      digitalWrite(CAM_TRIGGER_PIN, HIGH);
      delay(50);
      digitalWrite(CAM_TRIGGER_PIN, LOW);

      // Example trigger call; replace "Luutu" with Edge Impulse inferred result string if local
      sendFacialRecognitionTrigger("Luutu");
    }
    
    if (millis() - lastBlinkTime >= blinkInterval) {
      lastBlinkTime = millis();
      alarmState = !alarmState; 
      digitalWrite(LED_RED, alarmState);
      digitalWrite(BUZZER, alarmState);
    }
  } 
  else {
    digitalWrite(LED_RED, LOW);
    digitalWrite(BUZZER, LOW);
    digitalWrite(CAM_TRIGGER_PIN, LOW); 
    digitalWrite(LED_GREEN, HIGH);       
    alarmState = false;
    lastCamTriggerTime = 0;
  }

  // --- CONTINUOUS SERVO SWEEP ---
  if (millis() - lastServoTime >= sweepInterval) { 
    lastServoTime = millis();
    
    if (sweepingForward) {
      currentAngle += angleStep;
      if (currentAngle >= 180) {
        currentAngle = 180;
        sweepingForward = false;
      }
    } else {
      currentAngle -= angleStep;
      if (currentAngle <= 0) {
        currentAngle = 0;
        sweepingForward = true;
      }
    }
    
    servo1.write(currentAngle);
    servo2.write(currentAngle); 
  }
}