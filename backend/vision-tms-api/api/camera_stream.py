from __future__ import annotations


class CameraSnapshotService:
    """Captures a single camera frame without keeping the device open."""

    def __init__(self, config_repository) -> None:
        self._config_repository = config_repository

    def capture(self) -> bytes:
        import cv2

        from src.video.camera import Camera

        config = self._config_repository.load()
        camera = Camera.from_config(config["camera"])

        try:
            if not camera.is_open():
                raise RuntimeError("Camera unavailable.")

            frame = self._read_frame(camera)
            if frame is None:
                raise RuntimeError("Camera frame unavailable.")

            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if not ok:
                raise RuntimeError("Camera snapshot encoding failed.")

            return encoded.tobytes()
        finally:
            camera.release()

    def _read_frame(self, camera: object) -> object | None:
        frame = None
        for _ in range(3):
            frame = camera.read_frame()
            if frame is not None:
                return frame
        return frame
