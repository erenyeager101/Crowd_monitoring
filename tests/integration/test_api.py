"""Integration tests for the FastAPI crowd estimation endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crowd_engine.domain.entities import CameraInput, CrowdEstimate


def _good_estimate(cam: CameraInput) -> CrowdEstimate:
    return CrowdEstimate(
        count=7,
        confidence=0.88,
        timestamp=datetime.now(timezone.utc),
        source="test",
        camera_id=cam.camera_id,
        latitude=cam.latitude,
        longitude=cam.longitude,
    )


@pytest.fixture
def client():
    """Build a TestClient with mocked providers so no real APIs are called."""
    mock_orch = MagicMock()
    mock_orch.estimate.side_effect = _good_estimate
    mock_orch.health.return_value = {
        "status": "ok",
        "total_requests": 0,
        "fallback_count": 0,
        "fallback_rate": 0.0,
        "providers": {},
    }

    mock_health = MagicMock()
    mock_health.check.return_value = {
        "overall": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "providers": {},
    }

    # Patch factory functions so lifespan uses mock providers
    with patch("api_server.build_orchestrator", return_value=mock_orch), \
         patch("api_server.build_providers", return_value=[]):
        import api_server as server
        # Override health service factory
        original_lifespan = server.lifespan

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def patched_lifespan(app):
            server._orchestrator = mock_orch
            server._health_service = mock_health
            yield
            server._orchestrator = None
            server._health_service = None

        server.app.router.lifespan_context = patched_lifespan

        with TestClient(server.app) as c:
            yield c


class TestRootEndpoint:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data

    def test_livez(self, client):
        resp = client.get("/livez")
        assert resp.status_code == 200
        assert resp.json()["alive"] is True

    def test_readyz(self, client):
        resp = client.get("/readyz")
        assert resp.status_code == 200


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall" in data
        assert "providers" in data


class TestEstimateEndpoint:
    def test_valid_request(self, client):
        resp = client.post(
            "/api/v1/estimate",
            json={
                "latitude": 18.52,
                "longitude": 73.85,
                "source": "rtsp://cam1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 7
        assert "confidence" in data
        assert "source" in data
        assert "timestamp" in data

    def test_missing_source_returns_422(self, client):
        resp = client.post(
            "/api/v1/estimate",
            json={"latitude": 18.52, "longitude": 73.85},
        )
        assert resp.status_code == 422

    def test_invalid_latitude_returns_422(self, client):
        resp = client.post(
            "/api/v1/estimate",
            json={"latitude": 999, "longitude": 73.85, "source": "rtsp://cam"},
        )
        assert resp.status_code == 422

    def test_correlation_id_header_returned(self, client):
        resp = client.post(
            "/api/v1/estimate",
            json={"latitude": 18.52, "longitude": 73.85, "source": "rtsp://cam"},
        )
        assert "X-Correlation-ID" in resp.headers

    def test_correlation_id_echoed(self, client):
        resp = client.post(
            "/api/v1/estimate",
            json={"latitude": 18.52, "longitude": 73.85, "source": "rtsp://cam"},
            headers={"X-Correlation-ID": "my-trace-id"},
        )
        assert resp.headers["X-Correlation-ID"] == "my-trace-id"


class TestOrchestratorHealthEndpoint:
    def test_returns_metrics(self, client):
        resp = client.get("/api/v1/orchestrator/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "total_requests" in data
