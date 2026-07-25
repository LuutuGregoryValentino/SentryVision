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

    def test_edge_impulse_classification_payload_uses_top_label(self):
        response = self.client.post(
            "/api/v1/facial-recognition/",
            json={"classification": {"kessie": 0.92, "unknown": 0.08}},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["recognized"])
        self.assertEqual(payload["name"], "Kessie")

    def test_known_faces_are_recognized_case_insensitively(self):
        test_cases = [
            ("kEssie", "Kessie", "Authorized"),
            ("anold", "Anold", "Authorized"),
            ("faith", "Faith", "Unauthorized"),
            ("misha", "Misha", "Unauthorized"),
            ("luutu", "Luutu", "Unauthorized"),
        ]

        for label, expected_name, expected_status in test_cases:
            with self.subTest(label=label):
                response = self.client.post(
                    "/api/v1/facial-recognition/",
                    json={"label": label},
                )

                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertTrue(payload["recognized"])
                self.assertEqual(payload["name"], expected_name)
                self.assertEqual(payload["authorization_status"], expected_status)

    def test_model_greg_label_maps_to_luutu(self):
        response = self.client.post(
            "/api/v1/facial-recognition/",
            json={"classification": {"greg": 0.95, "unknown": 0.05}},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["recognized"])
        self.assertEqual(payload["name"], "Luutu")


if __name__ == "__main__":
    unittest.main()
