from datetime import datetime, timezone

from .extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Personnel(db.Model):
    __tablename__ = "personnel"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False)
    authorization_status = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    @property
    def is_authorized(self):
        return self.authorization_status == "Authorized"

    def to_detection_response(self):
        return {
            "name": self.name,
            "role": self.role,
            "authorization_status": self.authorization_status,
            "recognized": True,
        }


class DetectionLog(db.Model):
    __tablename__ = "detection_logs"

    id = db.Column(db.Integer, primary_key=True)
    detected_label = db.Column(db.String(120), nullable=False)
    recognized = db.Column(db.Boolean, nullable=False)
    authorization_status = db.Column(db.String(32), nullable=False)
    alert = db.Column(db.String(255), nullable=True)
    notification_required = db.Column(db.Boolean, default=False, nullable=False)
    personnel_id = db.Column(db.Integer, db.ForeignKey("personnel.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    personnel = db.relationship("Personnel", backref=db.backref("detection_logs", lazy=True))

    def to_dict(self):
        payload = {
            "id": self.id,
            "detected_label": self.detected_label,
            "recognized": self.recognized,
            "authorization_status": self.authorization_status,
            "notification_required": self.notification_required,
            "created_at": self.created_at.isoformat(),
        }
        if self.alert:
            payload["alert"] = self.alert
        if self.personnel:
            payload["personnel"] = {
                "name": self.personnel.name,
                "role": self.personnel.role,
            }
        return payload


class DeviceStatus(db.Model):
    __tablename__ = "device_statuses"

    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="Offline")
    last_ping = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    metric_name = db.Column(db.String(80), nullable=True)
    metric_value = db.Column(db.Float, nullable=True)
    metric_unit = db.Column(db.String(32), nullable=True)
    metadata_json = db.Column(db.JSON, default=dict, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self):
        return {
            "device_name": self.device_name,
            "status": self.status,
            "last_ping": self.last_ping.isoformat(),
            "metric": {
                "name": self.metric_name,
                "value": self.metric_value,
                "unit": self.metric_unit,
            },
            "metadata": self.metadata_json or {},
        }
