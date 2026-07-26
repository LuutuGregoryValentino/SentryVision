"""TensorFlow Lite inference for uploaded facial-recognition images."""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image, UnidentifiedImageError
from tensorflow.lite.python.interpreter import Interpreter


@dataclass(frozen=True)
class RecognitionResult:
    label: str | None
    confidence: float
    model_status: str


class FacialRecognitionEngine:
    """Runs the repository's image-classification TensorFlow Lite model.

    The exported model accepts a single 160 x 160 RGB image with float values in
    the 0-1 range and returns one score for each configured class.
    """

    def __init__(self, model_path: Path, labels: tuple[str, ...], threshold: float):
        self.model_path = model_path
        self.labels = labels
        self.threshold = threshold
        self._interpreter: Interpreter | None = None
        self._lock = Lock()

    def _load_interpreter(self) -> Interpreter:
        if self._interpreter is None:
            if not self.model_path.is_file():
                raise FileNotFoundError(self.model_path)
            interpreter = Interpreter(model_path=str(self.model_path))
            interpreter.allocate_tensors()
            self._interpreter = interpreter
        return self._interpreter

    def recognize(self, image_path: str) -> RecognitionResult:
        try:
            with Image.open(image_path) as image:
                image_data = np.asarray(
                    image.convert("RGB").resize((160, 160), Image.Resampling.LANCZOS),
                    dtype=np.float32,
                ) / 255.0
        except (FileNotFoundError, UnidentifiedImageError, OSError):
            return RecognitionResult(None, 0.0, "invalid_image")

        try:
            # A TFLite Interpreter is not safe for simultaneous invocations.
            with self._lock:
                interpreter = self._load_interpreter()
                input_detail = interpreter.get_input_details()[0]
                output_detail = interpreter.get_output_details()[0]
                interpreter.set_tensor(input_detail["index"], image_data[np.newaxis, ...])
                interpreter.invoke()
                scores = interpreter.get_tensor(output_detail["index"])[0]
        except (FileNotFoundError, ValueError, RuntimeError):
            return RecognitionResult(None, 0.0, "model_unavailable")

        if len(scores) != len(self.labels):
            return RecognitionResult(None, 0.0, "invalid_model_output")

        index = int(np.argmax(scores))
        confidence = float(scores[index]) * 100.0
        label = self.labels[index]
        if confidence < self.threshold or label.casefold() == "unknown":
            return RecognitionResult(None, confidence, "ok")
        return RecognitionResult(label, confidence, "ok")
