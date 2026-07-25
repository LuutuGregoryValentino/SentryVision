import io
import unittest

from app import create_app


class TestFacialRecognitionEndpoint(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            API_KEY = "test-api-key"

        self.app = create_app(TestConfig)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_facial_recognition_multipart_upload_creates_log(self):
        response = self.client.post(
            "/api/v1/facial-recognition/",
            data={
                "label": "Unknown",
                "image": (io.BytesIO(b"fake-image-data"), "frame.jpg"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("image_saved", payload)
        self.assertIn("image_url", payload)
        self.assertEqual(payload["recognized"], False)

        logs_response = self.client.get("/api/v1/detection-logs/?limit=1")
        self.assertEqual(logs_response.status_code, 200)
        logs = logs_response.get_json()["logs"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["detected_label"], "Unknown")
        self.assertIn("image_url", logs[0])


if __name__ == "__main__":
    unittest.main()
