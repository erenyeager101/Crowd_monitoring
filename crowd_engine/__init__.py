"""
crowd_engine — Modular Crowd Monitoring Engine
==============================================
Provider-agnostic crowd estimation with automatic fallback chain.
"""

__version__ = "2.0.0"
__all__ = ["CrowdEstimate", "CameraInput", "CrowdCountProvider", "FallbackOrchestrator"]

from crowd_engine.domain.entities import CrowdEstimate, CameraInput
from crowd_engine.domain.interfaces import CrowdCountProvider
from crowd_engine.services.orchestrator import FallbackOrchestrator
