"""
Health-check service — builds and exposes a rich system health report.

Used by the /health API endpoint and the CLI diagnostics sub-command.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from crowd_engine.domain.interfaces import CrowdCountProvider
from crowd_engine.infra.logger import get_logger

log = get_logger(__name__)


class HealthService:
    """Aggregate health status across all registered providers."""

    def __init__(self, providers: List[CrowdCountProvider]) -> None:
        self._providers = providers

    def check(self) -> dict:
        """Return a health report dict suitable for JSON serialisation."""
        provider_statuses = {}
        any_ok = False

        for p in self._providers:
            pname = p.name()
            try:
                h = p.health()
            except Exception as exc:
                h = {"status": "unavailable", "latency_ms": -1, "details": str(exc)}
            provider_statuses[pname] = h
            if h.get("status") == "ok":
                any_ok = True

        overall = "ok" if any_ok else "degraded"
        log.info("Health check: overall=%s", overall)

        return {
            "overall": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "providers": provider_statuses,
        }
