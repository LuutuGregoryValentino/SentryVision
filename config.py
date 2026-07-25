import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FACIAL_RECOGNITION_ASSET_DIR = os.path.join(BASE_DIR, "app", "facial_recognition_assets")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///sentry_vision.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    FACIAL_RECOGNITION_MODEL_PATH = os.getenv(
        "FACIAL_RECOGNITION_MODEL_PATH",
        os.path.join(FACIAL_RECOGNITION_ASSET_DIR, "model.lite"),
    )
    FACIAL_RECOGNITION_LABELS_PATH = os.getenv(
        "FACIAL_RECOGNITION_LABELS_PATH",
        os.path.join(FACIAL_RECOGNITION_ASSET_DIR, "labels.txt"),
    )
    FACIAL_RECOGNITION_LABELS = os.getenv("FACIAL_RECOGNITION_LABELS")
    FACIAL_RECOGNITION_LABEL_ALIASES = os.getenv("FACIAL_RECOGNITION_LABEL_ALIASES")
