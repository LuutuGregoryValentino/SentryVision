import os
from pathlib import Path

from flask import current_app
from .extensions import db
from .models import DetectionLog, Personnel
from .recognition import FacialRecognitionEngine


UNRECOGNIZED_RESPONSE = {
    "authorization_status": "Unauthorized",
    "recognized": False,
    "alert": "Unrecognized face detected",
}


def process_facial_recognition(image_path, image_filename=None):
    model_export = Path(current_app.root_path).parent / "sentry-vision-wasm-browser-simd-v1-impulse-#1.zip"
    result = FacialRecognitionEngine(model_export).recognize(image_path)
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
            authorization_status="Unauthorized",
            alert="Unrecognized face detected",
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

    response["image_received"] = True
    response["image_saved"] = image_filename or os.path.basename(image_path)
    response["confidence"] = result.confidence
    response["model_status"] = result.model_status

    return response, 200
