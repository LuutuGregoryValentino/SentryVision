import os

from .extensions import db
from .models import DetectionLog, Personnel


UNRECOGNIZED_RESPONSE = {
    "authorization_status": "Unauthorized",
    "recognized": False,
    "alert": "Unrecognized face detected",
}


def process_facial_recognition(label, image_path=None):
    normalized_label = (label or "unknown").strip()
    personnel = Personnel.query.filter_by(label=normalized_label).first()

    if personnel is None:
        log = DetectionLog(
            detected_label=normalized_label,
            recognized=False,
            authorization_status="Unauthorized",
            alert="Unrecognized face detected",
            notification_required=True,
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
        )
        db.session.add(log)
        db.session.commit()
        response = personnel.to_detection_response()

    response["image_received"] = image_path is not None
    if image_path:
        response["image_saved"] = os.path.basename(image_path)
        response["model_status"] = "image_received_ready_for_model"
    else:
        response["model_status"] = "no_image_received"

    return response, 200
