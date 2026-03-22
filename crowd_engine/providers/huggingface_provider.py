"""
HuggingFace Provider — local open-source inference using 🤗 Transformers.

Default model: facebook/detr-resnet-50 (DETR — Detection Transformer)
  - Fully open-source (Apache-2.0)
  - No API key required for local inference
  - Supports person detection out of the box (COCO classes)

Optional: set HF_API_KEY to use the Inference API instead of loading the
model locally (useful when GPU/RAM is limited).

Requirements
------------
  pip install transformers torch pillow
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from crowd_engine.domain.entities import CameraInput, CrowdEstimate
from crowd_engine.infra.config import settings
from crowd_engine.infra.logger import get_logger

log = get_logger(__name__)

_HF_INFERENCE_URL = "https://api-inference.huggingface.co/models"
_PERSON_LABELS = {"person", "people"}


class HuggingFaceProvider:
    """
    Crowd estimator using HuggingFace object detection models.

    Runs locally (preferred) or via the HuggingFace Inference API.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        confidence_threshold: float = 0.5,
        timeout: float = 30.0,
        use_api: bool = False,
    ) -> None:
        self._model_name = model_name or settings.huggingface_model
        self._api_key = api_key or settings.huggingface_api_key
        self._threshold = confidence_threshold
        self._timeout = timeout
        self._use_api = use_api or bool(self._api_key and not self._is_local_available())
        self._pipeline: Any = None
        self._last_latency_ms: float = -1.0
        self._available: bool = False

        if not self._use_api:
            self._init_local_pipeline()
        else:
            self._available = bool(self._api_key)

    # ── CrowdCountProvider contract ────────────────────────────────────────

    def name(self) -> str:
        return "huggingface"

    def estimate_crowd(self, camera_input: CameraInput) -> CrowdEstimate:
        if not self._available:
            return CrowdEstimate.error_result(
                self.name(), camera_input, "HuggingFace provider not available (no model or API key)"
            )
        try:
            t0 = time.monotonic()
            if self._use_api:
                results = self._call_api(camera_input.source)
            else:
                results = self._call_local(camera_input.source)
            self._last_latency_ms = (time.monotonic() - t0) * 1000

            persons = [
                r for r in results
                if r.get("label", "").lower() in _PERSON_LABELS
                and r.get("score", 0) >= self._threshold
            ]
            count = len(persons)
            avg_conf = (
                sum(p.get("score", 0) for p in persons) / count if count else 0.0
            )
            log.info(
                "huggingface estimate complete",
                extra={"count": count, "latency_ms": round(self._last_latency_ms, 1)},
            )
            return CrowdEstimate(
                count=count,
                confidence=min(avg_conf, 1.0),
                timestamp=datetime.now(timezone.utc),
                source=self.name(),
                camera_id=camera_input.camera_id,
                latitude=camera_input.latitude,
                longitude=camera_input.longitude,
                metadata={
                    "model": self._model_name,
                    "mode": "api" if self._use_api else "local",
                    "threshold": self._threshold,
                },
            )
        except Exception as exc:
            log.exception("huggingface provider error", exc_info=exc)
            return CrowdEstimate.error_result(self.name(), camera_input, str(exc))

    def health(self) -> dict:
        status = "ok" if self._available else "unavailable"
        mode = "api" if self._use_api else "local"
        return {
            "status": status,
            "latency_ms": self._last_latency_ms,
            "details": f"model={self._model_name} mode={mode}",
        }

    # ── Internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _is_local_available() -> bool:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    def _init_local_pipeline(self) -> None:
        try:
            from transformers import pipeline

            log.info("Loading HuggingFace pipeline: %s (first run may download model)", self._model_name)
            self._pipeline = pipeline(
                "object-detection",
                model=self._model_name,
                device=-1,  # CPU; set device=0 for CUDA
            )
            self._available = True
            log.info("HuggingFace pipeline ready: %s", self._model_name)
        except ImportError:
            log.warning("transformers / torch not installed; HuggingFace provider disabled")
        except Exception as exc:
            log.warning("Failed to load HuggingFace pipeline: %s", exc)

    def _call_local(self, source) -> list:
        from PIL import Image
        import numpy as np

        if isinstance(source, np.ndarray):
            img = Image.fromarray(source)
        elif isinstance(source, (str, bytes)) and str(source).startswith("http"):
            resp = requests.get(str(source), timeout=10)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        else:
            img = Image.open(str(source)).convert("RGB")

        return self._pipeline(img)  # type: ignore[return-value]

    def _call_api(self, source) -> list:
        import numpy as np

        if isinstance(source, np.ndarray):
            import cv2
            _, buf = cv2.imencode(".jpg", source)
            img_bytes = buf.tobytes()
        elif isinstance(source, (str, bytes)) and str(source).startswith("http"):
            resp = requests.get(str(source), timeout=10)
            resp.raise_for_status()
            img_bytes = resp.content
        else:
            with open(str(source), "rb") as fh:
                img_bytes = fh.read()

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        resp = requests.post(
            f"{_HF_INFERENCE_URL}/{self._model_name}",
            headers=headers,
            data=img_bytes,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()
