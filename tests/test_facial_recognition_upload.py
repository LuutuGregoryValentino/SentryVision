import io
import os
import unittest

from app import create_app


class FacialRecognitionUploadTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_multipart_upload_returns_image_metadata(self):
        response = self.client.post(
            "/api/v1/facial-recognition/",
            data={
                "label": "Kessie",
                "image": (io.BytesIO(b"fake-image-data"), "sample.jpg"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["recognized"])
        self.assertTrue(payload["image_received"])
        self.assertIn("image_saved", payload)

        upload_dir = os.path.join(self.app.instance_path, "uploads")
        self.assertTrue(os.path.isdir(upload_dir))
        self.assertTrue(any(name.endswith(".jpg") for name in os.listdir(upload_dir)))


if __name__ == "__main__":
    unittest.main()
