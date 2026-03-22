"""Domain entities — core data structures for crowd estimation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class CameraInput:
    """Represents a video/image source together with its geographic location."""

    source: Any  # file path, URL, device index, or raw frame bytes
    latitude: float
    longitude: float
    camera_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""

    def as_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "source": str(self.source),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "label": self.label,
        }


@dataclass
class CrowdEstimate:
    """Standardised output schema for every crowd-counting provider."""

    count: int
    confidence: float  # 0.0 – 1.0
    timestamp: datetime
    source: str  # provider name
    camera_id: str
    latitude: float
    longitude: float
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    # Convenience -----------------------------------------------------------

    def is_valid(self) -> bool:
        return self.error is None and self.count >= 0 and 0.0 <= self.confidence <= 1.0

    def as_dict(self) -> dict:
        return {
            "count": self.count,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "camera_id": self.camera_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "metadata": self.metadata,
            "error": self.error,
        }

    @classmethod
    def error_result(
        cls,
        source: str,
        camera_input: "CameraInput",
        error_msg: str,
    ) -> "CrowdEstimate":
        return cls(
            count=0,
            confidence=0.0,
            timestamp=datetime.now(timezone.utc),
            source=source,
            camera_id=camera_input.camera_id,
            latitude=camera_input.latitude,
            longitude=camera_input.longitude,
            error=error_msg,
        )
