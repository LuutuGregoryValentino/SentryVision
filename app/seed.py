from .extensions import db
from .models import DeviceStatus, Personnel


PERSONNEL_SEED = [
    {
        "label": "Kessie",
        "name": "Kessie",
        "role": "Administrator/Engineer",
        "authorization_status": "Authorized",
    },
    {
        "label": "Anold",
        "name": "Anold",
        "role": "Administrator/Engineer",
        "authorization_status": "Authorized",
    },
    {
        "label": "Faith",
        "name": "Faith",
        "role": "Visitor/Staff",
        "authorization_status": "Unauthorized",
    },
    {
        "label": "Misha",
        "name": "Misha",
        "role": "Visitor/Staff",
        "authorization_status": "Unauthorized",
    },
]


DEVICE_SEED = [
    {
        "device_name": "ESP32-CAM",
        "status": "Online",
        "metric_name": "inference_latency",
        "metric_value": 0.0,
        "metric_unit": "ms",
        "metadata_json": {"camera": "ready", "model": "Edge Impulse facial recognition"},
    },
    {
        "device_name": "Ultrasonic Sensor",
        "status": "Online",
        "metric_name": "distance",
        "metric_value": 0.0,
        "metric_unit": "cm",
        "metadata_json": {"purpose": "proximity detection"},
    },
    {
        "device_name": "Buzzer",
        "status": "Offline",
        "metric_name": "alarm_state",
        "metric_value": 0.0,
        "metric_unit": "binary",
        "metadata_json": {"purpose": "audible alert"},
    },
    {
        "device_name": "RCWL Sensor",
        "status": "Online",
        "metric_name": "motion",
        "metric_value": 0.0,
        "metric_unit": "binary",
        "metadata_json": {"sensor_type": "microwave radar"},
    },
]


def seed_database():
    for record in PERSONNEL_SEED:
        person = Personnel.query.filter_by(label=record["label"]).first()
        if person is None:
            db.session.add(Personnel(**record))
        else:
            person.name = record["name"]
            person.role = record["role"]
            person.authorization_status = record["authorization_status"]

    for record in DEVICE_SEED:
        device = DeviceStatus.query.filter_by(device_name=record["device_name"]).first()
        if device is None:
            db.session.add(DeviceStatus(**record))
        else:
            device.status = record["status"]
            device.metric_name = record["metric_name"]
            device.metric_value = record["metric_value"]
            device.metric_unit = record["metric_unit"]
            device.metadata_json = record["metadata_json"]

    db.session.commit()
