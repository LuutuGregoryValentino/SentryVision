#include <ESP32Servo.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ==========================================================================
// SENTRY-VISION — BASE NODE FIRMWARE
// Sleep -> Armed (green) -> Alert (red) perimeter-breach detector.
// Targets: ESP32 Dev Module | arduino-esp32 core 2.0.18 (ledc v2 API)
// ==========================================================================

// ==========================================
// 📌 NETWORK & WEB APP CONFIGURATION
// ==========================================
#ifndef WIFI_SSID_VALUE
#define WIFI_SSID_VALUE "Kessie"
#endif
#ifndef WIFI_PASSWORD_VALUE
#define WIFI_PASSWORD_VALUE "Kessie1011"
#endif
#ifndef BACKEND_BASE_URL_VALUE
#define BACKEND_BASE_URL_VALUE "http://10.192.102.71:5000"
#endif
#ifndef API_KEY_VALUE
#define API_KEY_VALUE "e52dc64913f9bbca16f37e4a27af776dee4b797db06e53abe99a9f5bc308e480"
#endif

const char* WIFI_SSID        = WIFI_SSID_VALUE;
const char* WIFI_PASSWORD    = WIFI_PASSWORD_VALUE;
const char* BACKEND_BASE_URL = BACKEND_BASE_URL_VALUE;
const char* API_KEY          = API_KEY_VALUE;

unsigned long lastHttpPostTime = 0;
const int httpPostInterval     = 1000; // throttle cloud telemetry to 1s

unsigned long lastWifiRetryTime = 0;
const int wifiRetryInterval     = 10000; // check Wi-Fi reconnection every 10s

// ==========================================
// 📌 PIN DEFINITIONS (unchanged from your wiring)
// ==========================================
const int LED_RED         = 33;
const int LED_GREEN       = 32;
const int BUZZER          = 14;
const int TRIG_PIN        = 26;
const int ECHO_PIN        = 25;
const int RCWL_PIN        = 27;
const int SERVO1_PIN      = 13;  // camera-facing servo
const int SERVO2_PIN      = 12;  // NOTE: GPIO12 is a boot strapping pin (MTDI/flash voltage select).
                                  // Fine in practice since a servo signal line doesn't hold a strong
                                  // level through reset, but if you ever see boot weirdness after wiring
                                  // this channel, that's the first thing to suspect.
const int CAM_TRIGGER_PIN = 16;

Servo servo1;
Servo servo2;

// ==========================================
// 📌 TUNABLE CONSTANTS — adjust these, not the logic below
// ==========================================

// --- Ultrasonic ranging ---
const float MIN_DISTANCE = 0.5;    // cm, below this = noise, reading discarded
const float MAX_DISTANCE = 400.0;  // cm, matches the "accurately maps 400cm" spec
const unsigned long ULTRASONIC_MIN_INTERVAL_MS = 60; // HC-SR04-class min gap between pings

// --- Servo sweep speed / smoothness ---
const int ANGLE_STEP          = 1;   // degrees per micro-step -> smoother visible motion
const int SWEEP_INTERVAL_MS   = 10;  // ms between micro-steps at normal (ARMED) speed
const int RESCAN_INTERVAL_MS  = 6;   // faster micro-step interval for the post-alert quick re-scan
const int EASE_ZONE_DEG       = 20;  // degrees near each end where the sweep slows down
const int EASE_INTERVAL_MS    = 22;  // interval used inside the ease zone (avoids a hard jerk on reversal)

// --- Breach detection ---
const int   MAX_SCAN_SAMPLES       = 80;   // upper bound on {angle,distance} pairs stored per sweep
const float DEVIATION_THRESHOLD_CM = 18.0; // live reading this much *closer* than baseline = breach
const int   BASELINE_MATCH_TOLERANCE_DEG = 10; // max angle gap allowed when matching live->baseline

// --- State timing ---
const unsigned long ALERT_HOLD_MS         = 600;  // freeze sweep so the camera gets a clean, sharp shot
const unsigned long ALERT_MIN_DURATION_MS = 4000; // minimum time spent "red" once triggered
const unsigned long ARMED_TO_SLEEP_MS     = 8000; // no-motion timeout before returning to SLEEP
const unsigned long CAM_PULSE_MS          = 50;   // camera trigger pulse width

const int blinkInterval      = 250;  // red LED blink period while in ALERT
const int guiLogInterval     = 100;
const int motionHoldDuration = 1500; // RCWL debounce hold

// --- Buzzer (LEDC) ---
// ESP32Servo reserves LEDC timers 0 and 1 for the two servo channels (see setupHardware()).
// Channel 8 lives on timer 2, which nothing else touches, so the buzzer's tone frequency
// can never fight with a servo's PWM frequency (that fight is a known ESP32 gotcha — a shared
// timer means retuning one channel silently retunes its neighbour too).
const int BUZZER_CHANNEL    = 8;
const int BUZZER_RESOLUTION = 10;

struct ToneStep { uint16_t freq; uint16_t durMs; };
// A short rising three-note chime (C6-E6-G6), repeated with a gap — distinctive and clearly
// "designed," not a generic monotone beeper. This is what plays during STATE_ALERT.
const ToneStep ALARM_PATTERN[] = {
  {1046, 90}, {0, 40}, {1318, 90}, {0, 40}, {1568, 160}, {0, 220},
  {1046, 90}, {0, 40}, {1318, 90}, {0, 40}, {1568, 160}, {0, 420}
};
const int ALARM_STEPS = sizeof(ALARM_PATTERN) / sizeof(ALARM_PATTERN[0]);
const uint16_t NOTIFY_FREQ = 1568; // single short chirp, used for non-alarm system events

// ==========================================
// 📌 STATE MACHINE
// ==========================================
enum SystemState { STATE_SLEEP, STATE_ARMED, STATE_ALERT };
SystemState state = STATE_SLEEP;

enum AlertPhase { ALERT_HOLD, ALERT_RESCAN };
AlertPhase alertPhase;
unsigned long alertPhaseStart = 0;
unsigned long alertEnterTime  = 0;

unsigned long lastMotionTriggerTime = 0;

// ==========================================
// 📌 SERVO SWEEP STATE
// ==========================================
unsigned long lastServoTime = 0;
int  currentAngle     = 0;
bool sweepingForward  = true;

// ==========================================
// 📌 ULTRASONIC RUNTIME STATE
// ==========================================
unsigned long lastPingTime    = 0;
float         lastLiveDistance = -1.0;
int           lastLiveAngle    = 0;
bool          newSampleReady   = false;

// ==========================================
// 📌 BASELINE ("INIT SCAN") STORAGE
// Captured once per boot in setup(), kept in RAM only — matches the "overwrite each
// restart" requirement, no flash/EEPROM wear, no stale calibration across power cycles.
// ==========================================
float baselineDist[MAX_SCAN_SAMPLES];
int   baselineAngle[MAX_SCAN_SAMPLES];
int   baselineCount = 0;
bool  baselineReady = false;

// ==========================================
// 📌 CAMERA TRIGGER (non-blocking pulse)
// ==========================================
bool camPulseActive = false;
unsigned long camPulseEnd = 0;

// ==========================================
// 📌 ALARM / NOTIFY TONE STATE
// ==========================================
bool alarmToneActive = false;
int  alarmStepIdx    = 0;
unsigned long alarmStepStart = 0;

bool notifyActive = false;
unsigned long notifyEnd = 0;

// LED alert blink
unsigned long lastBlinkTime = 0;
bool alarmState = false;

unsigned long lastGuiLogTime = 0;

// ==========================================
// 📌 FORWARD DECLARATIONS
// ==========================================
void setupHardware();
void setupBuzzer();
void runBaselineCalibration();
float pingDistanceBlocking();
void updateUltrasonic();
void updateServoSweep();
bool checkMotion();
float baselineAt(int angle);
bool isBreach(float liveDist, int angle);
void enterAlert();
void restartAlertCapture();
void handleSleepState(bool motionNow);
void handleArmedState();
void handleAlertState();
void updateLEDs();
void requestCameraCapture();
void updateCameraPulse();
void resetAlarmTone();
void applyAlarmStep();
void updateAlarmTone();
void playNotifyBeep();
void updateNotifyBeep();
void streamGuiLog(bool motionDetected, float distanceCm);
void maintainWiFiConnection();
void sendTelemetryOnline(bool motionDetected, float distanceCm, bool isAlarm, int angle);

// ==========================================================================
// 📌 MAIN STANDARD FUNCTIONS
// ==========================================================================

void setup() {
  Serial.begin(115200);
  delay(500);

  setupHardware();
  setupBuzzer();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  runBaselineCalibration(); // one-time blocking sweep; fine here, setup() only runs once
  playNotifyBeep();

  state = STATE_SLEEP;
  lastMotionTriggerTime = millis();

  Serial.println("--- Sentry core ready: baseline captured, system asleep ---");
}

void loop() {
  maintainWiFiConnection();

  bool motionNow = checkMotion();
  if (motionNow) lastMotionTriggerTime = millis();

  updateUltrasonic();
  updateServoSweep();
  updateAlarmTone();
  updateNotifyBeep();
  updateCameraPulse();

  switch (state) {
    case STATE_SLEEP: handleSleepState(motionNow); break;
    case STATE_ARMED: handleArmedState(); break;
    case STATE_ALERT: handleAlertState(); break;
  }

  updateLEDs();
  streamGuiLog(motionNow, lastLiveDistance);
  sendTelemetryOnline(motionNow, lastLiveDistance, state == STATE_ALERT, currentAngle);

  delay(5); // minor stability tick
}

// ==========================================================================
// 📌 HARDWARE SETUP
// ==========================================================================

void setupHardware() {
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(CAM_TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RCWL_PIN, INPUT);

  // Reserve LEDC timers 0 & 1 exclusively for the two servos. Timers 2 & 3 are left
  // untouched so the buzzer (below) can use them without any frequency cross-talk.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);

  servo1.setPeriodHertz(50);
  servo1.attach(SERVO1_PIN, 500, 2400);

  servo2.setPeriodHertz(50);
  servo2.attach(SERVO2_PIN, 500, 2400);

  servo1.write(0);
  servo2.write(0);

  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(CAM_TRIGGER_PIN, LOW);
}

void setupBuzzer() {
  ledcSetup(BUZZER_CHANNEL, 2000, BUZZER_RESOLUTION); // placeholder freq; each tone sets its own
  ledcAttachPin(BUZZER, BUZZER_CHANNEL);
  ledcWrite(BUZZER_CHANNEL, 0); // silent
}

// ==========================================================================
// 📌 BASELINE CALIBRATION ("INIT SCAN")
// Sweeps 0->180 once, taking one ultrasonic reading per ping cycle, and records
// {angle, distance} pairs. This is the "number of perfect measurements the
// ultrasonic can take in one sweep" — it falls out naturally from the ping
// cadence and sweep speed instead of being a hand-picked magic number.
// ==========================================================================

void runBaselineCalibration() {
  servo1.write(0);
  servo2.write(0);
  delay(400); // let both servos physically settle at the home position

  baselineCount = 0;
  currentAngle = 0;
  unsigned long lastStep = millis();
  unsigned long lastPing = 0;

  while (currentAngle < 180 && baselineCount < MAX_SCAN_SAMPLES) {
    unsigned long now = millis();

    if (now - lastStep >= SWEEP_INTERVAL_MS) {
      lastStep = now;
      currentAngle += ANGLE_STEP;
      if (currentAngle > 180) currentAngle = 180;
      servo1.write(currentAngle);
      servo2.write(currentAngle);
    }

    if (now - lastPing >= ULTRASONIC_MIN_INTERVAL_MS) {
      lastPing = now;
      float d = pingDistanceBlocking();
      if (d > 0) {
        baselineAngle[baselineCount] = currentAngle;
        baselineDist[baselineCount]  = d;
        baselineCount++;
      }
    }
  }

  baselineReady = (baselineCount > 0);
  sweepingForward = false; // we ended at 180, so live sweeping should head back down first

  Serial.printf("[CAL] Baseline captured: %d samples across the sweep\n", baselineCount);
}

// ==========================================================================
// 📌 ULTRASONIC
// ==========================================================================

float pingDistanceBlocking() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 15000);
  if (duration == 0) return -1.0; // no echo -> nothing in range

  float d = duration * 0.0343 / 2.0;
  if (d < MIN_DISTANCE || d > MAX_DISTANCE) return -1.0;
  return d;
}

void updateUltrasonic() {
  if (state == STATE_SLEEP) return; // dormant per spec — RCWL is the only thing "awake"

  unsigned long now = millis();
  if (now - lastPingTime >= ULTRASONIC_MIN_INTERVAL_MS) {
    lastPingTime = now;
    lastLiveDistance = pingDistanceBlocking();
    lastLiveAngle = currentAngle;
    newSampleReady = true;
  }
}

// ==========================================================================
// 📌 MOTION (RCWL-0516)
// ==========================================================================

bool checkMotion() {
  bool rawReading = (digitalRead(RCWL_PIN) == HIGH);

  if (rawReading) {
    return true;
  }
  if (millis() - lastMotionTriggerTime < motionHoldDuration) {
    return true;
  }
  return false;
}

// ==========================================================================
// 📌 SERVO SWEEP — smooth, eased at the reversal points, speed depends on state
// ==========================================================================

void updateServoSweep() {
  if (state == STATE_SLEEP) return;                     // motors dormant while asleep
  if (state == STATE_ALERT && alertPhase == ALERT_HOLD) return; // frozen for a clean camera shot

  unsigned long now = millis();
  bool inEaseZone = (currentAngle <= EASE_ZONE_DEG) || (currentAngle >= 180 - EASE_ZONE_DEG);

  int interval;
  if (state == STATE_ALERT && alertPhase == ALERT_RESCAN) {
    interval = RESCAN_INTERVAL_MS;       // quick re-check pass
  } else if (inEaseZone) {
    interval = EASE_INTERVAL_MS;         // slow down near the ends to avoid a jerky reversal
  } else {
    interval = SWEEP_INTERVAL_MS;        // normal cruising speed
  }

  if (now - lastServoTime < (unsigned long)interval) return;
  lastServoTime = now;

  if (sweepingForward) {
    currentAngle += ANGLE_STEP;
    if (currentAngle >= 180) { currentAngle = 180; sweepingForward = false; }
  } else {
    currentAngle -= ANGLE_STEP;
    if (currentAngle <= 0) { currentAngle = 0; sweepingForward = true; }
  }

  servo1.write(currentAngle);
  servo2.write(currentAngle);
}

// ==========================================================================
// 📌 BREACH DETECTION — compares a live reading against the baseline at the
// nearest matching angle (works regardless of sweep direction).
// ==========================================================================

float baselineAt(int angle) {
  int bestIdx = -1;
  int bestDiff = 999;
  for (int i = 0; i < baselineCount; i++) {
    int diff = abs(baselineAngle[i] - angle);
    if (diff < bestDiff) { bestDiff = diff; bestIdx = i; }
  }
  if (bestIdx == -1 || bestDiff > BASELINE_MATCH_TOLERANCE_DEG) return -1.0;
  return baselineDist[bestIdx];
}

bool isBreach(float liveDist, int angle) {
  if (!baselineReady || liveDist < 0) return false;
  float base = baselineAt(angle);
  if (base < 0) return false;
  return (base - liveDist) > DEVIATION_THRESHOLD_CM; // something now noticeably closer than baseline
}

// ==========================================================================
// 📌 STATE HANDLERS
// ==========================================================================

void handleSleepState(bool motionNow) {
  if (motionNow) {
    state = STATE_ARMED;
    playNotifyBeep();
    Serial.println("[STATE] SLEEP -> ARMED (motion detected)");
  }
}

void handleArmedState() {
  if (millis() - lastMotionTriggerTime > ARMED_TO_SLEEP_MS) {
    state = STATE_SLEEP;
    Serial.println("[STATE] ARMED -> SLEEP (no motion timeout)");
    return;
  }

  if (newSampleReady) {
    newSampleReady = false;
    if (isBreach(lastLiveDistance, lastLiveAngle)) {
      enterAlert();
    }
  }
}

void handleAlertState() {
  unsigned long now = millis();

  if (alertPhase == ALERT_HOLD && now - alertPhaseStart >= ALERT_HOLD_MS) {
    alertPhase = ALERT_RESCAN;
    alertPhaseStart = now;
  }

  if (alertPhase == ALERT_RESCAN && newSampleReady) {
    newSampleReady = false;
    if (isBreach(lastLiveDistance, lastLiveAngle)) {
      // Still a live threat — capture again and restart the hold/rescan cycle ("new, then old").
      alertEnterTime = now;
      alertPhase = ALERT_HOLD;
      alertPhaseStart = now;
      restartAlertCapture();
    }
  }

  if (now - alertEnterTime >= ALERT_MIN_DURATION_MS && alertPhase == ALERT_RESCAN) {
    state = STATE_ARMED;
    lastMotionTriggerTime = now; // stay armed a while longer after an alert
    Serial.println("[STATE] ALERT -> ARMED (clear)");
  }
}

void enterAlert() {
  state = STATE_ALERT;
  alertPhase = ALERT_HOLD;
  alertPhaseStart = millis();
  alertEnterTime = millis();
  requestCameraCapture();
  resetAlarmTone();
  Serial.println("[STATE] ARMED -> ALERT (breach detected)");
}

// Re-arm the hold/capture cycle without re-logging a full state transition (used on re-trigger).
void restartAlertCapture() {
  requestCameraCapture();
  resetAlarmTone();
}

// ==========================================================================
// 📌 LEDS
// ==========================================================================

void updateLEDs() {
  switch (state) {
    case STATE_SLEEP:
      digitalWrite(LED_GREEN, LOW);
      digitalWrite(LED_RED, LOW);
      break;

    case STATE_ARMED:
      digitalWrite(LED_GREEN, HIGH);
      digitalWrite(LED_RED, LOW);
      break;

    case STATE_ALERT:
      digitalWrite(LED_GREEN, LOW);
      if (millis() - lastBlinkTime >= blinkInterval) {
        lastBlinkTime = millis();
        alarmState = !alarmState;
        digitalWrite(LED_RED, alarmState);
      }
      break;
  }
}

// ==========================================================================
// 📌 CAMERA TRIGGER (non-blocking pulse — the original blocking delay(50) is gone)
// ==========================================================================

void requestCameraCapture() {
  digitalWrite(CAM_TRIGGER_PIN, HIGH);
  camPulseActive = true;
  camPulseEnd = millis() + CAM_PULSE_MS;
}

void updateCameraPulse() {
  if (camPulseActive && millis() >= camPulseEnd) {
    digitalWrite(CAM_TRIGGER_PIN, LOW);
    camPulseActive = false;
  }
}

// ==========================================================================
// 📌 BUZZER — distinctive alarm chime + short system-notify chirp
// Both use ledcWriteTone() directly on BUZZER_CHANNEL (see setupBuzzer()), so
// neither ever calls tone()/noTone(), avoiding the ESP32Servo/tone timer clash.
// ==========================================================================

void applyAlarmStep() {
  uint16_t f = ALARM_PATTERN[alarmStepIdx].freq;
  ledcWriteTone(BUZZER_CHANNEL, f); // f == 0 -> silence (the gaps between notes)
}

void resetAlarmTone() {
  alarmStepIdx = 0;
  alarmStepStart = millis();
  alarmToneActive = true;
  applyAlarmStep();
}

void updateAlarmTone() {
  if (state != STATE_ALERT) {
    if (alarmToneActive) {
      ledcWriteTone(BUZZER_CHANNEL, 0);
      alarmToneActive = false;
    }
    return;
  }

  if (!alarmToneActive) resetAlarmTone();

  unsigned long now = millis();
  if (now - alarmStepStart >= ALARM_PATTERN[alarmStepIdx].durMs) {
    alarmStepIdx = (alarmStepIdx + 1) % ALARM_STEPS;
    alarmStepStart = now;
    applyAlarmStep();
  }
}

void playNotifyBeep() {
  ledcWriteTone(BUZZER_CHANNEL, NOTIFY_FREQ);
  notifyActive = true;
  notifyEnd = millis() + 90;
}

void updateNotifyBeep() {
  if (notifyActive && millis() >= notifyEnd) {
    ledcWriteTone(BUZZER_CHANNEL, 0);
    notifyActive = false;
  }
}

// ==========================================================================
// 📌 SERIAL GUI LOG
// ==========================================================================

void streamGuiLog(bool motionDetected, float distanceCm) {
  if (millis() - lastGuiLogTime >= guiLogInterval) {
    lastGuiLogTime = millis();
    Serial.print("GUI_DATA,");
    Serial.print(motionDetected ? "1," : "0,");
    Serial.println(distanceCm);
  }
}

// ==========================================================================
// 📌 NETWORK & BACKEND
// ==========================================================================

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
  http.setTimeout(500);

  String endpoint = String(BACKEND_BASE_URL) + "/api/telemetry";
  const char* stateStr = (state == STATE_SLEEP) ? "SLEEP" : (state == STATE_ARMED) ? "ARMED" : "ALERT";

  if (http.begin(endpoint)) {
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", API_KEY);

    String jsonPayload = "{";
    jsonPayload += "\"device_name\":\"ESP32-BASE\",";
    jsonPayload += "\"status\":\"Online\",";
    jsonPayload += "\"state\":\"" + String(stateStr) + "\",";
    jsonPayload += "\"motion\":" + String(motionDetected ? "true" : "false") + ",";
    jsonPayload += "\"distance\":" + String(distanceCm) + ",";
    jsonPayload += "\"alarm\":" + String(isAlarm ? "true" : "false") + ",";
    jsonPayload += "\"servo_angle\":" + String(angle) + ",";
    jsonPayload += "\"metric_name\":\"distance\",";
    jsonPayload += "\"metric_value\":" + String(distanceCm) + ",";
    jsonPayload += "\"metric_unit\":\"cm\",";
    jsonPayload += "\"metadata\":{\"source\":\"esp32-base\",\"motion\":" + String(motionDetected ? "true" : "false") + ",\"alarm\":" + String(isAlarm ? "true" : "false") + "}";
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
