import unittest

from app import create_app
from app.extensions import db
from app.models import DeviceStatus


class TestTelemetryEndpoint(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            API_KEY = "test-api-key"

        self.app = create_app(TestConfig)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_telemetry_endpoint_accepts_esp_payload(self):
        response = self.client.post(
            "/api/telemetry",
            json={"motion": True, "distance": 12.5, "alarm": True, "servo_angle": 90},
            headers={"X-API-Key": "test-api-key"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_telemetry_endpoint_creates_device_record(self):
        response = self.client.post(
            "/api/telemetry",
            json={
                "device_name": "ESP32-BASE",
                "status": "Online",
                "motion": True,
                "distance": 12.5,
                "alarm": True,
                "servo_angle": 90,
            },
            headers={"X-API-Key": "test-api-key"},
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            device = DeviceStatus.query.filter_by(device_name="ESP32-BASE").first()
            ultrasonic = DeviceStatus.query.filter_by(device_name="Ultrasonic Sensor").first()
            rcwl = DeviceStatus.query.filter_by(device_name="RCWL Sensor").first()
            buzzer = DeviceStatus.query.filter_by(device_name="Buzzer").first()
        self.assertIsNotNone(device)
        self.assertEqual(device.status, "Online")
        self.assertEqual(device.metric_name, "servo_angle")
        self.assertEqual(device.metric_value, 90)
        self.assertEqual(device.metadata_json["motion"], True)
        self.assertEqual(device.metadata_json["alarm"], True)
        self.assertEqual(device.metadata_json["servo_angle"], 90)
        self.assertIsNotNone(ultrasonic)
        self.assertEqual(ultrasonic.metric_name, "distance")
        self.assertEqual(ultrasonic.metric_value, 12.5)
        self.assertIsNotNone(rcwl)
        self.assertEqual(rcwl.metric_name, "motion")
        self.assertEqual(rcwl.metric_value, 1.0)
        self.assertIsNotNone(buzzer)
        self.assertEqual(buzzer.metric_name, "alarm_state")
        self.assertEqual(buzzer.metric_value, 1.0)

    def test_motion_false_updates_rcwl_from_live_payload(self):
        response = self.client.post(
            "/api/telemetry",
            json={"device_name": "ESP32-BASE", "motion": False, "distance": 80.0},
            headers={"X-API-Key": "test-api-key"},
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            device = DeviceStatus.query.filter_by(device_name="ESP32-BASE").first()
            ultrasonic = DeviceStatus.query.filter_by(device_name="Ultrasonic Sensor").first()
            rcwl = DeviceStatus.query.filter_by(device_name="RCWL Sensor").first()
        self.assertIsNotNone(device)
        self.assertEqual(device.metric_name, "distance")
        self.assertEqual(device.metric_value, 80.0)
        self.assertEqual(device.metadata_json["motion"], False)
        self.assertIsNotNone(ultrasonic)
        self.assertEqual(ultrasonic.metric_value, 80.0)
        self.assertIsNotNone(rcwl)
        self.assertEqual(rcwl.metric_name, "motion")
        self.assertEqual(rcwl.metric_value, 0.0)

    def test_device_status_returns_live_records_without_hiding_or_normalizing(self):
        with self.app.app_context():
            db.session.add(DeviceStatus(device_name="Buzzer", status="Online", metric_name="alarm", metric_value=1.0))
            db.session.add(DeviceStatus(device_name="ESP32-BASE", status="Online", metric_name="distance", metric_value=40.0))
            db.session.add(DeviceStatus(device_name="RCWL Sensor", status="Online", metric_name="motion", metric_value=1.0))
            db.session.add(DeviceStatus(device_name="Ultrasonic Sensor", status="Online", metric_name="distance", metric_value=40.0))
            db.session.commit()

        response = self.client.get("/api/v1/device-status/")

        self.assertEqual(response.status_code, 200)
        devices = response.get_json()["devices"]
        device_names = {device["device_name"] for device in devices}
        self.assertIn("Buzzer", device_names)
        self.assertIn("ESP32-BASE", device_names)
        self.assertIn("RCWL Sensor", device_names)
        self.assertIn("Ultrasonic Sensor", device_names)
        esp32 = next(device for device in devices if device["device_name"] == "ESP32-BASE")
        self.assertEqual(esp32["metric"]["name"], "distance")
        self.assertEqual(esp32["metric"]["value"], 40.0)


if __name__ == "__main__":
    unittest.main()
