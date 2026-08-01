import json
import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from urllib import request as urllib_request

from flask import current_app, url_for
from sqlalchemy import func

from .extensions import db
from .models import DetectionLog, DeviceStatus, Personnel, utc_now
from .recognition import FacialRecognitionEngine


UNRECOGNIZED_RESPONSE = {
    "authorization_status": "Unknown",
    "recognized": False,
    "alert": "No face identified",
}


def _get_message_body(message, subtype):
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "text" and part.get_content_subtype() == subtype:
                payload = part.get_payload(decode=True)
                if payload is None:
                    return part.get_payload()
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""

    if message.get_content_type() == f"text/{subtype}":
        payload = message.get_payload(decode=True)
        if payload is None:
            return message.get_payload()
        charset = message.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")

    return ""


def _send_via_sendgrid_api(message, mail_username, mail_password, sender, recipients):
    if not mail_username or not mail_password:
        return False

    url = "https://api.sendgrid.com/v3/mail/send"
    plain_text = _get_message_body(message, "plain")
    html_body = _get_message_body(message, "html")

    payload = {
        "personalizations": [{"to": [{"email": recipient}] for recipient in recipients}],
        "from": {"email": sender},
        "subject": message["Subject"],
        "content": [{"type": "text/plain", "value": plain_text}],
    }
    if html_body:
        payload["content"].append({"type": "text/html", "value": html_body})

    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {mail_password}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=15) as response:
            return response.status in {200, 202}
    except Exception as exc:
        current_app.logger.exception("SendGrid API fallback failed: %s", exc)
        return False


def send_unauthorized_notification(image_path, log):
    if not current_app.config.get("EMAIL_NOTIFICATION_ENABLED", False):
        current_app.logger.info("Email notifications are disabled; skipping unauthorized alert email.")
        return False

    recipients = [value.strip() for value in (current_app.config.get("ADMIN_EMAIL") or "").split(",") if value.strip()]
    if not recipients:
        fallback_sender = current_app.config.get("MAIL_DEFAULT_SENDER")
        if fallback_sender:
            recipients = [value.strip() for value in fallback_sender.split(",") if value.strip()]
        else:
            current_app.logger.warning("No admin email configured for unauthorized detection notifications.")
            return False

    mail_server = current_app.config.get("MAIL_SERVER", "localhost")
    mail_port = int(current_app.config.get("MAIL_PORT", 25))
    mail_use_tls = str(current_app.config.get("MAIL_USE_TLS", False)).lower() in {"1", "true", "yes", "on"}
    mail_username = current_app.config.get("MAIL_USERNAME")
    mail_password = current_app.config.get("MAIL_PASSWORD")
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or mail_username or "noreply@sentryvision.local"

    base_url = (current_app.config.get("PUBLIC_BASE_URL") or "http://localhost").rstrip("/")
    alert_path = f"/api/v1/notifications/{log.id}/alert/"
    ignore_path = f"/api/v1/notifications/{log.id}/ignore/"
    alert_url = f"{base_url}{alert_path}"
    ignore_url = f"{base_url}{ignore_path}"

    subject = "Sentry Vision unauthorized detection"
    text_body = (
        f"A new unauthorized detection was recorded on Sentry Vision.\n\n"
        f"Detected label: {log.detected_label}\n"
        f"Authorization status: {log.authorization_status}\n"
        f"Confidence: {log.confidence if log.confidence is not None else 'n/a'}\n\n"
        f"To alert security now, visit: {alert_url}\n"
        f"To ignore this event, visit: {ignore_url}"
    )
    html_body = f"""<html><body>
        <p>A new unauthorized detection was recorded on Sentry Vision.</p>
        <ul>
            <li><strong>Detected label:</strong> {log.detected_label}</li>
            <li><strong>Authorization status:</strong> {log.authorization_status}</li>
            <li><strong>Confidence:</strong> {log.confidence if log.confidence is not None else 'n/a'}</li>
        </ul>
        <p><a href="{alert_url}">Alert security now</a></p>
        <p><a href="{ignore_url}">Ignore this event</a></p>
    </body></html>"""

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    if image_path and Path(image_path).is_file():
        guess_type, _ = mimetypes.guess_type(image_path)
        if guess_type is None:
            guess_type = "application/octet-stream"
        maintype, subtype = guess_type.split("/", 1)
        with open(image_path, "rb") as handle:
            message.add_attachment(handle.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(image_path))

    try:
        with smtplib.SMTP(mail_server, mail_port) as smtp:
            if mail_use_tls:
                smtp.starttls()
            if mail_username and mail_password:
                smtp.login(mail_username, mail_password)
            smtp.send_message(message)
    except Exception as exc:
        current_app.logger.exception("Failed to send unauthorized detection email via SMTP: %s", exc)
        if mail_username and mail_password:
            if _send_via_sendgrid_api(message, mail_username, mail_password, sender, recipients):
                return True
        return False

    return True


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


def _normalize_device_name(device_name):
    if not device_name:
        return "ESP32-CAM"

    normalized = str(device_name).strip()
    if not normalized:
        return "ESP32-CAM"

    compact = normalized.replace(" ", "").lower()
    if compact in {"esp32cam", "esp32-cam", "esp32", "esp32base", "esp32-base", "esp32-device", "esp32device"}:
        return "ESP32-CAM"
    if compact in {"alarmstatus", "alarm-status", "alarm"}:
        return "Buzzer"
    return normalized


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
    device_name = _normalize_device_name(payload.get("device_name") or payload.get("source") or current_app.config.get("DEFAULT_DEVICE_NAME", "ESP32-CAM"))

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
        send_unauthorized_notification(image_path, log)
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
        if log.notification_required:
            send_unauthorized_notification(image_path, log)
        response = personnel.to_detection_response()

    response["detected_label"] = normalized_label
    response["image_received"] = True
    response["image_saved"] = image_filename or os.path.basename(image_path)
    response["confidence"] = result.confidence
    response["model_status"] = result.model_status
    response["scores"] = result.scores

    return response, 200
