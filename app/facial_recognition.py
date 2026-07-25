import json
import os
from functools import lru_cache


class FacialRecognitionModelError(RuntimeError):
    """Raised when model inference cannot be completed."""


def _load_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise FacialRecognitionModelError(
            "NumPy is required for local facial-recognition inference."
        ) from exc
    return np


def _load_interpreter():
    try:
        from tensorflow.lite import Interpreter

        return Interpreter
    except ImportError:
        pass

    try:
        from tflite_runtime.interpreter import Interpreter

        return Interpreter
    except ImportError as exc:
        raise FacialRecognitionModelError(
            "A TensorFlow Lite interpreter is required for local facial-recognition inference."
        ) from exc


def _load_image_tools():
    try:
        from PIL import Image
    except ImportError as exc:
        raise FacialRecognitionModelError(
            "Pillow is required to run image uploads through the local model."
        ) from exc
    return Image


def _parse_labels(labels_config, labels_path):
    if labels_config:
        if isinstance(labels_config, str):
            return [label.strip() for label in labels_config.split(",") if label.strip()]
        return [str(label).strip() for label in labels_config if str(label).strip()]

    if labels_path and os.path.exists(labels_path):
        with open(labels_path, "r", encoding="utf-8") as labels_file:
            return [line.strip() for line in labels_file if line.strip()]

    return []


@lru_cache(maxsize=4)
def _load_model(model_path):
    if not model_path or not os.path.exists(model_path):
        raise FacialRecognitionModelError(f"Facial-recognition model not found: {model_path}")

    Interpreter = _load_interpreter()
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter


def _details(config):
    interpreter = _load_model(config["model_path"])
    return interpreter, interpreter.get_input_details()[0], interpreter.get_output_details()[0]


def _coerce_features(raw_features):
    if isinstance(raw_features, str):
        raw_features = raw_features.strip()
        if raw_features.startswith("["):
            raw_features = json.loads(raw_features)
        else:
            raw_features = [value.strip() for value in raw_features.split(",") if value.strip()]

    if not isinstance(raw_features, (list, tuple)):
        raise FacialRecognitionModelError("features must be an array or comma-separated string.")

    np = _load_numpy()
    try:
        return np.asarray(raw_features, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise FacialRecognitionModelError("features must contain only numeric values.") from exc


def _prepare_features(raw_features, input_detail):
    np = _load_numpy()
    features = _coerce_features(raw_features)
    input_shape = tuple(int(dim) for dim in input_detail["shape"])
    expected_size = int(np.prod(input_shape))

    if features.size != expected_size:
        raise FacialRecognitionModelError(
            f"Model expects {expected_size} feature values, but received {features.size}."
        )

    return features.reshape(input_shape).astype(input_detail["dtype"])


def _prepare_image(image_path, input_detail):
    np = _load_numpy()
    Image = _load_image_tools()
    input_shape = tuple(int(dim) for dim in input_detail["shape"])

    if len(input_shape) != 4 or input_shape[3] not in (1, 3):
        raise FacialRecognitionModelError(
            "This model expects Edge Impulse features, not raw image pixels. "
            "Send a label, classification payload, or features array."
        )

    _batch, height, width, channels = input_shape
    with Image.open(image_path) as image:
        image = image.convert("L" if channels == 1 else "RGB").resize((width, height))
        image_array = np.asarray(image)

    if channels == 1:
        image_array = image_array[..., np.newaxis]

    model_input = image_array.astype(input_detail["dtype"])
    if input_detail["dtype"] == np.float32:
        model_input = model_input / 255.0

    return model_input.reshape(input_shape)


def _run_model(model_input, config):
    np = _load_numpy()
    interpreter, input_detail, output_detail = _details(config)

    interpreter.set_tensor(input_detail["index"], model_input)
    interpreter.invoke()
    scores = np.asarray(interpreter.get_tensor(output_detail["index"])).reshape(-1)

    labels = config["labels"]
    if not labels:
        labels = [str(index) for index in range(scores.size)]

    top_index = int(scores.argmax())
    label = labels[top_index] if top_index < len(labels) else str(top_index)
    confidence = float(scores[top_index])

    return {
        "label": label,
        "confidence": confidence,
        "scores": {
            labels[index] if index < len(labels) else str(index): float(score)
            for index, score in enumerate(scores)
        },
    }


def build_inference_config(app_config):
    return {
        "model_path": app_config.get("FACIAL_RECOGNITION_MODEL_PATH"),
        "labels": _parse_labels(
            app_config.get("FACIAL_RECOGNITION_LABELS"),
            app_config.get("FACIAL_RECOGNITION_LABELS_PATH"),
        ),
    }


def classify_features(raw_features, app_config):
    config = build_inference_config(app_config)
    _interpreter, input_detail, _output_detail = _details(config)
    return _run_model(_prepare_features(raw_features, input_detail), config)


def classify_image(image_path, app_config):
    config = build_inference_config(app_config)
    _interpreter, input_detail, _output_detail = _details(config)
    return _run_model(_prepare_image(image_path, input_detail), config)
