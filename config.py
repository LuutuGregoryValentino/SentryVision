import os
from pathlib import Path


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///sentry_vision.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    FACIAL_MODEL_PATH = Path(__file__).parent / "FacialModelForSentryVision.4.lite"
    # TFLite stores six scores but no human-readable class labels. This mapping
    # follows the project's expected training-label order; verify it against the
    # training dataset whenever the model is replaced.
    FACIAL_MODEL_LABELS = ("Anold", "Faith", "Kessie", "Luutu", "Misha", "Unknown")
    FACIAL_RECOGNITION_THRESHOLD = 75.0
