"""Unit tests for domain entities."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crowd_engine.domain.entities import CameraInput, CrowdEstimate


class TestCameraInput:
    def test_default_camera_id_generated(self):
        cam = CameraInput(source="rtsp://cam1", latitude=18.52, longitude=73.85)
        assert cam.camera_id  # non-empty UUID
        assert len(cam.camera_id) == 36  # UUID4 format

    def test_as_dict_keys(self):
        cam = CameraInput(source="rtsp://cam1", latitude=18.52, longitude=73.85, label="Shop A")
        d = cam.as_dict()
        assert set(d.keys()) == {"camera_id", "source", "latitude", "longitude", "label"}

    def test_custom_camera_id(self):
        cam = CameraInput(source=0, latitude=0.0, longitude=0.0, camera_id="cam-001")
        assert cam.camera_id == "cam-001"


class TestCrowdEstimate:
    def _make(self, **kwargs):
        defaults = dict(
            count=5,
            confidence=0.85,
            timestamp=datetime.now(timezone.utc),
            source="test",
            camera_id="cam-1",
            latitude=18.52,
            longitude=73.85,
        )
        defaults.update(kwargs)
        return CrowdEstimate(**defaults)

    def test_is_valid_success(self):
        est = self._make()
        assert est.is_valid()

    def test_is_valid_with_error(self):
        est = self._make(error="Something went wrong")
        assert not est.is_valid()

    def test_is_valid_negative_count(self):
        est = self._make(count=-1)
        assert not est.is_valid()

    def test_is_valid_confidence_out_of_range(self):
        est = self._make(confidence=1.5)
        assert not est.is_valid()

    def test_as_dict_has_all_keys(self):
        est = self._make()
        d = est.as_dict()
        required = {"count", "confidence", "timestamp", "source", "camera_id",
                    "latitude", "longitude", "metadata", "error"}
        assert required.issubset(d.keys())

    def test_as_dict_timestamp_is_iso(self):
        est = self._make()
        d = est.as_dict()
        # Should parse without error
        datetime.fromisoformat(d["timestamp"])

    def test_error_result_factory(self):
        cam = CameraInput(source="x", latitude=1.0, longitude=2.0)
        est = CrowdEstimate.error_result("provider", cam, "boom")
        assert est.error == "boom"
        assert est.count == 0
        assert not est.is_valid()

    def test_confidence_rounded_in_dict(self):
        est = self._make(confidence=0.123456789)
        d = est.as_dict()
        assert d["confidence"] == round(0.123456789, 4)
