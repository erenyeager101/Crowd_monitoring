"""
Unit tests for provider adapters.

These tests mock external dependencies (OpenCV, HTTP calls, etc.) so they
run without any heavy requirements installed.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from crowd_engine.domain.entities import CameraInput, CrowdEstimate


def _make_camera(**kwargs) -> CameraInput:
    defaults = dict(source="test_image.jpg", latitude=18.52, longitude=73.85)
    defaults.update(kwargs)
    return CameraInput(**defaults)


# ── OpenCV provider ────────────────────────────────────────────────────────

class TestOpenCVProvider:
    def test_health_unavailable_when_model_missing(self, tmp_path):
        from crowd_engine.providers.opencv_provider import OpenCVProvider

        p = OpenCVProvider(
            prototxt=str(tmp_path / "missing.prototxt"),
            caffemodel=str(tmp_path / "missing.caffemodel"),
        )
        h = p.health()
        assert h["status"] == "unavailable"

    def test_estimate_returns_error_when_unavailable(self, tmp_path):
        from crowd_engine.providers.opencv_provider import OpenCVProvider

        p = OpenCVProvider(
            prototxt=str(tmp_path / "missing.prototxt"),
            caffemodel=str(tmp_path / "missing.caffemodel"),
        )
        cam = _make_camera()
        result = p.estimate_crowd(cam)
        assert not result.is_valid()
        assert result.error

    def test_name(self, tmp_path):
        from crowd_engine.providers.opencv_provider import OpenCVProvider

        p = OpenCVProvider(
            prototxt=str(tmp_path / "a.prototxt"),
            caffemodel=str(tmp_path / "a.caffemodel"),
        )
        assert p.name() == "opencv"


# ── Roboflow provider ──────────────────────────────────────────────────────

class TestRoboflowProvider:
    def test_name(self):
        from crowd_engine.providers.roboflow_provider import RoboflowProvider
        p = RoboflowProvider(api_key="dummy")
        assert p.name() == "roboflow"

    def test_estimate_returns_error_without_api_key(self):
        from crowd_engine.providers.roboflow_provider import RoboflowProvider
        p = RoboflowProvider(api_key="")
        result = p.estimate_crowd(_make_camera())
        assert not result.is_valid()
        assert "API_KEY" in (result.error or "")

    @patch("crowd_engine.providers.roboflow_provider.requests.post")
    def test_estimate_counts_persons(self, mock_post):
        from crowd_engine.providers.roboflow_provider import RoboflowProvider

        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "predictions": [
                    {"class": "person", "confidence": 0.9},
                    {"class": "person", "confidence": 0.85},
                    {"class": "car", "confidence": 0.95},
                ]
            },
        )
        mock_post.return_value.raise_for_status = lambda: None

        with patch.object(
            RoboflowProvider, "_load_image_b64", return_value="base64data"
        ):
            p = RoboflowProvider(api_key="test_key")
            cam = _make_camera()
            result = p.estimate_crowd(cam)

        assert result.is_valid()
        assert result.count == 2  # only persons
        assert result.source == "roboflow"

    @patch("crowd_engine.providers.roboflow_provider.requests.post")
    def test_estimate_handles_http_error(self, mock_post):
        from crowd_engine.providers.roboflow_provider import RoboflowProvider
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError("refused")

        with patch.object(
            RoboflowProvider, "_load_image_b64", return_value="base64data"
        ):
            p = RoboflowProvider(api_key="test_key")
            result = p.estimate_crowd(_make_camera())

        assert not result.is_valid()
        assert result.error


# ── HuggingFace provider ───────────────────────────────────────────────────

class TestHuggingFaceProvider:
    def test_name(self):
        from crowd_engine.providers.huggingface_provider import HuggingFaceProvider
        p = HuggingFaceProvider.__new__(HuggingFaceProvider)
        p._model_name = "facebook/detr-resnet-50"
        assert p.name() == "huggingface"

    def test_estimate_unavailable_without_model(self):
        from crowd_engine.providers.huggingface_provider import HuggingFaceProvider

        p = HuggingFaceProvider.__new__(HuggingFaceProvider)
        p._available = False
        p._use_api = False
        p._pipeline = None
        p._model_name = "test"
        p._api_key = None
        p._threshold = 0.5
        p._timeout = 10.0
        p._last_latency_ms = -1.0
        result = p.estimate_crowd(_make_camera())
        assert not result.is_valid()


# ── Geospatial provider ────────────────────────────────────────────────────

class TestGeospatialProvider:
    def test_name(self):
        from crowd_engine.providers.geospatial_provider import GeospatialProvider
        p = GeospatialProvider()
        assert p.name() == "geospatial"

    @patch("crowd_engine.providers.geospatial_provider.requests.get")
    def test_estimate_returns_low_confidence(self, mock_get):
        from crowd_engine.providers.geospatial_provider import GeospatialProvider

        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "display_name": "Pune, Maharashtra, India",
                "type": "market",
                "class": "place",
                "address": {},
            },
        )
        mock_get.return_value.raise_for_status = lambda: None

        p = GeospatialProvider()
        result = p.estimate_crowd(_make_camera())

        assert result.is_valid()
        assert result.confidence <= 0.35  # capped low
        assert result.source == "geospatial"
        assert "Low-confidence" in result.metadata.get("note", "")

    @patch("crowd_engine.providers.geospatial_provider.requests.get")
    def test_estimate_handles_network_error(self, mock_get):
        from crowd_engine.providers.geospatial_provider import GeospatialProvider
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("no network")
        p = GeospatialProvider()
        result = p.estimate_crowd(_make_camera())
        assert not result.is_valid()

    def test_popularity_score_range(self):
        from crowd_engine.providers.geospatial_provider import GeospatialProvider

        p = GeospatialProvider()
        for dow in range(7):
            for hour in range(24):
                score = p._popularity_score("mall", dow, hour)
                assert 0.0 <= score <= 1.0, f"Score out of range: {score}"
