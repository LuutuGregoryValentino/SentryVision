import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import socket

from app import create_app
from app.recognition import RecognitionResult
from app.services import send_unauthorized_notification


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

    @patch("app.services.send_unauthorized_notification")
    @patch("app.services.FacialRecognitionEngine.recognize")
    def test_unauthorized_detection_sends_email_notification(self, recognize, send_notification):
        recognize.return_value = RecognitionResult(None, 64.5, "unknown_class", {"unknown": 64.5})

        response = self.client.post(
            "/api/v1/facial-recognition/",
            data={"image": (io.BytesIO(TINY_JPEG), "frame.jpg")},
            content_type="multipart/form-data",
            headers={"X-API-Key": self.app.config["API_KEY"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["recognized"], False)
        self.assertEqual(payload["authorization_status"], "Unknown")
        send_notification.assert_called_once()

    @patch("app.services.smtplib.SMTP")
    def test_send_unauthorized_notification_works_outside_request_context(self, smtp_cls):
        smtp_instance = smtp_cls.return_value.__enter__.return_value
        self.app.config.update(
            EMAIL_NOTIFICATION_ENABLED=True,
            ADMIN_EMAIL="snowchild@gmail.com",
            MAIL_SERVER="smtp.gmail.com",
            MAIL_PORT=587,
            MAIL_USE_TLS=False,
            MAIL_USERNAME="smtp-user",
            MAIL_PASSWORD="smtp-password",
            MAIL_DEFAULT_SENDER="no-reply@example.com",
            PUBLIC_BASE_URL="http://localhost:5000",
        )

        with self.app.app_context():
            log = SimpleNamespace(id=123, detected_label="Unknown", authorization_status="Unknown", confidence=63.2)
            result = send_unauthorized_notification("instance/uploads/20260730164103106280_frame.jpg", log)

        self.assertTrue(result)
        smtp_instance.send_message.assert_called_once()

    @patch("app.services._send_via_sendgrid_api")
    @patch("app.services.smtplib.SMTP")
    def test_send_unauthorized_notification_falls_back_to_sendgrid_api(self, smtp_cls, api_sender):
        smtp_cls.side_effect = socket.gaierror("dns failure")
        api_sender.return_value = True
        self.app.config.update(
            EMAIL_NOTIFICATION_ENABLED=True,
            ADMIN_EMAIL="alerts@example.com",
            MAIL_SERVER="smtp.sendgrid.net",
            MAIL_PORT=587,
            MAIL_USE_TLS=True,
            MAIL_USERNAME="apikey",
            MAIL_PASSWORD="smtp-password",
            MAIL_DEFAULT_SENDER="alerts@example.com",
            PUBLIC_BASE_URL="http://localhost:5000",
        )

        with self.app.app_context():
            log = SimpleNamespace(id=789, detected_label="Unknown", authorization_status="Unknown", confidence=61.4)
            result = send_unauthorized_notification("instance/uploads/20260730164103106280_frame.jpg", log)

        self.assertTrue(result)
        api_sender.assert_called_once()

    @patch("app.services.smtplib.SMTP")
    def test_send_unauthorized_notification_uses_default_sender_as_fallback_recipient(self, smtp_cls):
        smtp_instance = smtp_cls.return_value.__enter__.return_value
        self.app.config.update(
            EMAIL_NOTIFICATION_ENABLED=True,
            ADMIN_EMAIL="",
            MAIL_SERVER="smtp.sendgrid.net",
            MAIL_PORT=587,
            MAIL_USE_TLS=True,
            MAIL_USERNAME="apikey",
            MAIL_PASSWORD="smtp-password",
            MAIL_DEFAULT_SENDER="alerts@example.com",
            PUBLIC_BASE_URL="http://localhost:5000",
        )

        with self.app.app_context():
            log = SimpleNamespace(id=456, detected_label="Unknown", authorization_status="Unknown", confidence=61.4)
            result = send_unauthorized_notification("instance/uploads/20260730164103106280_frame.jpg", log)

        self.assertTrue(result)
        sent_message = smtp_instance.send_message.call_args[0][0]
        self.assertEqual(sent_message["To"], "alerts@example.com")


if __name__ == "__main__":
    unittest.main()
