"""
Crowd Monitoring API Server
============================
FastAPI application exposing crowd estimation and system health endpoints.

Run with:
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

Or via Docker / docker-compose (see docker-compose.yml).

OpenAPI docs available at:
    http://localhost:8000/docs     (Swagger UI)
    http://localhost:8000/redoc    (ReDoc)
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from crowd_engine.domain.entities import CameraInput
from crowd_engine.infra.config import settings
from crowd_engine.infra.logger import get_logger, set_correlation_id
from crowd_engine.services.factory import build_orchestrator
from crowd_engine.services.health import HealthService
from crowd_engine.services.factory import build_providers

log = get_logger("api_server")

# ── Startup / shutdown ─────────────────────────────────────────────────────

_orchestrator = None
_health_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator, _health_service
    log.info("Starting Crowd Monitoring API")
    providers = build_providers()
    _orchestrator = build_orchestrator()
    _health_service = HealthService(providers)
    yield
    log.info("Shutting down Crowd Monitoring API")


# ── App factory ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Crowd Monitoring API",
    description=(
        "Modular, provider-agnostic crowd estimation API with automatic fallback. "
        "Supports multiple providers: Roboflow, HuggingFace, Geospatial, OpenCV."
    ),
    version="2.0.0",
    contact={"name": "Crowd Monitoring Team"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Rate limiter (in-memory, per IP) ──────────────────────────────────────

_rate_store: Dict[str, Dict[str, Any]] = {}
_RATE_WINDOW = 60  # seconds


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    record = _rate_store.setdefault(ip, {"count": 0, "window_start": now})
    if now - record["window_start"] > _RATE_WINDOW:
        record["count"] = 0
        record["window_start"] = now
    record["count"] += 1
    return record["count"] <= settings.rate_limit_per_minute


# ── Middleware ─────────────────────────────────────────────────────────────

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    set_correlation_id(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "retry_after_seconds": _RATE_WINDOW},
        )
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Request / Response schemas ─────────────────────────────────────────────

class EstimateRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Camera latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Camera longitude")
    source: str = Field(..., description="Image/video source: URL, file path, or device index")
    camera_id: Optional[str] = Field(None, description="Optional stable camera identifier")
    label: Optional[str] = Field(None, description="Human-readable camera label")

    @field_validator("source")
    @classmethod
    def source_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source must not be empty")
        return v


class EstimateResponse(BaseModel):
    count: int
    confidence: float
    timestamp: str
    source: str
    camera_id: str
    latitude: float
    longitude: float
    metadata: Dict[str, Any] = {}
    error: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/", tags=["meta"])
def root():
    """API root — returns version info."""
    return {"name": "Crowd Monitoring API", "version": "2.0.0", "docs": "/docs"}


@app.get("/health", tags=["observability"], summary="System health check")
def health_check():
    """
    Returns health status for all configured providers plus aggregate metrics.

    Overall status is `ok` if at least one provider is healthy, `degraded` otherwise.
    """
    if _health_service is None:
        raise HTTPException(status_code=503, detail="Service initialising")
    return _health_service.check()


@app.get("/readyz", tags=["observability"], summary="Kubernetes readiness probe")
def readyz():
    """Lightweight readiness probe — 200 when the app is ready to serve."""
    if _orchestrator is None:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return {"ready": True}


@app.get("/livez", tags=["observability"], summary="Kubernetes liveness probe")
def livez():
    """Lightweight liveness probe — always 200 if the process is alive."""
    return {"alive": True}


@app.post(
    "/api/v1/estimate",
    response_model=EstimateResponse,
    tags=["crowd"],
    summary="Estimate crowd count",
    status_code=status.HTTP_200_OK,
)
def estimate_crowd(body: EstimateRequest):
    """
    Estimate the crowd count for a given camera source.

    The orchestrator tries providers in order (as configured by PROVIDER_CHAIN):
    1. Roboflow API (if ROBOFLOW_API_KEY configured)
    2. HuggingFace local model / Inference API
    3. Geospatial / OSM heuristic (low confidence)
    4. OpenCV MobileNetSSD (legacy degraded mode)

    Returns the first valid estimate, or an error estimate if all fail.
    """
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Service initialising")

    camera = CameraInput(
        source=body.source,
        latitude=body.latitude,
        longitude=body.longitude,
        camera_id=body.camera_id or str(uuid.uuid4()),
        label=body.label or body.source,
    )
    result = _orchestrator.estimate(camera)
    return result.as_dict()


@app.get(
    "/api/v1/orchestrator/health",
    tags=["observability"],
    summary="Orchestrator metrics",
)
def orchestrator_health():
    """
    Returns detailed orchestrator metrics: success rate, fallback rate,
    per-provider circuit-breaker status, and call counts.
    """
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Service initialising")
    return _orchestrator.health()


# ── Dev entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
