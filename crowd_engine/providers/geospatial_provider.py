"""
Geospatial Provider — crowd proxy using OpenStreetMap / Nominatim.

This is a tertiary, low-confidence crowd indicator.  It works by:
  1. Resolving the lat/lng to the nearest OSM place/POI using Nominatim.
  2. Heuristically estimating crowd density based on:
       - Place category (mall, market, park, restaurant, …)
       - Day-of-week + hour-of-day popularity weights
       - (Optional) local historical data passed via metadata

This provider NEVER raises; it always returns a result with a clearly
downgraded confidence score (≤ 0.4) so the orchestrator knows to try
better providers first.

No API key required — uses the free Nominatim service with a courteous
User-Agent header and request throttling (≥ 1 s between calls).

Limitations
-----------
  - Accuracy is fundamentally limited (no real-time signal).
  - Confidence is capped at 0.35 to signal "best-effort proxy only".
  - Rate-limit: Nominatim ToS requires max 1 req/s and a valid User-Agent.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import requests

from crowd_engine.domain.entities import CameraInput, CrowdEstimate
from crowd_engine.infra.logger import get_logger

log = get_logger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "CrowdMonitoringApp/2.0 (open-source crowd management system)"
_MAX_CONFIDENCE = 0.35

# Popularity multipliers by place category (rough heuristic)
_CATEGORY_WEIGHTS: dict[str, float] = {
    "mall": 1.0,
    "market": 0.95,
    "marketplace": 0.95,
    "supermarket": 0.85,
    "restaurant": 0.7,
    "food_court": 0.9,
    "park": 0.6,
    "station": 0.9,
    "bus_station": 0.85,
    "hospital": 0.7,
    "school": 0.6,
    "university": 0.65,
    "place_of_worship": 0.55,
    "default": 0.5,
}

# Day-of-week weights (0 = Monday … 6 = Sunday)
_DOW_WEIGHTS = [0.7, 0.75, 0.8, 0.85, 0.95, 1.0, 0.9]

# Hour-of-day weights (index 0 = midnight)
_HOUR_WEIGHTS = [
    0.1, 0.05, 0.05, 0.05, 0.05, 0.1,   # 00–05
    0.3, 0.5, 0.7, 0.8, 0.85, 0.9,      # 06–11
    0.95, 0.9, 0.85, 0.8, 0.85, 0.95,   # 12–17
    1.0, 0.9, 0.8, 0.6, 0.4, 0.2,       # 18–23
]

# Nominal crowd capacity for 100 % weight (persons)
_BASE_CAPACITY = 80

_LAST_CALL_TS: float = 0.0  # module-level throttle


class GeospatialProvider:
    """Low-confidence crowd estimator based on geospatial heuristics + OSM."""

    def __init__(self, timeout: float = 5.0) -> None:
        self._timeout = timeout
        self._last_latency_ms: float = -1.0

    # ── CrowdCountProvider contract ────────────────────────────────────────

    def name(self) -> str:
        return "geospatial"

    def estimate_crowd(self, camera_input: CameraInput) -> CrowdEstimate:
        global _LAST_CALL_TS
        try:
            t0 = time.monotonic()

            # Throttle: respect Nominatim's 1-req/s ToS
            elapsed = time.monotonic() - _LAST_CALL_TS
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)

            place_info = self._reverse_geocode(camera_input.latitude, camera_input.longitude)
            _LAST_CALL_TS = time.monotonic()

            category = self._extract_category(place_info)
            now = datetime.now(timezone.utc)
            score = self._popularity_score(category, now.weekday(), now.hour)
            count = max(0, int(_BASE_CAPACITY * score))
            confidence = min(_MAX_CONFIDENCE, score * _MAX_CONFIDENCE)

            self._last_latency_ms = (time.monotonic() - t0) * 1000
            log.info(
                "geospatial estimate",
                extra={
                    "count": count,
                    "confidence": round(confidence, 3),
                    "category": category,
                    "latency_ms": round(self._last_latency_ms, 1),
                },
            )
            return CrowdEstimate(
                count=count,
                confidence=confidence,
                timestamp=now,
                source=self.name(),
                camera_id=camera_input.camera_id,
                latitude=camera_input.latitude,
                longitude=camera_input.longitude,
                metadata={
                    "osm_category": category,
                    "popularity_score": round(score, 3),
                    "place_info": place_info.get("display_name", ""),
                    "note": "Low-confidence geospatial proxy; not real-time",
                },
            )
        except Exception as exc:
            log.warning("geospatial provider error: %s", exc)
            return CrowdEstimate.error_result(self.name(), camera_input, str(exc))

    def health(self) -> dict:
        try:
            resp = requests.get(
                _NOMINATIM_URL,
                params={"lat": 0, "lon": 0, "format": "json"},
                headers={"User-Agent": _USER_AGENT},
                timeout=5.0,
            )
            status = "ok" if resp.status_code < 500 else "degraded"
        except Exception as exc:
            return {"status": "unavailable", "latency_ms": -1, "details": str(exc)}
        return {
            "status": status,
            "latency_ms": self._last_latency_ms,
            "details": "OSM Nominatim reachable",
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _reverse_geocode(self, lat: float, lon: float) -> dict:
        resp = requests.get(
            _NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 18, "addressdetails": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _extract_category(place_info: dict) -> str:
        # OSM type/class → our category map
        osm_type = place_info.get("type", "").lower()
        osm_class = place_info.get("class", "").lower()
        address = place_info.get("address", {})
        for key in ("shop", "amenity", "leisure", "tourism"):
            if key in address:
                val = str(address[key]).lower()
                if val in _CATEGORY_WEIGHTS:
                    return val
        for candidate in (osm_type, osm_class):
            if candidate in _CATEGORY_WEIGHTS:
                return candidate
        return "default"

    @staticmethod
    def _popularity_score(category: str, day_of_week: int, hour: int) -> float:
        cat_w = _CATEGORY_WEIGHTS.get(category, _CATEGORY_WEIGHTS["default"])
        dow_w = _DOW_WEIGHTS[day_of_week % 7]
        hour_w = _HOUR_WEIGHTS[hour % 24]
        return cat_w * dow_w * hour_w
