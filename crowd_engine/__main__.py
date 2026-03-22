"""
crowd_engine CLI entry point.

Usage
-----
    python -m crowd_engine               # run all cameras in cameras.json
    python -m crowd_engine --once        # process one frame per camera and exit
    python -m crowd_engine --health      # print provider health and exit
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from crowd_engine.domain.entities import CameraInput
from crowd_engine.infra.config import settings
from crowd_engine.infra.logger import get_logger, set_correlation_id
from crowd_engine.services.factory import build_orchestrator
from crowd_engine.services.health import HealthService
from crowd_engine.services.factory import build_providers

log = get_logger(__name__)


def load_cameras(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        log.warning("cameras file not found: %s — using empty list", path)
        return []
    with open(p) as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    log.error("cameras.json must be a JSON array")
    return []


def _send_to_node(data: dict) -> None:
    url = f"{settings.node_server_url}/update_data"
    try:
        resp = requests.post(url, json=data, timeout=5)
        if resp.status_code != 200:
            log.warning("Node server returned %s", resp.status_code)
    except requests.exceptions.RequestException as exc:
        log.warning("Failed to send data to Node server: %s", exc)


def process_camera_loop(cam_config: dict, orchestrator: Any, run_once: bool = False) -> None:
    set_correlation_id()
    source = cam_config.get("source", 0)
    lat = cam_config.get("coordinates", {}).get("latitude", 0.0)
    lng = cam_config.get("coordinates", {}).get("longitude", 0.0)
    label = cam_config.get("label", str(source))

    camera_input = CameraInput(
        source=source,
        latitude=lat,
        longitude=lng,
        label=label,
    )
    log.info("Starting camera loop", extra={"source": str(source), "label": label})

    while True:
        estimate = orchestrator.estimate(camera_input)
        payload = {
            "count": estimate.count,
            "coordinates": {"latitude": lat, "longitude": lng},
            "timestamp": estimate.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "source": estimate.source,
            "confidence": estimate.confidence,
        }
        log.info(
            "Crowd estimate",
            extra={"count": estimate.count, "provider": estimate.source, "label": label},
        )
        _send_to_node(payload)

        if run_once:
            break
        time.sleep(settings.opencv_frame_skip)  # reuse frame_skip as poll interval


def cmd_health() -> None:
    providers = build_providers()
    svc = HealthService(providers)
    report = svc.check()
    print(json.dumps(report, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crowd Monitoring Engine")
    parser.add_argument("--once", action="store_true", help="Process one frame per camera and exit")
    parser.add_argument("--health", action="store_true", help="Print provider health and exit")
    parser.add_argument(
        "--cameras", default=settings.cameras_file, help="Path to cameras.json"
    )
    args = parser.parse_args(argv)

    if args.health:
        cmd_health()
        return 0

    cameras = load_cameras(args.cameras)
    if not cameras:
        log.error("No cameras configured. Add entries to %s", args.cameras)
        return 1

    orchestrator = build_orchestrator()
    threads: list[threading.Thread] = []
    for cam in cameras:
        t = threading.Thread(
            target=process_camera_loop,
            args=(cam, orchestrator, args.once),
            daemon=True,
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return 0


if __name__ == "__main__":
    sys.exit(main())
