from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from src.detection.mediapipe_detector import MediapipeDetector
from src.shared.hand_side import HandSide


def _landmark(x: float, y: float):
    return SimpleNamespace(x=x, y=y, z=0.0)


def _handedness(name: str = "Right", score: float = 0.95):
    return [SimpleNamespace(category_name=name, score=score)]


def _result(landmarks, handedness):
    return SimpleNamespace(hand_landmarks=landmarks, handedness=handedness)


def _detector() -> MediapipeDetector:
    fake_mp = SimpleNamespace(
        Image=lambda image_format, data: SimpleNamespace(image_format=image_format, data=data),
        ImageFormat=SimpleNamespace(SRGB="SRGB"),
    )
    return MediapipeDetector("unused.task", landmarker=MagicMock(), mp_module=fake_mp)


def test_detector_can_be_exercised_without_loading_mediapipe_model() -> None:
    detector = _detector()
    landmarks = [_landmark(0.5, 0.5) for _ in range(21)]
    detector._landmarker.detect_for_video.return_value = _result([landmarks], [_handedness("Right", 0.91)])

    detections = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))

    assert len(detections) == 1
    assert detections[0].hand_side == HandSide.RIGHT
    assert detections[0].confidence.value == 0.91


def test_injected_landmarker_requires_mp_module() -> None:
    try:
        MediapipeDetector("unused.task", landmarker=MagicMock())
    except ValueError as exc:
        assert "mp_module" in str(exc)
    else:
        raise AssertionError("Expected ValueError when mp_module is missing")
