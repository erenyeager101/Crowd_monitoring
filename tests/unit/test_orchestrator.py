"""Unit tests for the FallbackOrchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

import pytest

from crowd_engine.domain.entities import CameraInput, CrowdEstimate
from crowd_engine.services.orchestrator import FallbackOrchestrator


# ── Test helpers ───────────────────────────────────────────────────────────

def _make_camera() -> CameraInput:
    return CameraInput(source="rtsp://test", latitude=18.52, longitude=73.85)


def _good_estimate(source: str, count: int = 5) -> CrowdEstimate:
    return CrowdEstimate(
        count=count,
        confidence=0.9,
        timestamp=datetime.now(timezone.utc),
        source=source,
        camera_id="cam-1",
        latitude=18.52,
        longitude=73.85,
    )


def _error_estimate(source: str) -> CrowdEstimate:
    return CrowdEstimate(
        count=0,
        confidence=0.0,
        timestamp=datetime.now(timezone.utc),
        source=source,
        camera_id="cam-1",
        latitude=18.52,
        longitude=73.85,
        error="simulated failure",
    )


def _mock_provider(name: str, result: CrowdEstimate, health_status: str = "ok"):
    p = MagicMock()
    p.name.return_value = name
    p.estimate_crowd.return_value = result
    p.health.return_value = {"status": health_status, "latency_ms": 10.0, "details": "mock"}
    return p


# ── Tests ──────────────────────────────────────────────────────────────────

class TestFallbackOrchestrator:
    def test_first_provider_success(self):
        p1 = _mock_provider("p1", _good_estimate("p1"))
        p2 = _mock_provider("p2", _good_estimate("p2"))
        orch = FallbackOrchestrator([p1, p2], timeout=5.0, max_retries=0)
        cam = _make_camera()
        result = orch.estimate(cam)
        assert result.source == "p1"
        p2.estimate_crowd.assert_not_called()

    def test_fallback_to_second_on_first_failure(self):
        p1 = _mock_provider("p1", _error_estimate("p1"))
        p2 = _mock_provider("p2", _good_estimate("p2", count=3))
        orch = FallbackOrchestrator([p1, p2], timeout=5.0, max_retries=0)
        result = orch.estimate(_make_camera())
        assert result.source == "p2"
        assert result.count == 3

    def test_all_providers_fail_returns_error(self):
        p1 = _mock_provider("p1", _error_estimate("p1"))
        p2 = _mock_provider("p2", _error_estimate("p2"))
        orch = FallbackOrchestrator([p1, p2], timeout=5.0, max_retries=0)
        result = orch.estimate(_make_camera())
        assert not result.is_valid()
        assert result.error

    def test_circuit_breaker_opens_after_threshold(self):
        p1 = _mock_provider("p1", _error_estimate("p1"))
        p2 = _mock_provider("p2", _good_estimate("p2"))
        orch = FallbackOrchestrator(
            [p1, p2],
            timeout=5.0,
            max_retries=0,
            circuit_breaker_threshold=2,
            circuit_breaker_reset_seconds=9999,
        )
        cam = _make_camera()
        # Two failures open the circuit for p1
        orch.estimate(cam)
        orch.estimate(cam)
        # Third call: p1 circuit should be open, jump straight to p2
        result = orch.estimate(cam)
        assert result.source == "p2"
        # p1 should have been called only 2 times (not 3)
        assert p1.estimate_crowd.call_count == 2

    def test_total_requests_tracked(self):
        p1 = _mock_provider("p1", _good_estimate("p1"))
        orch = FallbackOrchestrator([p1], timeout=5.0, max_retries=0)
        cam = _make_camera()
        orch.estimate(cam)
        orch.estimate(cam)
        h = orch.health()
        assert h["total_requests"] == 2

    def test_fallback_count_incremented(self):
        p1 = _mock_provider("p1", _error_estimate("p1"))
        p2 = _mock_provider("p2", _good_estimate("p2"))
        orch = FallbackOrchestrator([p1, p2], timeout=5.0, max_retries=0)
        orch.estimate(_make_camera())
        h = orch.health()
        assert h["fallback_count"] >= 1

    def test_health_reports_all_providers(self):
        p1 = _mock_provider("p1", _good_estimate("p1"))
        p2 = _mock_provider("p2", _good_estimate("p2"))
        orch = FallbackOrchestrator([p1, p2], timeout=5.0, max_retries=0)
        h = orch.health()
        assert "p1" in h["providers"]
        assert "p2" in h["providers"]

    def test_timeout_triggers_fallback(self):
        import time

        def slow_estimate(cam):
            time.sleep(5)
            return _good_estimate("slow")

        p1 = MagicMock()
        p1.name.return_value = "slow"
        p1.estimate_crowd.side_effect = slow_estimate
        p1.health.return_value = {"status": "ok", "latency_ms": -1, "details": ""}

        p2 = _mock_provider("fast", _good_estimate("fast"))
        orch = FallbackOrchestrator([p1, p2], timeout=0.1, max_retries=0)
        result = orch.estimate(_make_camera())
        assert result.source == "fast"
