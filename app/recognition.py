"""The small boundary between Flask and the facial-recognition model runtime."""

import json
import os
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RecognitionResult:
    label: str | None
    confidence: float
    model_status: str
    scores: dict[str, float] = field(default_factory=dict)


class FacialRecognitionEngine:
    """Runs the bundled Edge Impulse browser export against uploaded images."""

    IMAGE_WIDTH = 160
    IMAGE_HEIGHT = 160
    RESULT_MARKER = "@@SENTRY_VISION_RESULT@@"

    def __init__(self, model_export: Path, node_binary: str | None = None):
        self.model_export = model_export
        self.node_binary = node_binary or os.getenv("NODE_BINARY", "node")

    def recognize(self, image_path: str) -> RecognitionResult:
        image_file_path = Path(image_path)
        if not image_file_path.is_file():
            return RecognitionResult(None, 0.0, "image_missing")

        if image_file_path.stat().st_size == 0:
            return RecognitionResult(None, 0.0, "empty_image")

        browser_dir = self._browser_runtime_dir()
        if browser_dir is None:
            return RecognitionResult(None, 0.0, "model_export_missing")

        try:
            features = self._image_to_features(image_file_path)
        except ImportError:
            return RecognitionResult(None, 0.0, "pillow_not_installed")
        except OSError:
            return RecognitionResult(None, 0.0, "invalid_image")

        runner = Path(__file__).with_name("edge_impulse_runner.js")
        if not runner.is_file():
            return RecognitionResult(None, 0.0, "model_runner_missing")

        try:
            payload = self._run_classifier(browser_dir, runner, features)
        except FileNotFoundError:
            return RecognitionResult(None, 0.0, "node_runtime_not_available")
        except subprocess.TimeoutExpired:
            return RecognitionResult(None, 0.0, "model_runtime_timeout")
        except (json.JSONDecodeError, RuntimeError):
            return RecognitionResult(None, 0.0, "model_runtime_error")

        results = payload.get("result", {}).get("results", [])
        if not results:
            return RecognitionResult(None, 0.0, "no_classification")

        top_result = max(results, key=lambda item: item.get("value", 0.0))
        raw_label = str(top_result.get("label") or "").strip()
        raw_confidence = float(top_result.get("value") or 0.0)
        confidence = raw_confidence * 100
        scores = {
            str(item.get("label")): round(float(item.get("value") or 0.0) * 100, 2)
            for item in results
            if item.get("label")
        }

        threshold = float(payload.get("properties", {}).get("classification_threshold") or 0.6)
        if raw_label.lower() == "unknown":
            return RecognitionResult(None, confidence, "unknown_class", scores)

        if raw_confidence < threshold:
            return RecognitionResult(None, confidence, "low_confidence", scores)

        return RecognitionResult(raw_label, confidence, "matched", scores)

    def _browser_runtime_dir(self) -> Path | None:
        if self.model_export.is_dir():
            browser_dir = self.model_export / "browser"
            return browser_dir if browser_dir.is_dir() else self.model_export

        if not self.model_export.is_file():
            return None

        cache_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.model_export.stem)
        cache_dir = Path(tempfile.gettempdir()) / "sentry_vision_edge_impulse" / cache_name
        required_files = [
            cache_dir / "edge-impulse-standalone.js",
            cache_dir / "edge-impulse-standalone.wasm",
            cache_dir / "run-impulse.js",
        ]
        if all(path.is_file() for path in required_files):
            return cache_dir

        cache_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.model_export) as archive:
            for filename in ("edge-impulse-standalone.js", "edge-impulse-standalone.wasm", "run-impulse.js"):
                archive_member = f"browser/{filename}"
                with archive.open(archive_member) as source, open(cache_dir / filename, "wb") as destination:
                    destination.write(source.read())

        return cache_dir

    def _image_to_features(self, image_path: Path) -> list[int]:
        from PIL import Image, ImageOps

        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB").resize((self.IMAGE_WIDTH, self.IMAGE_HEIGHT), Image.Resampling.BILINEAR)
            return [(red << 16) + (green << 8) + blue for red, green, blue in image.getdata()]

    def _run_classifier(self, browser_dir: Path, runner: Path, features: list[int]) -> dict:
        features_path = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as features_file:
                json.dump(features, features_file, separators=(",", ":"))
                features_path = features_file.name

            completed = subprocess.run(
                [self.node_binary, str(runner), str(browser_dir), features_path],
                cwd=str(browser_dir),
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
        finally:
            if features_path:
                Path(features_path).unlink(missing_ok=True)

        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        if completed.returncode != 0:
            raise RuntimeError(output)

        for line in output.splitlines():
            if line.startswith(self.RESULT_MARKER):
                return json.loads(line[len(self.RESULT_MARKER):])

        raise RuntimeError(output)
