from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from api.services import BASE_DIR, ConfigRepository

logger = logging.getLogger(__name__)


class CameraStreamService:
    """Publishes one annotated camera feed to any number of HTTP clients."""

    def __init__(self, config_repository: ConfigRepository) -> None:
        self._config_repository = config_repository
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._producer_thread: threading.Thread | None = None
        self._client_count = 0
        self._latest_jpeg: bytes | None = None
        self._frame_version = 0
        self._last_live_frame_at = 0.0

    def frames(self) -> Iterator[bytes]:
        """Yield multipart JPEG frames for a browser <img> or video client."""
        self._register_client()
        last_seen_version = -1

        try:
            while True:
                version, jpeg = self._wait_for_frame(last_seen_version)
                last_seen_version = version
                yield self._multipart_frame(jpeg)
        finally:
            self._unregister_client()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the producer thread and release the camera promptly."""
        with self._condition:
            producer_thread = self._producer_thread
            self._client_count = 0
            self._stop_event.set()
            self._condition.notify_all()

        if producer_thread is not None and producer_thread.is_alive():
            producer_thread.join(timeout=timeout)

    def _register_client(self) -> None:
        with self._condition:
            self._client_count += 1
            if self._producer_thread is not None and self._producer_thread.is_alive():
                self._stop_event.clear()
                return

            if self._producer_thread is None or not self._producer_thread.is_alive():
                self._stop_event.clear()
                self._latest_jpeg = None
                self._frame_version = 0
                self._producer_thread = threading.Thread(
                    target=self._produce_frames,
                    name="camera-stream-producer",
                    daemon=True,
                )
                self._producer_thread.start()

    def _unregister_client(self) -> None:
        with self._condition:
            self._client_count = max(0, self._client_count - 1)
            if self._client_count == 0:
                self._stop_event.set()
            self._condition.notify_all()

    def _wait_for_frame(self, last_seen_version: int) -> tuple[int, bytes]:
        with self._condition:
            while self._latest_jpeg is None or self._frame_version == last_seen_version:
                self._condition.wait(timeout=2)
                if self._latest_jpeg is not None and self._frame_version != last_seen_version:
                    break
                if self._producer_thread is not None and not self._producer_thread.is_alive():
                    self._latest_jpeg = self._status_jpeg("Camera stream stopped")
                    self._frame_version += 1
                    break
                if self._is_live_frame_stale():
                    self._latest_jpeg = self._status_jpeg("Camera stream reconnecting")
                    self._frame_version += 1
                    break

            return self._frame_version, self._latest_jpeg or self._status_jpeg("Waiting for camera")

    def _produce_frames(self) -> None:
        import cv2

        from src.detection.mediapipe_detector import MediapipeDetector
        from src.video import frame_annotator

        config = self._config_repository.load()
        camera = None
        detector = None
        detector_error = None
        read_failures = 0
        previous_time = time.perf_counter()

        try:
            try:
                model_path = self._resolve_path(config["detection"]["model_path"])
                if not model_path.exists():
                    raise FileNotFoundError(f"Model not found: {model_path}")

                detector = MediapipeDetector(
                    model_path=str(model_path),
                    max_num_hands=config["detection"]["max_num_hands"],
                    min_detection_confidence=config["detection"]["min_detection_confidence"],
                    min_tracking_confidence=config["detection"]["min_tracking_confidence"],
                )
            except Exception as exc:
                detector_error = self._exception_message("Detector unavailable", exc)
                logger.exception(detector_error)

            while not self._stop_event.is_set():
                if camera is None or not camera.is_open():
                    camera = self._open_camera(config)
                    if camera is None:
                        self._sleep_until_stop(0.5)
                        continue

                frame = camera.read_frame()
                if frame is None:
                    read_failures += 1
                    if read_failures == 1:
                        self._publish_error("Camera frame unavailable")
                    if read_failures >= 5:
                        logger.warning("Camera stream lost frames; reopening camera.")
                        camera.release()
                        camera = None
                        read_failures = 0
                        self._sleep_until_stop(0.5)
                    continue
                read_failures = 0

                if detector is not None:
                    try:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        detections = detector.detect(frame_rgb)
                        frame_annotator.draw_detections(frame, detections)
                    except Exception as exc:
                        detector_error = self._exception_message("Detection failed", exc)
                        logger.exception(detector_error)
                        detector.release()
                        detector = None

                if detector_error:
                    self._draw_overlay_message(frame, detector_error)

                now = time.perf_counter()
                elapsed = now - previous_time
                fps = 1.0 / elapsed if elapsed > 0 else 0.0
                previous_time = now
                frame_annotator.draw_fps(frame, fps)

                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok:
                    self._publish_jpeg(encoded.tobytes(), is_live_frame=True)

                time.sleep(0.03)
        finally:
            if detector is not None:
                detector.release()
            if camera is not None:
                camera.release()
            with self._condition:
                if threading.current_thread() is self._producer_thread:
                    self._producer_thread = None
                self._condition.notify_all()

    def _publish_error(self, message: str) -> None:
        self._publish_jpeg(self._status_jpeg(message))

    def _publish_jpeg(self, jpeg: bytes, *, is_live_frame: bool = False) -> None:
        with self._condition:
            self._latest_jpeg = jpeg
            self._frame_version += 1
            if is_live_frame:
                self._last_live_frame_at = time.monotonic()
            self._condition.notify_all()

    def _open_camera(self, config: dict) -> object | None:
        from src.video.camera import Camera

        camera = Camera.from_config(config["camera"])
        if camera.is_open():
            return camera

        camera.release()
        self._publish_error("Camera unavailable")
        return None

    def _sleep_until_stop(self, seconds: float) -> None:
        self._stop_event.wait(timeout=seconds)

    def _is_live_frame_stale(self) -> bool:
        if self._latest_jpeg is None:
            return False
        if self._last_live_frame_at <= 0:
            return False
        return time.monotonic() - self._last_live_frame_at > 4.0

    def _status_jpeg(self, message: str) -> bytes:
        import cv2
        import numpy as np

        image = np.full((360, 640, 3), (28, 42, 38), dtype=np.uint8)
        self._draw_overlay_message(image, message)
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            return b""
        return encoded.tobytes()

    def _resolve_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return BASE_DIR / path

    def _exception_message(self, prefix: str, exc: Exception) -> str:
        detail = str(exc).strip()
        if detail:
            return f"{prefix}: {type(exc).__name__}: {detail}"
        return f"{prefix}: {type(exc).__name__}"

    def _draw_overlay_message(self, frame, message: str) -> None:
        import cv2

        cv2.rectangle(frame, (0, 0), (frame.shape[1], 70), (20, 32, 29), -1)
        for index, line in enumerate(self._wrap_message(message, 58)[:2]):
            cv2.putText(
                frame,
                line,
                (14, 27 + index * 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

    def _wrap_message(self, message: str, width: int) -> list[str]:
        words = message.split()
        lines = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
        if current:
            lines.append(current)
        return lines or [message[:width]]

    def _multipart_frame(self, jpeg: bytes) -> bytes:
        return (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Cache-Control: no-cache\r\n\r\n"
            + jpeg
            + b"\r\n"
        )
