# Sentry Vision Flask Backend

Backend service for an ESP32-CAM and Edge Impulse powered embedded security system.

## Features

- `POST /api/v1/facial-recognition/` ingests facial recognition labels.
- Strict authorization matrix for Kessie, Anold, Faith, Misha, and unknown faces.
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

Unrecognized:

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
  "authorization_status": "Unauthorized",
  "recognized": false,
  "alert": "Unrecognized face detected"
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
