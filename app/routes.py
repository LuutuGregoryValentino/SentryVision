from flask import Blueprint, jsonify, request

from .extensions import db
from .models import DetectionLog, DeviceStatus, utc_now
from .schemas import DeviceStatusUpdateSchema, FacialRecognitionSchema
from .services import process_facial_recognition


api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

facial_schema = FacialRecognitionSchema()
device_update_schema = DeviceStatusUpdateSchema()


@api_bp.route("/health/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


@api_bp.route("/facial-recognition/", methods=["POST"])
def facial_recognition():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    payload = facial_schema.load(request.get_json())
    response, status_code = process_facial_recognition(payload["label"])
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
            "logs": [log.to_dict() for log in logs],
        }
    ), 200
