from .extensions import db
from .models import DetectionLog, Personnel


UNRECOGNIZED_RESPONSE = {
    "authorization_status": "Unauthorized",
    "recognized": False,
    "alert": "Unrecognized face detected",
}


def process_facial_recognition(label):
    normalized_label = (label or "").strip()
    if not normalized_label:
        return {
            "authorization_status": "Unauthorized",
            "recognized": False,
            "alert": "No face label provided",
        }, 200

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
        return dict(UNRECOGNIZED_RESPONSE), 200

    log = DetectionLog(
        detected_label=normalized_label,
        recognized=True,
        authorization_status=personnel.authorization_status,
        notification_required=not personnel.is_authorized,
        personnel=personnel,
    )
    db.session.add(log)
    db.session.commit()

    return personnel.to_detection_response(), 200
