import io
import unittest

from PIL import Image

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

    @staticmethod
    def _image_file():
        image = Image.new("RGB", (160, 160), color="white")
        data = io.BytesIO()
        image.save(data, format="JPEG")
        data.seek(0)
        return data

    def test_facial_recognition_multipart_upload_creates_log(self):
        response = self.client.post(
            "/api/v1/facial-recognition/",
            data={
                # Labels submitted by a client are deliberately ignored: the
                # backend derives identity only from the uploaded image.
                "label": "Kessie",
                "image": (self._image_file(), "frame.jpg"),
            },
            content_type="multipart/form-data",
            headers={"X-API-Key": self.app.config["API_KEY"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("image_saved", payload)
        self.assertIn("image_url", payload)
        self.assertEqual(payload["recognized"], False)
        self.assertEqual(payload["image_received"], True)
        self.assertEqual(payload["model_status"], "ok")

        logs_response = self.client.get("/api/v1/detection-logs/?limit=1")
        self.assertEqual(logs_response.status_code, 200)
        logs = logs_response.get_json()["logs"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["detected_label"], payload["detected_label"])
        self.assertNotIn("image_url", logs[0])


if __name__ == "__main__":
    unittest.main()
