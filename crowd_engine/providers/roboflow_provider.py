"""
Roboflow Provider — primary API-based crowd counting.

Uses the Roboflow Inference API (https://roboflow.com) which offers a
generous free tier for custom vision models.

Requirements
------------
  ROBOFLOW_API_KEY env var must be set.
  ROBOFLOW_WORKSPACE / ROBOFLOW_MODEL_ID / ROBOFLOW_MODEL_VERSION configure
  which hosted model to call.

Free-tier note
--------------
  Roboflow offers free-tier inference via their public hosted models.
  The default model IDs point to publicly available person-detection models.
  No credit card is needed for the free tier (as of 2024).
"""

from __future__ import annotations

import base64
import io
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from crowd_engine.domain.entities import CameraInput, CrowdEstimate
from crowd_engine.infra.config import settings
from crowd_engine.infra.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://detect.roboflow.com"


class RoboflowProvider:
    """Crowd estimator backed by the Roboflow Hosted Inference API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace: Optional[str] = None,
        model_id: Optional[str] = None,
        model_version: Optional[int] = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key or settings.roboflow_api_key
        self._workspace = workspace or settings.roboflow_workspace
        self._model_id = model_id or settings.roboflow_model_id
        self._model_version = model_version or settings.roboflow_model_version
        self._timeout = timeout
        self._last_latency_ms: float = -1.0

    # ── CrowdCountProvider contract ────────────────────────────────────────

    def name(self) -> str:
        return "roboflow"

    def estimate_crowd(self, camera_input: CameraInput) -> CrowdEstimate:
        if not self._api_key:
            return CrowdEstimate.error_result(
                self.name(), camera_input, "ROBOFLOW_API_KEY not configured"
            )
        try:
            image_b64 = self._load_image_b64(camera_input.source)
            url = (
                f"{_BASE_URL}/{self._model_id}/{self._model_version}"
                f"?api_key={self._api_key}&confidence=40&overlap=30"
            )
            t0 = time.monotonic()
            resp = requests.post(
                url,
                data=image_b64,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._timeout,
            )
            self._last_latency_ms = (time.monotonic() - t0) * 1000
            resp.raise_for_status()
            payload = resp.json()
            predictions = payload.get("predictions", [])
            count = sum(
                1 for p in predictions if p.get("class", "").lower() == "person"
            )
            avg_conf = (
                sum(p.get("confidence", 0) for p in predictions) / len(predictions)
                if predictions
                else 0.0
            )
            log.info(
                "roboflow estimate complete",
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
                    "model": f"{self._model_id}/{self._model_version}",
                    "raw_predictions": len(predictions),
                },
            )
        except requests.exceptions.Timeout:
            return CrowdEstimate.error_result(
                self.name(), camera_input, "Roboflow API timeout"
            )
        except requests.exceptions.RequestException as exc:
            return CrowdEstimate.error_result(self.name(), camera_input, str(exc))
        except Exception as exc:
            log.exception("roboflow provider error", exc_info=exc)
            return CrowdEstimate.error_result(self.name(), camera_input, str(exc))

    def health(self) -> dict:
        if not self._api_key:
            return {"status": "unavailable", "latency_ms": -1, "details": "API key not configured"}
        try:
            t0 = time.monotonic()
            resp = requests.get(
                f"{_BASE_URL}/{self._model_id}/{self._model_version}",
                params={"api_key": self._api_key},
                timeout=5.0,
            )
            latency = (time.monotonic() - t0) * 1000
            if resp.status_code < 500:
                return {"status": "ok", "latency_ms": latency, "details": f"HTTP {resp.status_code}"}
            return {"status": "degraded", "latency_ms": latency, "details": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "unavailable", "latency_ms": -1, "details": str(exc)}

    # ── Internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _load_image_b64(source) -> str:
        """Convert a source (path, URL, or numpy array) to base64-encoded JPEG."""
        import numpy as np

        if isinstance(source, np.ndarray):
            try:
                import cv2
                _, buf = cv2.imencode(".jpg", source)
                return base64.b64encode(buf.tobytes()).decode("utf-8")
            except ImportError:
                pass
            # Fallback: use PIL
            from PIL import Image
            img = Image.fromarray(source)
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")

        if isinstance(source, (str, bytes)) and str(source).startswith("http"):
            resp = requests.get(str(source), timeout=10)
            resp.raise_for_status()
            return base64.b64encode(resp.content).decode("utf-8")

        # Local file
        with open(source, "rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")
