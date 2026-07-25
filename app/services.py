import json

from flask import current_app, has_app_context

from .extensions import db
from .models import DetectionLog, Personnel


UNRECOGNIZED_RESPONSE = {
    "authorization_status": "Unauthorized",
    "recognized": False,
    "alert": "Unrecognized face detected",
}


DEFAULT_LABEL_ALIASES = {
    "greg": "Luutu",
}


def _configured_label_aliases():
    aliases = dict(DEFAULT_LABEL_ALIASES)

    if not has_app_context():
        return aliases

    configured_aliases = current_app.config.get("FACIAL_RECOGNITION_LABEL_ALIASES") or {}
    if isinstance(configured_aliases, str):
        try:
            configured_aliases = json.loads(configured_aliases)
        except json.JSONDecodeError:
            configured_aliases = {}

    aliases.update(configured_aliases)
    return {str(key).lower(): str(value) for key, value in aliases.items()}


def normalize_label(label):
    normalized_label = " ".join(label.strip().split())
    return _configured_label_aliases().get(normalized_label.lower(), normalized_label)


def normalize_output_label(label):
    return normalize_label(label)


def process_facial_recognition(label):
    normalized_label = normalize_label(label)
    personnel = Personnel.query.filter(db.func.lower(Personnel.label) == normalized_label.lower()).first()

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
        detected_label=personnel.label,
        recognized=True,
        authorization_status=personnel.authorization_status,
        notification_required=not personnel.is_authorized,
        personnel=personnel,
    )
    db.session.add(log)
    db.session.commit()

    return personnel.to_detection_response(), 200
