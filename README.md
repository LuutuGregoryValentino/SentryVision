# Sentry Vision Flask Backend

Backend service for an ESP32-CAM and Edge Impulse powered embedded security system.

## Features

- `POST /api/v1/facial-recognition/` ingests facial recognition labels, Edge Impulse classification payloads, or model features.
- Strict authorization matrix for Kessie, Anold, Faith, Misha, Luutu, and unknown faces.
- Unrecognized faces create database logs with `notification_required=true`.
- `GET /api/v1/device-status/` returns status for ESP32-CAM, Ultrasonic Sensor, Buzzer, and RCWL Sensor.
- SQLite database with Flask-SQLAlchemy models for personnel, detections, and devices.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask --app run.py init-db
python run.py
```

The service runs on `http://localhost:5000`.

## Example Requests

Recognized and authorized:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5000/api/v1/facial-recognition/ `
  -ContentType "application/json" `
  -Body '{"label":"Kessie"}'
```

Response:

```json
{
  "name": "Kessie",
  "role": "Administrator/Engineer",
  "authorization_status": "Authorized",
  "recognized": true
}
```

Multipart upload with image and label:

```powershell
$body = @{
  label = 'Kessie'
  trigger_source = 'motion'
  image = Get-Item 'frame.jpg'
}
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5000/api/v1/facial-recognition/ `
  -ContentType 'multipart/form-data' `
  -Body $body
```

The backend saves the uploaded image and uses the `label` value to determine recognition. If you omit `label`, the backend will try to run `app/facial_recognition_assets/model.lite`; this requires a TensorFlow Lite interpreter such as `tensorflow` or `tflite-runtime`. This Edge Impulse model reports labels in this order: `anold`, `faith`, `greg`, `kessie`, `misha`, `unknown`. The backend maps the model label `greg` to the personnel record `Luutu`.

Model features:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5000/api/v1/facial-recognition/ `
  -ContentType "application/json" `
  -Body '{"features":[0.1,0.2,0.3]}'
```

Recognized but unauthorized:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5000/api/v1/facial-recognition/ `
  -ContentType "application/json" `
  -Body '{"label":"Luutu"}'
```

Response:

```json
{
  "name": "Luutu",
  "role": "Visitor/Staff",
  "authorization_status": "Unauthorized",
  "recognized": true
}
```

Device status:

```powershell
Invoke-RestMethod http://localhost:5000/api/v1/device-status/
```

Optional device telemetry update:

```powershell
Invoke-RestMethod `
  -Method Patch `
  -Uri "http://localhost:5000/api/v1/device-status/Ultrasonic%20Sensor/" `
  -ContentType "application/json" `
  -Body '{"status":"Active","metric_name":"distance","metric_value":27.4,"metric_unit":"cm","metadata":{"location":"entryway"}}'
```
