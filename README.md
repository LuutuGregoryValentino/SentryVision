# Sentry Vision

Sentry Vision is a simple demonstration security dashboard for an ESP32-CAM system. It shows telemetry from connected devices and sends captured images to a Flask backend for facial recognition.

## Demonstration flow

```text
ESP32-CAM captures an image
        |
        v
Flask backend receives the image
        |
        v
Facial-recognition model identifies the possible person
        |
        v
Backend checks that identity in the personnel database
        |
        v
Dashboard shows the image, identity, confidence, and access status
```

The ESP32-CAM sends an image only. It must not send a person name, label, authorization status, or confidence value. The backend runs the trained model already included in this repository, then checks the server-side personnel database to determine whether the identified person is `Authorized`, `Unauthorized`, or `Unknown`.

This keeps recognition and access control simple and separate:

- The model suggests an identity and confidence from the image.
- The database decides whether that identity is authorized.
- No match, or a score below the chosen confidence threshold, is shown as `Unknown`.

## API used by the dashboard

### Face capture

`POST /api/v1/facial-recognition/`

Send a `multipart/form-data` request with an `image` JPEG/PNG file. The backend should return a response in this shape:

```json
{
  "recognized": true,
  "name": "Example Person",
  "confidence": 92.4,
  "authorization_status": "Authorized"
}
```

For no match, return:

```json
{
  "recognized": false,
  "confidence": 0,
  "authorization_status": "Unknown"
}
```

### Device telemetry

`GET /api/v1/device-status/` returns the latest status, metric, and last-seen time for the ESP32-CAM and other connected devices. The dashboard displays these cards at the top of the page.

## Planned backend refactor

The current implementation uses a client-supplied label for its demo logic. Replace that with the following small server flow:

1. Receive and validate the uploaded image.
2. Pass the image to the trained facial-recognition model.
3. Read the possible identity and confidence returned by the model.
4. If there is no match or confidence is too low, return `Unknown`.
5. Otherwise, look up the identity in the personnel database and return its authorization status.
6. Save a simple detection log and return the result to the dashboard.

Keep this as a straightforward Flask service for the demonstration. The dashboard gallery shows captures made during the current browser session; persistent capture history can be added later if needed.

## Current model note

The Flask backend runs the included Edge Impulse WebAssembly export through Node.js. Uploaded JPEG/PNG images are resized to the model's 160x160 RGB input, classified with the bundled labels, then checked against the personnel database. Scores below the model's confidence threshold, or the model's `unknown` class, are returned as `Unknown`.

The bundled model labels are `anold`, `faith`, `greg`, `kessie`, `misha`, and `unknown`. If you expect another person such as `Luutu` to match, retrain/export the model with that class included.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask --app run.py init-db
python run.py
```

The development service runs on `http://localhost:5000`.

Node.js must be available on `PATH` for the bundled WebAssembly model runner.

## Deployment readiness

A repository-specific deployment guide is available in [DEPLOYMENT.md](DEPLOYMENT.md). It covers the Flask app, the Edge Impulse runtime, environment variables, Gunicorn, and the production service layout used by this project.

### Unauthorized detection email notifications

To send an email to the admin when an unauthorized or unknown detection occurs, configure these environment variables before starting the app:

```powershell
$env:EMAIL_NOTIFICATION_ENABLED="true"
$env:MAIL_SERVER="smtp.sendgrid.net"
$env:MAIL_PORT="587"
$env:MAIL_USE_TLS="true"
$env:MAIL_USERNAME="apikey"
$env:MAIL_PASSWORD="YOUR_SENDGRID_API_KEY"
$env:MAIL_DEFAULT_SENDER="you@yourdomain.com"
$env:PUBLIC_BASE_URL="http://localhost:5000"
```

The notification recipient is hard-coded to snowchild@gmail.com.

When an unauthorized detection is logged, the app sends an email containing the image attachment plus links to either alert security or ignore the event.
