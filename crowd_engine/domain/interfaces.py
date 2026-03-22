"""Domain interfaces — provider contract (structural sub-typing via Protocol)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from crowd_engine.domain.entities import CameraInput, CrowdEstimate


@runtime_checkable
class CrowdCountProvider(Protocol):
    """
    Every crowd-counting provider must implement this interface.

    Providers are stateless; state is managed externally (orchestrator / config).
    """

    def name(self) -> str:
        """Return a stable, unique provider identifier (e.g. 'opencv', 'roboflow')."""
        ...

    def estimate_crowd(self, camera_input: CameraInput) -> CrowdEstimate:
        """
        Perform crowd estimation for the given camera input.

        Must return a valid CrowdEstimate on success, or a CrowdEstimate with
        error set on failure.  Must NOT raise exceptions; use error field instead.
        """
        ...

    def health(self) -> dict:
        """
        Return provider health information.

        Expected keys:
          - status: 'ok' | 'degraded' | 'unavailable'
          - latency_ms: float (last successful call latency, or -1)
          - details: str (optional human-readable detail)
        """
        ...
