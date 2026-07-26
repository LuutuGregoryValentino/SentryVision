from pathlib import Path

from flask import current_app

from .extensions import db
from .models import DetectionLog, DeviceStatus, Personnel, utc_now
from .recognition import FacialRecognitionEngine


UNRECOGNIZED_RESPONSE = {
    "authorization_status": "Unknown",
    "recognized": False,
    "alert": "No face identified",
}


def _pick_metric(payload):
    if payload.get("metric_name"):
        return payload.get("metric_name"), payload.get("metric_value"), payload.get("metric_unit")
    if "distance" in payload:
        return "distance", payload.get("distance"), "cm"
    if "motion" in payload:
        return "motion", 1.0 if payload.get("motion") else 0.0, "binary"
    if "servo_angle" in payload:
        return "servo_angle", payload.get("servo_angle"), "degrees"
    return None, None, None


def upsert_device_status(payload):
    device_name = (payload.get("device_name") or payload.get("source") or "ESP32-DEVICE").strip()
    if not device_name:
        device_name = "ESP32-DEVICE"

    device = DeviceStatus.query.filter_by(device_name=device_name).first()
    if device is None:
        device = DeviceStatus(device_name=device_name)

    device.status = payload.get("status") or "Online"
    device.last_ping = utc_now()
    metric_name, metric_value, metric_unit = _pick_metric(payload)
    device.metric_name = metric_name
    device.metric_value = metric_value
    device.metric_unit = metric_unit

    metadata = dict(payload.get("metadata") or {})
    for key in ("motion", "distance", "alarm", "servo_angle", "trigger_source"):
        if key in payload and payload[key] is not None:
            metadata[key] = payload[key]
    metadata.setdefault("source", "esp32")
    device.metadata_json = metadata

    db.session.add(device)
    db.session.commit()
    return device


def _recognition_engine():
    engine = current_app.extensions.get("facial_recognition_engine")
    if engine is None:
        engine = FacialRecognitionEngine(
            Path(current_app.config["FACIAL_MODEL_PATH"]),
            tuple(current_app.config["FACIAL_MODEL_LABELS"]),
            float(current_app.config["FACIAL_RECOGNITION_THRESHOLD"]),
        )
        current_app.extensions["facial_recognition_engine"] = engine
    return engine


def process_facial_recognition(image_path, image_filename=None):
    result = _recognition_engine().recognize(image_path)
    current_app.logger.info(
        "Recognition engine processed image=%s model_status=%s confidence=%.1f",
        image_filename,
        result.model_status,
        result.confidence,
    )

    normalized_label = (result.label or "Unknown").strip()
    personnel = Personnel.query.filter_by(label=normalized_label).first()

    if personnel is None:
        log = DetectionLog(
            detected_label=normalized_label,
            recognized=False,
            authorization_status="Unknown",
            alert="No face identified",
            notification_required=True,
            image_filename=image_filename,
            confidence=result.confidence,
        )
        db.session.add(log)
        db.session.commit()
        response = dict(UNRECOGNIZED_RESPONSE)
    else:
        log = DetectionLog(
            detected_label=normalized_label,
            recognized=True,
            authorization_status=personnel.authorization_status,
            notification_required=not personnel.is_authorized,
            personnel=personnel,
            image_filename=image_filename,
            confidence=result.confidence,
        )
        db.session.add(log)
        db.session.commit()
        response = personnel.to_detection_response()

    response["detected_label"] = normalized_label
    response["image_received"] = True
    response["image_saved"] = image_filename or Path(image_path).name
    response["confidence"] = result.confidence
    response["model_status"] = result.model_status

    return response, 200
