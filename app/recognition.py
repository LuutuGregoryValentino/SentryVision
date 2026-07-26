"""The small boundary between Flask and the facial-recognition model runtime."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecognitionResult:
    label: str | None
    confidence: float
    model_status: str


class FacialRecognitionEngine:
    """Receives capture bytes before a server-compatible model runtime is installed."""

    def __init__(self, model_export: Path):
        self.model_export = model_export

    def recognize(self, image_path: str) -> RecognitionResult:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        if not image_bytes:
            return RecognitionResult(None, 0.0, "empty_image")

        if not self.model_export.is_file():
            return RecognitionResult(None, 0.0, "image_received_ready_for_model")

        return RecognitionResult(None, 0.0, "image_received_ready_for_model")
