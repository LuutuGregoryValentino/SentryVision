from .extensions import db
from .models import DeviceStatus, Personnel


PERSONNEL_SEED = []


DEVICE_SEED = []


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
