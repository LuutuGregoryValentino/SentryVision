import unittest

from app import create_app
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
            ultrasonic = DeviceStatus.query.filter_by(device_name="Ultrasonic Sensor").first()
            rcwl = DeviceStatus.query.filter_by(device_name="RCWL Sensor").first()
        self.assertIsNotNone(ultrasonic)
        self.assertEqual(ultrasonic.status, "Online")
        self.assertEqual(ultrasonic.metric_name, "distance")
        self.assertEqual(ultrasonic.metric_value, 12.5)
        self.assertIsNotNone(rcwl)
        self.assertEqual(rcwl.metric_name, "presence")
        self.assertEqual(rcwl.metric_value, 1.0)

    def test_rcwl_presence_records_zero_when_motion_is_false(self):
        response = self.client.post(
            "/api/telemetry",
            json={"device_name": "ESP32-BASE", "motion": False, "distance": 80.0},
            headers={"X-API-Key": "test-api-key"},
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            rcwl = DeviceStatus.query.filter_by(device_name="RCWL Sensor").first()
        self.assertIsNotNone(rcwl)
        self.assertEqual(rcwl.metric_name, "presence")
        self.assertEqual(rcwl.metric_value, 0.0)


if __name__ == "__main__":
    unittest.main()
