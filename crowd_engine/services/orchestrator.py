"""
Fallback Orchestrator — the heart of the resiliency layer.

Responsibilities
----------------
  1. Maintains an ordered list of providers (the "chain").
  2. For each estimation request, tries providers in order until one
     returns a valid result.
  3. Implements per-provider:
       - Timeout handling (using threading)
       - Retry with exponential back-off
       - Circuit-breaker (open after N consecutive failures; auto-resets)
  4. Exposes aggregate health status for every provider.
  5. Records metrics counters (success/fallback/error) accessible via health().
"""

from __future__ import annotations

import concurrent.futures
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from crowd_engine.domain.entities import CameraInput, CrowdEstimate
from crowd_engine.domain.interfaces import CrowdCountProvider
from crowd_engine.infra.config import settings
from crowd_engine.infra.logger import get_logger

log = get_logger(__name__)


class _CircuitBreaker:
    """Simple per-provider circuit breaker."""

    def __init__(self, threshold: int, reset_seconds: int) -> None:
        self._threshold = threshold
        self._reset_delta = timedelta(seconds=reset_seconds)
        self._failures = 0
        self._opened_at: Optional[datetime] = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if datetime.now(timezone.utc) - self._opened_at >= self._reset_delta:
            # Auto-reset
            log.info("Circuit breaker reset")
            self._failures = 0
            self._opened_at = None
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            if self._opened_at is None:
                self._opened_at = datetime.now(timezone.utc)
                log.warning(
                    "Circuit breaker OPENED after %d failures", self._failures
                )


class FallbackOrchestrator:
    """
    Provider chain with timeout, retry, and circuit-breaker resilience.

    Parameters
    ----------
    providers : list[CrowdCountProvider]
        Ordered list — first healthy provider that succeeds wins.
    timeout : float
        Per-call timeout in seconds (default from settings).
    max_retries : int
        Maximum retry attempts per provider before moving to next.
    circuit_breaker_threshold : int
        Consecutive failures before a provider is circuit-broken.
    circuit_breaker_reset_seconds : int
        Seconds before an open circuit auto-resets.
    """

    def __init__(
        self,
        providers: List[CrowdCountProvider],
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        circuit_breaker_threshold: Optional[int] = None,
        circuit_breaker_reset_seconds: Optional[int] = None,
    ) -> None:
        self._providers = providers
        self._timeout = timeout or settings.provider_timeout_seconds
        self._max_retries = max_retries if max_retries is not None else settings.provider_max_retries
        self._cb_threshold = (
            circuit_breaker_threshold
            if circuit_breaker_threshold is not None
            else settings.circuit_breaker_threshold
        )
        self._cb_reset = (
            circuit_breaker_reset_seconds
            if circuit_breaker_reset_seconds is not None
            else settings.circuit_breaker_reset_seconds
        )
        self._circuit_breakers: Dict[str, _CircuitBreaker] = {
            p.name(): _CircuitBreaker(self._cb_threshold, self._cb_reset)
            for p in providers
        }
        # Metrics
        self._metrics: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"success": 0, "failure": 0, "timeout": 0, "circuit_open": 0}
        )
        self._total_requests = 0
        self._fallback_count = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def estimate(self, camera_input: CameraInput) -> CrowdEstimate:
        """
        Run the fallback chain and return the first valid CrowdEstimate.

        Never raises — on total failure returns a synthetic error estimate.
        """
        self._total_requests += 1
        first_attempt = True
        last_error: Optional[CrowdEstimate] = None

        for provider in self._providers:
            pname = provider.name()
            cb = self._circuit_breakers[pname]

            if cb.is_open:
                self._metrics[pname]["circuit_open"] += 1
                log.warning("Provider %s circuit open — skipping", pname)
                continue

            if not first_attempt:
                self._fallback_count += 1
                log.info("Falling back to provider: %s", pname)

            result = self._try_with_retries(provider, camera_input)
            first_attempt = False

            if result.is_valid():
                self._metrics[pname]["success"] += 1
                cb.record_success()
                log.info(
                    "Provider %s returned valid estimate",
                    pname,
                    extra={"count": result.count, "confidence": result.confidence},
                )
                return result
            else:
                self._metrics[pname]["failure"] += 1
                cb.record_failure()
                last_error = result
                log.warning("Provider %s failed: %s", pname, result.error)

        # All providers failed
        log.error("All providers exhausted — returning error estimate")
        return last_error or CrowdEstimate.error_result(
            "orchestrator", camera_input, "All providers failed"
        )

    def health(self) -> dict:
        """Return aggregate health info for all providers + orchestrator metrics."""
        providers_health = {}
        for p in self._providers:
            pname = p.name()
            cb = self._circuit_breakers[pname]
            try:
                ph = p.health()
            except Exception as exc:
                ph = {"status": "unavailable", "latency_ms": -1, "details": str(exc)}
            ph["circuit_open"] = cb.is_open
            ph["metrics"] = dict(self._metrics[pname])
            providers_health[pname] = ph

        return {
            "status": "ok" if any(
                v.get("status") == "ok" for v in providers_health.values()
            ) else "degraded",
            "total_requests": self._total_requests,
            "fallback_count": self._fallback_count,
            "fallback_rate": (
                round(self._fallback_count / self._total_requests, 4)
                if self._total_requests
                else 0.0
            ),
            "providers": providers_health,
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _try_with_retries(
        self, provider: CrowdCountProvider, camera_input: CameraInput
    ) -> CrowdEstimate:
        pname = provider.name()
        backoff = 0.5
        attempt = 0
        while attempt <= self._max_retries:
            if attempt > 0:
                log.info("Retry %d/%d for provider %s", attempt, self._max_retries, pname)
                time.sleep(backoff)
                backoff = min(backoff * 2, 8.0)
            result = self._call_with_timeout(provider, camera_input)
            if result.is_valid():
                return result
            attempt += 1

        return result  # last failed result

    def _call_with_timeout(
        self, provider: CrowdCountProvider, camera_input: CameraInput
    ) -> CrowdEstimate:
        pname = provider.name()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(provider.estimate_crowd, camera_input)
            try:
                return future.result(timeout=self._timeout)
            except concurrent.futures.TimeoutError:
                self._metrics[pname]["timeout"] += 1
                log.warning("Provider %s timed out after %.1fs", pname, self._timeout)
                return CrowdEstimate.error_result(
                    pname, camera_input, f"Provider timeout ({self._timeout}s)"
                )
            except Exception as exc:
                log.exception("Unexpected error from provider %s", pname, exc_info=exc)
                return CrowdEstimate.error_result(pname, camera_input, str(exc))
