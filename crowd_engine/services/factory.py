"""
Factory helpers — wire providers according to the configured chain.
"""

from __future__ import annotations

from typing import List

from crowd_engine.domain.interfaces import CrowdCountProvider
from crowd_engine.infra.config import settings
from crowd_engine.infra.logger import get_logger
from crowd_engine.services.orchestrator import FallbackOrchestrator

log = get_logger(__name__)

_PROVIDER_REGISTRY = {
    "roboflow": "crowd_engine.providers.roboflow_provider:RoboflowProvider",
    "huggingface": "crowd_engine.providers.huggingface_provider:HuggingFaceProvider",
    "geospatial": "crowd_engine.providers.geospatial_provider:GeospatialProvider",
    "opencv": "crowd_engine.providers.opencv_provider:OpenCVProvider",
}


def _load_provider(name: str) -> CrowdCountProvider:
    entry = _PROVIDER_REGISTRY.get(name)
    if not entry:
        raise ValueError(f"Unknown provider: {name!r}. Available: {list(_PROVIDER_REGISTRY)}")
    module_path, class_name = entry.split(":")
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()  # type: ignore[return-value]


def build_providers(chain: List[str] | None = None) -> List[CrowdCountProvider]:
    chain = chain or settings.provider_chain
    providers: List[CrowdCountProvider] = []
    for name in chain:
        try:
            p = _load_provider(name)
            providers.append(p)
            log.info("Registered provider: %s", name)
        except Exception as exc:
            log.warning("Failed to load provider %r: %s — skipping", name, exc)
    if not providers:
        raise RuntimeError("No providers could be loaded. Check PROVIDER_CHAIN and dependencies.")
    return providers


def build_orchestrator(chain: List[str] | None = None) -> FallbackOrchestrator:
    providers = build_providers(chain)
    return FallbackOrchestrator(providers)
