#!/usr/bin/env python3
"""Small localhost-only stale-while-refresh snapshot cache for Scrypted cameras."""

from __future__ import annotations

import json
import logging
import math
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from quality import check_pixels


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("NEST_SNAPSHOT_CONFIG", ROOT / "config.json"))
LOG = logging.getLogger("nest-snapshot-cache")


class Camera:
    def __init__(self, name: str, settings: dict, ffmpeg: str, cache_dir: Path):
        self.name = name
        self.source = settings["source"]
        self.cache_path = cache_dir / f"{name}.jpg"
        self.ffmpeg = ffmpeg
        self.refresh_cooldown = float(settings.get("refresh_cooldown_seconds", 120))
        self.fresh_for = float(settings.get("fresh_for_seconds", 300))
        self.capture_timeout = float(settings.get("capture_timeout_seconds", 30))
        self.first_request_wait = float(settings.get("first_request_wait_seconds", 8))
        self.output_width = int(settings.get("output_width", 1280))
        self.output_height = int(settings.get("output_height", 720))
        self.crop_vertical_bias = float(settings.get("crop_vertical_bias", 0.5))
        self.timestamp_overlay = bool(settings.get("timestamp_overlay", True))
        self.overlay_helper = ROOT / "timestamp-overlay"
        if not 0 <= self.crop_vertical_bias <= 1:
            raise ValueError(f"crop_vertical_bias for {name} must be between 0 and 1")
        self.lock = threading.Lock()
        self.in_flight: threading.Thread | None = None
        self.last_attempt = 0.0
        self.last_success = self.cache_path.stat().st_mtime if self.cache_path.exists() else 0.0
        self.last_error: str | None = None
        self.quality_rejections = 0
        self.last_quality_error: str | None = None
        self.request_count = 0
        self.last_request = 0.0
        self.last_request_interval: float | None = None

    def record_request(self) -> None:
        now = time.time()
        with self.lock:
            if self.last_request:
                self.last_request_interval = now - self.last_request
            self.last_request = now
            self.request_count += 1

    def cached(self) -> bytes | None:
        try:
            data = self.cache_path.read_bytes()
        except FileNotFoundError:
            return None
        if data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
            LOG.warning("Ignoring invalid cached JPEG for %s", self.name)
            return None
        return data

    def should_refresh(self) -> bool:
        now = time.time()
        return now - self.last_success >= self.fresh_for and now - self.last_attempt >= self.refresh_cooldown

    def start_refresh(self, force: bool = False) -> threading.Thread | None:
        with self.lock:
            if self.in_flight and self.in_flight.is_alive():
                return self.in_flight
            if not force and not self.should_refresh():
                return None
            self.last_attempt = time.time()
            self.in_flight = threading.Thread(target=self._refresh, name=f"refresh-{self.name}", daemon=True)
            self.in_flight.start()
            return self.in_flight

    def _refresh(self) -> None:
        LOG.info("Refreshing %s", self.name)
        filters = (
            f"[0:v]scale={self.output_width}:{self.output_height}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={self.output_width}:{self.output_height}:"
            f"(iw-ow)/2:(ih-oh)*{self.crop_vertical_bias},setsar=1"
        )
        filters += "[output]"
        command = [
            self.ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-i", self.source,
            "-filter_complex",
            filters,
            "-map", "[output]",
            "-frames:v", "1",
            "-q:v", "2",
            "-f", "image2pipe",
            "-c:v", "mjpeg",
            "pipe:1",
        ]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.capture_timeout,
                check=False,
            )
            image = result.stdout
            if result.returncode != 0:
                error = result.stderr.decode("utf-8", "replace").strip()
                raise RuntimeError(error or f"ffmpeg exited {result.returncode}")
            if image[:2] != b"\xff\xd8" or image[-2:] != b"\xff\xd9":
                raise RuntimeError("capture did not return a complete JPEG")
            # Local receipt time approximates capture time; the cloud source
            # does not provide an authoritative wall-clock exposure timestamp.
            captured_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
            overlay_text = f"Snapshot · {captured_at}"
            self.validate_quality(image)
            if self.timestamp_overlay:
                overlay = subprocess.run(
                    [str(self.overlay_helper), overlay_text],
                    input=image,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False,
                )
                if overlay.returncode != 0:
                    error = overlay.stderr.decode("utf-8", "replace").strip()
                    raise RuntimeError(error or f"timestamp overlay exited {overlay.returncode}")
                image = overlay.stdout
                if image[:2] != b"\xff\xd8" or image[-2:] != b"\xff\xd9":
                    raise RuntimeError("timestamp overlay did not return a complete JPEG")
                self.validate_quality(image)
            temporary = self.cache_path.with_suffix(".jpg.tmp")
            temporary.write_bytes(image)
            temporary.replace(self.cache_path)
            self.last_success = time.time()
            self.last_error = None
            LOG.info("Refreshed %s (%d bytes)", self.name, len(image))
        except Exception as exc:
            self.last_error = str(exc)
            LOG.warning("Refresh failed for %s: %s", self.name, exc)

    def validate_quality(self, image: bytes) -> None:
        try:
            result = subprocess.run(
                [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror",
                 "-i", "pipe:0", "-vf", "scale=160:90", "-frames:v", "1",
                 "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"],
                input=image, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10, check=False,
            )
            if result.returncode != 0:
                raise ValueError("snapshot could not be decoded cleanly")
            check_pixels(result.stdout)
        except Exception as exc:
            self.quality_rejections += 1
            self.last_quality_error = str(exc)
            raise RuntimeError(f"snapshot quality rejected: {exc}") from exc

    def status(self) -> dict:
        cached = self.cached()
        return {
            "cached": cached is not None,
            "cache_age_seconds": round(time.time() - self.last_success, 1) if self.last_success else None,
            "refreshing": bool(self.in_flight and self.in_flight.is_alive()),
            "last_error": self.last_error,
            "output_size": f"{self.output_width}x{self.output_height}",
            "crop_vertical_bias": self.crop_vertical_bias,
            "timestamp_overlay": self.timestamp_overlay,
            "quality_rejections": self.quality_rejections,
            "last_quality_error": self.last_quality_error,
            "snapshot_requests": self.request_count,
            "last_request_seconds_ago": round(time.time() - self.last_request, 1) if self.last_request else None,
            "last_request_interval_seconds": round(self.last_request_interval, 1) if self.last_request_interval else None,
        }


def load_config() -> tuple[dict, dict[str, Camera]]:
    config = json.loads(CONFIG_PATH.read_text())
    cache_dir = Path(config.get("cache_dir", ROOT / "cache")).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cameras = {
        name: Camera(name, settings, config.get("ffmpeg", "/opt/homebrew/bin/ffmpeg"), cache_dir)
        for name, settings in config["cameras"].items()
    }
    return config, cameras


CONFIG, CAMERAS = load_config()


def solar_time(local_date, latitude: float, longitude: float, sunrise: bool, tz: ZoneInfo):
    """Approximate civil sunrise/sunset using the NOAA solar calculation."""
    day = local_date.timetuple().tm_yday
    zenith = 90.833
    hour = longitude / 15.0
    mean = (0.9856 * day) - 3.289
    true_longitude = (mean + 1.916 * math.sin(math.radians(mean))
                      + 0.020 * math.sin(math.radians(2 * mean)) + 282.634) % 360
    right_ascension = math.degrees(math.atan(0.91764 * math.tan(math.radians(true_longitude)))) % 360
    right_ascension += (math.floor(true_longitude / 90) - math.floor(right_ascension / 90)) * 90
    right_ascension /= 15
    sin_decl = 0.39782 * math.sin(math.radians(true_longitude))
    cos_decl = math.cos(math.asin(sin_decl))
    cos_hour = ((math.cos(math.radians(zenith)) - sin_decl * math.sin(math.radians(latitude)))
                / (cos_decl * math.cos(math.radians(latitude))))
    if not -1 <= cos_hour <= 1:
        return None
    hour_angle = math.degrees(math.acos(cos_hour))
    if sunrise:
        hour_angle = 360 - hour_angle
    local_hour = (hour_angle / 15 + right_ascension - 0.06571 * day - 6.622 - hour) % 24
    utc_midnight = datetime.combine(local_date, datetime.min.time(), tzinfo=timezone.utc)
    return (utc_midnight + timedelta(hours=local_hour)).astimezone(tz)


def scheduler_loop() -> None:
    settings = CONFIG.get("schedule", {})
    if not settings.get("enabled", False):
        return
    tz = ZoneInfo(settings.get("timezone", "America/Detroit"))
    latitude = float(settings.get("latitude", 42.3314))
    longitude = float(settings.get("longitude", -83.0458))
    hourly = bool(settings.get("hourly", True))
    completed: set[str] = set()
    while True:
        now = datetime.now(tz)
        keys: list[tuple[str, datetime | None]] = []
        if hourly:
            keys.append((f"hourly:{now.strftime('%Y-%m-%d-%H')}", now.replace(minute=0, second=0, microsecond=0)))
        for name, sunrise in (("sunrise", True), ("sunset", False)):
            event = solar_time(now.date(), latitude, longitude, sunrise, tz)
            if event:
                event += timedelta(minutes=15)
                keys.append((f"{name}:{now.date().isoformat()}", event))
        for key, target in keys:
            if target and key not in completed and 0 <= (now - target).total_seconds() < 60:
                LOG.info("Scheduled refresh (%s)", key)
                for camera in CAMERAS.values():
                    camera.start_refresh(force=True)
                completed.add(key)
        completed = {key for key in completed if key.split(":", 1)[-1] >= (now - timedelta(days=2)).strftime("%Y-%m-%d")}
        time.sleep(10)


class Handler(BaseHTTPRequestHandler):
    server_version = "NestSnapshotCache/0.1"

    def log_message(self, fmt: str, *args) -> None:
        # Snapshot consumers may poll frequently; refresh lifecycle messages are
        # useful, but one access-log line per JPEG would grow without bound.
        LOG.debug("%s %s", self.address_string(), fmt % args)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self.send_json(200, {"status": "ok", "cameras": {k: v.status() for k, v in CAMERAS.items()}})
            return
        if path.startswith("/refresh/"):
            name = path.removeprefix("/refresh/").removesuffix(".jpg")
            camera = CAMERAS.get(name)
            if not camera:
                self.send_json(404, {"error": "unknown camera"})
                return
            thread = camera.start_refresh(force=True)
            self.send_json(202, {"refreshing": bool(thread), "camera": name})
            return
        name = path.removeprefix("/").removesuffix(".jpg")
        camera = CAMERAS.get(name)
        if not camera:
            self.send_json(404, {"error": "unknown camera"})
            return

        camera.record_request()
        cached = camera.cached()
        thread = None
        if cached is None:
            thread = camera.start_refresh()
            if thread:
                thread.join(camera.first_request_wait)
                cached = camera.cached()
        if cached is None:
            self.send_json(503, {"error": "snapshot not available yet", "refreshing": bool(thread)})
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(cached)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Snapshot-Age", str(round(time.time() - camera.last_success, 1)))
        self.end_headers()
        self.wfile.write(cached)
        # Do not let stream startup delay delivery of a known-good stale image.
        if camera.should_refresh():
            camera.start_refresh()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    host = CONFIG.get("host", "127.0.0.1")
    port = int(CONFIG.get("port", 8765))
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=scheduler_loop, name="scheduled-refresh", daemon=True).start()
    # BaseServer.shutdown must run outside the serve_forever thread.
    signal.signal(
        signal.SIGTERM,
        lambda *_: threading.Thread(target=server.shutdown, name="shutdown", daemon=True).start(),
    )
    LOG.info("Listening at http://%s:%d", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
