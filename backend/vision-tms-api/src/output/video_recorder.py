from __future__ import annotations

from pathlib import Path
from time import monotonic

import numpy as np


class VideoRecorder:
    """Grava frames BGR anotados num MP4."""

    def __init__(self, path: Path, fps: float, *, enabled: bool = True) -> None:
        if fps <= 0:
            raise ValueError("fps deve ser maior que zero.")

        self._path = path
        self._fps = fps
        self._period = 1 / fps
        self._enabled = enabled
        self._writer = None
        self._last_write_at: float | None = None

    @property
    def path(self) -> Path:
        return self._path

    def write(self, frame_bgr: np.ndarray) -> None:
        """Escreve um frame BGR respeitando o FPS nominal configurado."""
        if not self._enabled:
            return

        now = monotonic()
        if self._last_write_at is not None and now - self._last_write_at < self._period:
            return

        if self._writer is None:
            self._open(frame_bgr)

        self._writer.write(frame_bgr)
        self._last_write_at = now

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def _open(self, frame_bgr: np.ndarray) -> None:
        import cv2

        height, width = frame_bgr.shape[:2]
        self._path.parent.mkdir(parents=True, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(self._path), fourcc, self._fps, (width, height))
        if not writer.isOpened():
            self._enabled = False
            raise RuntimeError(f"Nao foi possivel abrir o video para escrita: {self._path}")

        self._writer = writer
