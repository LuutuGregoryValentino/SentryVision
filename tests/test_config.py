import importlib
import os
from pathlib import Path
import unittest


class ConfigEnvLoadingTests(unittest.TestCase):
    def test_config_reads_dotenv_values_and_admin_email_override(self):
        repo_root = Path(__file__).resolve().parents[1]
        env_path = repo_root / ".env"
        original_content = env_path.read_text(encoding="utf-8") if env_path.exists() else None

        try:
            for key in ["ADMIN_EMAIL", "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER", "EMAIL_NOTIFICATION_ENABLED"]:
                os.environ.pop(key, None)

            env_path.write_text(
                "ADMIN_EMAIL=alerts@example.com\n"
                "MAIL_PASSWORD=sendgrid-secret\n"
                "MAIL_DEFAULT_SENDER=alerts@example.com\n"
                "EMAIL_NOTIFICATION_ENABLED=true\n",
                encoding="utf-8",
            )

            import config

            reloaded = importlib.reload(config)
            self.assertEqual(reloaded.Config.ADMIN_EMAIL, "alerts@example.com")
            self.assertEqual(reloaded.Config.MAIL_PASSWORD, "sendgrid-secret")
            self.assertEqual(reloaded.Config.MAIL_DEFAULT_SENDER, "alerts@example.com")
            self.assertTrue(reloaded.Config.EMAIL_NOTIFICATION_ENABLED)
        finally:
            if original_content is None:
                env_path.unlink(missing_ok=True)
            else:
                env_path.write_text(original_content, encoding="utf-8")

            import config

            importlib.reload(config)

    def test_config_reads_dotenv_from_app_directory(self):
        repo_root = Path(__file__).resolve().parents[1]
        app_env_path = repo_root / "app" / ".env"
        original_content = app_env_path.read_text(encoding="utf-8") if app_env_path.exists() else None

        try:
            for key in ["ADMIN_EMAIL", "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER", "EMAIL_NOTIFICATION_ENABLED"]:
                os.environ.pop(key, None)

            app_env_path.write_text(
                "ADMIN_EMAIL=alerts@example.com\n"
                "MAIL_PASSWORD=sendgrid-secret\n"
                "MAIL_DEFAULT_SENDER=alerts@example.com\n"
                "EMAIL_NOTIFICATION_ENABLED=true\n",
                encoding="utf-8",
            )

            import config

            reloaded = importlib.reload(config)
            self.assertEqual(reloaded.Config.ADMIN_EMAIL, "alerts@example.com")
            self.assertEqual(reloaded.Config.MAIL_PASSWORD, "sendgrid-secret")
            self.assertEqual(reloaded.Config.MAIL_DEFAULT_SENDER, "alerts@example.com")
            self.assertTrue(reloaded.Config.EMAIL_NOTIFICATION_ENABLED)
        finally:
            if original_content is None:
                app_env_path.unlink(missing_ok=True)
            else:
                app_env_path.write_text(original_content, encoding="utf-8")

            import config

            importlib.reload(config)

    def test_dotenv_values_override_existing_environment_variables(self):
        repo_root = Path(__file__).resolve().parents[1]
        app_env_path = repo_root / "app" / ".env"
        original_content = app_env_path.read_text(encoding="utf-8") if app_env_path.exists() else None

        try:
            os.environ["MAIL_DEFAULT_SENDER"] = "shell@example.com"
            app_env_path.write_text("MAIL_DEFAULT_SENDER=dotenv@example.com\n", encoding="utf-8")

            import config

            reloaded = importlib.reload(config)
            self.assertEqual(reloaded.Config.MAIL_DEFAULT_SENDER, "dotenv@example.com")
        finally:
            if original_content is None:
                app_env_path.unlink(missing_ok=True)
            else:
                app_env_path.write_text(original_content, encoding="utf-8")

            os.environ.pop("MAIL_DEFAULT_SENDER", None)
            import config

            importlib.reload(config)
