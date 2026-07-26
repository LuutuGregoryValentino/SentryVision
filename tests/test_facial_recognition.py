import io
import unittest
from unittest.mock import patch

from app import create_app
from app.recognition import RecognitionResult


TINY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4"
    b"\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda"
    b"\x00\x08\x01\x01\x00\x00?\x00?\xff\xd9"
)


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

    @patch("app.services.FacialRecognitionEngine.recognize")
    def test_facial_recognition_multipart_upload_uses_model_label(self, recognize):
        recognize.return_value = RecognitionResult("kessie", 91.4, "matched", {"kessie": 91.4})

        response = self.client.post(
            "/api/v1/facial-recognition/",
            data={
                "label": "Unknown",
                "image": (io.BytesIO(TINY_JPEG), "frame.jpg"),
            },
            content_type="multipart/form-data",
            headers={"X-API-Key": self.app.config["API_KEY"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("image_saved", payload)
        self.assertIn("image_url", payload)
        self.assertEqual(payload["recognized"], True)
        self.assertEqual(payload["name"], "Kessie")
        self.assertEqual(payload["detected_label"], "Kessie")
        self.assertEqual(payload["image_received"], True)
        self.assertEqual(payload["model_status"], "matched")

        logs_response = self.client.get("/api/v1/detection-logs/?limit=1")
        self.assertEqual(logs_response.status_code, 200)
        logs = logs_response.get_json()["logs"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["detected_label"], "Kessie")
        self.assertEqual(logs[0]["recognized"], True)
        self.assertIn("image_url", logs[0])

    @patch("app.services.FacialRecognitionEngine.recognize")
    def test_dashboard_upload_can_use_same_origin_request_without_api_key(self, recognize):
        recognize.return_value = RecognitionResult("faith", 88.0, "matched", {"faith": 88.0})

        response = self.client.post(
            "/api/v1/facial-recognition/",
            data={"image": (io.BytesIO(TINY_JPEG), "frame.jpg")},
            content_type="multipart/form-data",
            headers={"Referer": "http://localhost/"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["recognized"], True)
        self.assertEqual(payload["detected_label"], "Faith")


if __name__ == "__main__":
    unittest.main()
