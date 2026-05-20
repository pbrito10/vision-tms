from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from src.video import frame_annotator

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_FRAME_PATH = "dashboard/data/program_frame.jpg"
DEFAULT_JPEG_QUALITY = 82


def dashboard_frame_path(config: dict[str, Any]) -> Path:
    raw_path = Path(config.get("dashboard", {}).get("frame_path", DEFAULT_FRAME_PATH))
    path = raw_path if raw_path.is_absolute() else BASE_DIR / raw_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def annotate_detection_frame(
    frame_rgb,
    detections,
    *,
    rois=None,
    color_scheme=None,
    fps: float | None = None,
):
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    frame_annotator.draw_detections(frame_bgr, detections)
    if rois is not None:
        frame_annotator.draw_rois(frame_bgr, rois, color_scheme=color_scheme)
    if fps is not None:
        frame_annotator.draw_fps(frame_bgr, fps)
    return frame_bgr


class JpegFramePublisher:
    def __init__(self, frame_path: Path, *, quality: int = DEFAULT_JPEG_QUALITY) -> None:
        self.path = frame_path
        self._quality = quality

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> JpegFramePublisher:
        return cls(dashboard_frame_path(config))

    def publish(self, frame_bgr) -> bool:
        ok, encoded = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
        if not ok:
            return False

        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_bytes(encoded.tobytes())
        temp_path.replace(self.path)
        return True
