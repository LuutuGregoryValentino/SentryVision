import os
from pathlib import Path


def _load_dotenv_file():
    candidate_paths = []
    project_root = Path(__file__).resolve().parent
    candidate_paths.extend([
        project_root / "app" / ".env",
        project_root / ".env",
        Path.cwd() / ".env",
    ])

    seen_paths = set()
    for env_path in candidate_paths:
        if env_path in seen_paths:
            continue
        seen_paths.add(env_path)
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\'\"")
            if key:
                os.environ[key] = value


_load_dotenv_file()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///sentry_vision.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    API_KEY = os.getenv("API_KEY")
    EMAIL_NOTIFICATION_ENABLED = os.getenv("EMAIL_NOTIFICATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", os.getenv("MAIL_FROM_ADDRESS", "snowchild@gmail.com"))
    MAIL_SERVER = os.getenv("SMTP_HOST", os.getenv("MAIL_SERVER", "smtp.gmail.com"))
    MAIL_PORT = int(os.getenv("SMTP_PORT", os.getenv("MAIL_PORT", "587")))
    MAIL_USE_TLS = os.getenv("SMTP_SECURE", os.getenv("MAIL_USE_TLS", "false")).lower() in {"1", "true", "yes", "on"}
    MAIL_USERNAME = os.getenv("SMTP_USER", os.getenv("MAIL_USERNAME", "apikey"))
    # Prefer explicit MAIL_PASSWORD set in dotenv before falling back to legacy
    # SMTP_PASSWORD or SENDGRID_API_KEY values.
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", os.getenv("SMTP_PASSWORD", os.getenv("SENDGRID_API_KEY")))
    # Prefer explicit MAIL_DEFAULT_SENDER over MAIL_FROM_ADDRESS if provided.
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_FROM_ADDRESS"))
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost")