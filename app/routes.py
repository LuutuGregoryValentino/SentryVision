import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from .extensions import db
from .models import DetectionLog, DeviceStatus, utc_now
from .schemas import DeviceStatusUpdateSchema, FacialRecognitionSchema
from .services import process_facial_recognition


def _require_api_key():
    expected_key = current_app.config.get("API_KEY")
    provided_key = request.headers.get("X-API-Key")
    if expected_key and provided_key != expected_key:
        return False
    return True


api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
telemetry_bp = Blueprint("telemetry", __name__, url_prefix="/api")

facial_schema = FacialRecognitionSchema()
device_update_schema = DeviceStatusUpdateSchema()


def save_uploaded_image(file_storage):
    if file_storage is None or file_storage.filename == "":
        return None

    upload_dir = os.path.join(current_app.instance_path, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    filename = secure_filename(file_storage.filename)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    filename = f"{timestamp}_{filename}"
    destination = os.path.join(upload_dir, filename)
    file_storage.save(destination)
    return destination


# ==========================================
#  NEW ROUTE: SERVE UPLOADED IMAGES TO FRONTEND
# ==========================================
@api_bp.route("/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    """Serves captured images stored in instance/uploads to the frontend."""
    upload_dir = os.path.join(current_app.instance_path, "uploads")
    return send_from_directory(upload_dir, filename)


@api_bp.route("/health/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


@telemetry_bp.route("/telemetry", methods=["POST"])
def telemetry():
    if not _require_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    return jsonify({
        "status": "ok",
        "motion": payload.get("motion", False),
        "distance": payload.get("distance"),
        "alarm": payload.get("alarm", False),
        "servo_angle": payload.get("servo_angle"),
    }), 200


@api_bp.route("/facial-recognition/", methods=["POST"])
def facial_recognition():
    # Enforce API Key
    if not _require_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    request_content_type = request.content_type or ""
    saved_image_name = None
    saved_image_path = None

    if request_content_type.startswith("multipart/form-data"):
        if "image" not in request.files:
            return jsonify({"error": "Multipart request must include an image file under the 'image' field."}), 415

        saved_image_path = save_uploaded_image(request.files["image"])
        if saved_image_path:
            saved_image_name = os.path.basename(saved_image_path)

        form_data = request.form.to_dict()
        if "detected_label" in form_data and "label" not in form_data:
            form_data["label"] = form_data["detected_label"]

        payload = facial_schema.load(form_data)
    else:
        return jsonify({"error": "Content-Type must be multipart/form-data with an image file."}), 415

    # Process the saved image with the recognition engine and return a preview URL for the frontend.
    response, status_code = process_facial_recognition(saved_image_path, image_filename=saved_image_name)

    # Attach a frontend-safe URL for previewing the captured image
    if saved_image_name:
        response = {
            **response,
            "image_saved": saved_image_name,
            "image_url": url_for("api.serve_upload", filename=saved_image_name),
        }

    return jsonify(response), status_code


@api_bp.route("/device-status/", methods=["GET"])
def get_device_statuses():
    devices = DeviceStatus.query.order_by(DeviceStatus.device_name.asc()).all()
    return jsonify(
        {
            "count": len(devices),
            "devices": [device.to_dict() for device in devices],
        }
    ), 200


@api_bp.route("/device-status/<string:device_name>/", methods=["PATCH"])
def update_device_status(device_name):
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    device = DeviceStatus.query.filter_by(device_name=device_name).first()
    if device is None:
        return jsonify({"error": "Device not found", "device_name": device_name}), 404

    payload = device_update_schema.load(request.get_json())
    device.status = payload["status"]
    device.last_ping = utc_now()
    device.metric_name = payload["metric_name"]
    device.metric_value = payload["metric_value"]
    device.metric_unit = payload["metric_unit"]
    device.metadata_json = payload["metadata"]
    db.session.commit()

    return jsonify(device.to_dict()), 200


@api_bp.route("/detection-logs/", methods=["GET"])
def get_detection_logs():
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit, 200))
    logs = DetectionLog.query.order_by(DetectionLog.created_at.desc()).limit(limit).all()
    return jsonify(
        {
            "count": len(logs),
            "logs": [
                {
                    **log.to_dict(),
                    **(
                        {"image_url": f"/api/v1/uploads/{log.image_filename}"}
                        if log.image_filename
                        else {}
                    ),
                }
                for log in logs
            ],
        }
    ), 200