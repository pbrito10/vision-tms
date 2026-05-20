from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

from api.services import BASE_DIR, ConfigRepository


class PublishedFrameStreamService:
    """Streams the latest frame published by the active vision pipeline."""

    def __init__(self, config_repository: ConfigRepository) -> None:
        self._config_repository = config_repository

    def frames(self) -> Iterator[bytes]:
        frame_path = self._frame_path()
        last_mtime = None
        last_jpeg = self._status_jpeg("Waiting for camera frame")

        while True:
            try:
                stat = frame_path.stat()
                if stat.st_mtime_ns != last_mtime:
                    last_jpeg = frame_path.read_bytes()
                    last_mtime = stat.st_mtime_ns
            except OSError:
                last_jpeg = self._status_jpeg("Waiting for camera frame")

            yield self._multipart_frame(last_jpeg)
            time.sleep(1 / 30)

    def _frame_path(self) -> Path:
        config = self._config_repository.load()
        raw_path = Path(config.get("dashboard", {}).get("frame_path", "dashboard/data/program_frame.jpg"))
        if raw_path.is_absolute():
            return raw_path
        return BASE_DIR / raw_path

    def _status_jpeg(self, message: str) -> bytes:
        import cv2
        import numpy as np

        image = np.full((360, 640, 3), (28, 42, 38), dtype=np.uint8)
        cv2.putText(
            image,
            message,
            (32, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            return b""
        return encoded.tobytes()

    def _multipart_frame(self, jpeg: bytes) -> bytes:
        return (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Cache-Control: no-cache\r\n\r\n"
            + jpeg
            + b"\r\n"
        )
