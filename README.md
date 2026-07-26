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

## Facial-recognition backend data flow

`POST /api/v1/facial-recognition/` accepts only a `multipart/form-data` image
under the `image` field. The API key is checked first; any label included in the
form is ignored. The route saves the original capture in `instance/uploads/`,
then the recognition service performs this server-side flow:

```text
JPEG/PNG upload → Pillow decodes RGB image → resize to 160×160 → float32 / 255
    → FacialModelForSentryVision.4.lite → six class scores
    → highest score must be ≥ 75% → Personnel lookup → DetectionLog + JSON response
```

The TensorFlow Lite model returns six scores but does not embed human-readable
labels. The backend maps them to `Anold`, `Faith`, `Kessie`, `Luutu`, `Misha`,
and `Unknown` in `config.py`; confirm that order against the training dataset
before deployment, and update `FACIAL_MODEL_LABELS` if needed. `Unknown` or a
score below the configured threshold never receives personnel authorization.
The returned `confidence` is a percentage.

The old browser/WASM export was removed because Flask cannot execute it and the
new `.lite` model is now the sole model used by the backend.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask --app run.py init-db
python run.py
```

The development service runs on `http://localhost:5000`.
