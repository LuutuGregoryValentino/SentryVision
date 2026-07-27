import os
from pathlib import Path

from flask import current_app
from sqlalchemy import func

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


def _pick_controller_metric(payload):
    if "servo_angle" in payload and payload.get("servo_angle") is not None:
        return "servo_angle", payload.get("servo_angle"), "degrees"
    if "alarm" in payload and payload.get("alarm") is not None:
        return "alarm", 1.0 if payload.get("alarm") else 0.0, "binary"
    return _pick_metric(payload)


def _upsert_device_record(device_name, status, metric_name, metric_value, metric_unit, metadata):
    device = DeviceStatus.query.filter_by(device_name=device_name).first()
    if device is None:
        device = DeviceStatus(device_name=device_name)

    device.status = status or "Online"
    device.last_ping = utc_now()
    device.metric_name = metric_name
    device.metric_value = metric_value
    device.metric_unit = metric_unit
    device.metadata_json = metadata
    db.session.add(device)
    return device


def upsert_device_status(payload):
    device_name = (payload.get("device_name") or payload.get("source") or "ESP32-DEVICE").strip()
    if not device_name:
        device_name = "ESP32-DEVICE"

    status = payload.get("status") or "Online"
    metric_name, metric_value, metric_unit = _pick_controller_metric(payload)
    base_metadata = dict(payload.get("metadata") or {})
    for key in ("motion", "distance", "alarm", "servo_angle", "trigger_source"):
        if key in payload and payload[key] is not None:
            base_metadata[key] = payload[key]
    base_metadata.setdefault("source", "esp32")

    device = _upsert_device_record(
        device_name,
        status,
        metric_name,
        metric_value,
        metric_unit,
        base_metadata,
    )

    if "distance" in payload and payload.get("distance") is not None:
        _upsert_device_record(
            "Ultrasonic Sensor",
            status,
            "distance",
            payload.get("distance"),
            "cm",
            {
                "source": device_name,
                "sensor_type": "ultrasonic",
            },
        )

    if "motion" in payload and payload.get("motion") is not None:
        _upsert_device_record(
            "RCWL Sensor",
            status,
            "motion",
            1.0 if payload.get("motion") else 0.0,
            "binary",
            {
                "source": device_name,
                "sensor_type": "microwave radar",
            },
        )

    if "alarm" in payload and payload.get("alarm") is not None:
        _upsert_device_record(
            "Buzzer",
            status,
            "alarm_state",
            1.0 if payload.get("alarm") else 0.0,
            "binary",
            {
                "source": device_name,
                "purpose": "audible alert",
            },
        )

    db.session.commit()
    return device


def process_facial_recognition(image_path, image_filename=None):
    model_export = Path(current_app.root_path).parent / "sentry-vision-wasm-browser-simd-v1-impulse-#1.zip"
    result = FacialRecognitionEngine(model_export).recognize(image_path)
    current_app.logger.info(
        "Recognition engine processed image=%s model_status=%s confidence=%.1f",
        image_filename,
        result.model_status,
        result.confidence,
    )

    detected_label = (result.label or "").strip()
    personnel = None
    if detected_label:
        personnel = Personnel.query.filter(func.lower(Personnel.label) == detected_label.lower()).first()

    normalized_label = personnel.label if personnel else (detected_label.title() if detected_label else "Unknown")

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
    response["image_saved"] = image_filename or os.path.basename(image_path)
    response["confidence"] = result.confidence
    response["model_status"] = result.model_status
    response["scores"] = result.scores

    return response, 200
