"""
OpenCV Provider — legacy MobileNetSSD people detector wrapped behind the
CrowdCountProvider interface.

This is the last-resort fallback in the chain.  It requires:
  - opencv-python-headless
  - imutils
  - MobileNetSSD_deploy.prototxt / .caffemodel model files
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

from crowd_engine.domain.entities import CameraInput, CrowdEstimate
from crowd_engine.infra.config import settings
from crowd_engine.infra.logger import get_logger

log = get_logger(__name__)

_CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus",
    "car", "cat", "chair", "cow", "diningtable", "dog", "horse", "motorbike",
    "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor",
]
_PERSON_IDX = _CLASSES.index("person")


class OpenCVProvider:
    """Crowd estimator using OpenCV DNN + MobileNetSSD (caffe model)."""

    def __init__(
        self,
        prototxt: Optional[str] = None,
        caffemodel: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
    ) -> None:
        self._prototxt = prototxt or settings.opencv_prototxt
        self._caffemodel = caffemodel or settings.opencv_caffemodel
        self._threshold = confidence_threshold or settings.opencv_confidence_threshold
        self._net = None
        self._last_latency_ms: float = -1.0
        self._available: bool = False
        self._init_network()

    # ── CrowdCountProvider contract ────────────────────────────────────────

    def name(self) -> str:
        return "opencv"

    def estimate_crowd(self, camera_input: CameraInput) -> CrowdEstimate:
        if not self._available:
            return CrowdEstimate.error_result(
                self.name(), camera_input, "OpenCV model files not loaded"
            )
        try:
            import cv2
            import imutils
            import numpy as np

            t0 = time.monotonic()
            source = camera_input.source

            # Accept a raw numpy frame or a path/URL/device index
            if isinstance(source, np.ndarray):
                frame = source
            else:
                cap = cv2.VideoCapture(source)
                if not cap.isOpened():
                    return CrowdEstimate.error_result(
                        self.name(), camera_input, f"Cannot open source: {source}"
                    )
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    return CrowdEstimate.error_result(
                        self.name(), camera_input, "Failed to grab frame"
                    )

            frame = imutils.resize(frame, width=400)
            (H, W) = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 0.007843, (W, H), 127.5)
            self._net.setInput(blob)
            detections = self._net.forward()

            count = 0
            for i in range(detections.shape[2]):
                conf = detections[0, 0, i, 2]
                if conf > self._threshold:
                    idx = int(detections[0, 0, i, 1])
                    if idx == _PERSON_IDX:
                        count += 1

            self._last_latency_ms = (time.monotonic() - t0) * 1000
            log.info(
                "opencv estimate complete",
                extra={"count": count, "latency_ms": round(self._last_latency_ms, 1)},
            )
            return CrowdEstimate(
                count=count,
                confidence=0.6,  # fixed confidence for degraded mode
                timestamp=datetime.now(timezone.utc),
                source=self.name(),
                camera_id=camera_input.camera_id,
                latitude=camera_input.latitude,
                longitude=camera_input.longitude,
                metadata={"threshold": self._threshold},
            )
        except Exception as exc:
            log.exception("opencv provider error", exc_info=exc)
            return CrowdEstimate.error_result(self.name(), camera_input, str(exc))

    def health(self) -> dict:
        return {
            "status": "ok" if self._available else "unavailable",
            "latency_ms": self._last_latency_ms,
            "details": "MobileNetSSD loaded" if self._available else "Model files missing",
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _init_network(self) -> None:
        try:
            import cv2  # noqa: F401 — verify import first

            if not os.path.isfile(self._prototxt):
                log.warning("OpenCV prototxt not found: %s", self._prototxt)
                return
            if not os.path.isfile(self._caffemodel):
                log.warning("OpenCV caffemodel not found: %s", self._caffemodel)
                return
            import cv2

            self._net = cv2.dnn.readNetFromCaffe(
                prototxt=self._prototxt, caffeModel=self._caffemodel
            )
            self._available = True
            log.info("OpenCV MobileNetSSD loaded successfully")
        except ImportError:
            log.warning("opencv-python-headless not installed; OpenCV provider disabled")
        except Exception as exc:
            log.warning("Failed to load OpenCV model: %s", exc)
