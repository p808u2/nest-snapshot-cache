#!/usr/bin/env python3
"""Read-only readiness check for the local snapshot-cache prototype."""

from __future__ import annotations

import json
import sys
import time
from urllib.request import urlopen


BASE = "http://127.0.0.1:18765"


def get(path: str, timeout: float = 8) -> tuple[bytes, dict[str, str], float]:
    started = time.monotonic()
    with urlopen(BASE + path, timeout=timeout) as response:
        body = response.read()
        headers = {key.lower(): value for key, value in response.headers.items()}
        if response.status != 200:
            raise RuntimeError(f"{path} returned HTTP {response.status}")
    return body, headers, time.monotonic() - started


def main() -> int:
    health_body, _, _ = get("/health")
    health = json.loads(health_body)
    if health["status"] != "ok":
        raise RuntimeError(f"cache is not ready: {health}")
    results = {}
    for name, camera in health["cameras"].items():
        if not camera["cached"]:
            raise RuntimeError(f"{name} cache is not ready: {health}")
        image, headers, elapsed = get(f"/{name}.jpg")
        if headers.get("content-type") != "image/jpeg":
            raise RuntimeError(f"{name} returned {headers.get('content-type')}")
        if image[:2] != b"\xff\xd8" or image[-2:] != b"\xff\xd9":
            raise RuntimeError(f"{name} response is not a complete JPEG")
        if elapsed > 1:
            raise RuntimeError(f"{name} cached response was too slow: {elapsed:.3f}s")
        results[name] = {
            "response_seconds": round(elapsed, 4),
            "jpeg_bytes": len(image),
            "snapshot_age_seconds": headers.get("x-snapshot-age"),
            "refreshing": camera["refreshing"],
            "last_error": camera["last_error"],
            "output_size": camera["output_size"],
            "crop_vertical_bias": camera["crop_vertical_bias"],
        }
    print(
        json.dumps(
            {
                "ok": True,
                "cameras": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
