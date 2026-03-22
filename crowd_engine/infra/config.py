"""
Infrastructure — typed, env-var-backed configuration.

Usage
-----
    from crowd_engine.infra.config import settings
    print(settings.mongo_uri)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key, "")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key, "")
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key, "").lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


@dataclass
class Settings:
    # ── MongoDB ────────────────────────────────────────────────────────────
    mongo_uri: str = field(default_factory=lambda: _env("MONGO_URI", "mongodb://localhost:27017"))
    mongo_db: str = field(default_factory=lambda: _env("MONGO_DB", "home"))
    mongo_collection: str = field(default_factory=lambda: _env("MONGO_COLLECTION", "blogs"))

    # ── Node server ────────────────────────────────────────────────────────
    node_server_url: str = field(default_factory=lambda: _env("NODE_SERVER_URL", "http://localhost:3000"))

    # ── Crowd engine (Python API) ──────────────────────────────────────────
    api_host: str = field(default_factory=lambda: _env("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: _env_int("API_PORT", 8000))
    api_secret_key: str = field(default_factory=lambda: _env("API_SECRET_KEY", "changeme-in-production"))

    # ── Provider chain ─────────────────────────────────────────────────────
    # Comma-separated ordered list.  Available: roboflow, huggingface, geospatial, opencv
    provider_chain: List[str] = field(
        default_factory=lambda: [
            p.strip()
            for p in _env("PROVIDER_CHAIN", "roboflow,huggingface,geospatial,opencv").split(",")
            if p.strip()
        ]
    )

    # ── Roboflow provider ──────────────────────────────────────────────────
    roboflow_api_key: str = field(default_factory=lambda: _env("ROBOFLOW_API_KEY"))
    roboflow_workspace: str = field(default_factory=lambda: _env("ROBOFLOW_WORKSPACE", "crowd-counting"))
    roboflow_model_id: str = field(default_factory=lambda: _env("ROBOFLOW_MODEL_ID", "crowd-counting-1"))
    roboflow_model_version: int = field(default_factory=lambda: _env_int("ROBOFLOW_MODEL_VERSION", 1))

    # ── HuggingFace provider ───────────────────────────────────────────────
    huggingface_model: str = field(
        default_factory=lambda: _env("HF_MODEL", "facebook/detr-resnet-50")
    )
    huggingface_api_key: Optional[str] = field(
        default_factory=lambda: _env("HF_API_KEY") or None
    )

    # ── OpenCV provider ────────────────────────────────────────────────────
    opencv_prototxt: str = field(
        default_factory=lambda: _env("OPENCV_PROTOTXT", "MobileNetSSD_deploy.prototxt")
    )
    opencv_caffemodel: str = field(
        default_factory=lambda: _env("OPENCV_CAFFEMODEL", "MobileNetSSD_deploy.caffemodel")
    )
    opencv_confidence_threshold: float = field(
        default_factory=lambda: _env_float("OPENCV_CONFIDENCE_THRESHOLD", 0.4)
    )
    opencv_frame_skip: int = field(default_factory=lambda: _env_int("OPENCV_FRAME_SKIP", 5))

    # ── Orchestrator / resiliency ──────────────────────────────────────────
    provider_timeout_seconds: float = field(
        default_factory=lambda: _env_float("PROVIDER_TIMEOUT_SECONDS", 10.0)
    )
    provider_max_retries: int = field(default_factory=lambda: _env_int("PROVIDER_MAX_RETRIES", 2))
    circuit_breaker_threshold: int = field(
        default_factory=lambda: _env_int("CIRCUIT_BREAKER_THRESHOLD", 3)
    )
    circuit_breaker_reset_seconds: int = field(
        default_factory=lambda: _env_int("CIRCUIT_BREAKER_RESET_SECONDS", 60)
    )

    # ── Logging ───────────────────────────────────────────────────────────
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())
    log_json: bool = field(default_factory=lambda: _env_bool("LOG_JSON", False))

    # ── Camera sources ─────────────────────────────────────────────────────
    cameras_file: str = field(default_factory=lambda: _env("CAMERAS_FILE", "cameras.json"))

    # ── Rate limiting ──────────────────────────────────────────────────────
    rate_limit_per_minute: int = field(
        default_factory=lambda: _env_int("RATE_LIMIT_PER_MINUTE", 60)
    )


# Singleton — imported by all modules
settings = Settings()
