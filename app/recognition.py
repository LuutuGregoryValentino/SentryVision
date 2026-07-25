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
        # Read the actual capture here so every upload is passed through the engine boundary.
        # The checked-in Edge Impulse export is browser WebAssembly and expects numeric
        # features, so it cannot be run directly by this Flask/Python process.
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        if not image_bytes:
            return RecognitionResult(None, 0.0, "empty_image")

        if not self.model_export.is_file():
            return RecognitionResult(None, 0.0, "model_export_missing")

        return RecognitionResult(None, 0.0, "model_runtime_not_configured")
