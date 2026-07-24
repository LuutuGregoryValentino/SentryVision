import unittest

from app import create_app


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


if __name__ == "__main__":
    unittest.main()
