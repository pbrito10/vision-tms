from src.detection.bounding_box import BoundingBox
from src.detection.hand_detection import HandDetection
from src.detection.keypoint import Keypoint
from src.detection.keypoint_collection import KeypointCollection
from src.shared.confidence import Confidence
from src.shared.hand_side import HandSide
from src.shared.point import Point
from src.tracking.activation_strategy import StillnessDwellStrategy


def _make_hand(
    *,
    wrist: tuple[int, int] = (50, 50),
    mcp: tuple[int, int] = (50, 50),
    side: HandSide = HandSide.RIGHT,
) -> HandDetection:
    confidence = Confidence(0.9)
    keypoints = []
    for index in range(21):
        x, y = mcp if index in (5, 9, 13, 17) else wrist
        keypoints.append(Keypoint(index=index, position=Point(x, y), confidence=confidence))

    return HandDetection(
        keypoints=KeypointCollection(keypoints),
        bounding_box=BoundingBox(Point(0, 0), Point(100, 100)),
        confidence=confidence,
        hand_side=side,
    )


def test_stillness_without_previous_frame_is_inactive() -> None:
    strategy = StillnessDwellStrategy(velocity_threshold_px_per_frame=8.0)

    assert strategy.is_active(_make_hand(mcp=(50, 50)), None) is False


def test_stillness_uses_mcp_centroid_instead_of_wrist() -> None:
    strategy = StillnessDwellStrategy(velocity_threshold_px_per_frame=8.0)

    hand = _make_hand(wrist=(120, 50), mcp=(50, 50))
    previous = _make_hand(wrist=(50, 50), mcp=(51, 50))

    assert strategy.is_active(hand, previous) is True


def test_stillness_rejects_mcp_motion_at_or_above_threshold() -> None:
    strategy = StillnessDwellStrategy(velocity_threshold_px_per_frame=8.0)

    hand = _make_hand(mcp=(58, 50))
    previous = _make_hand(mcp=(50, 50))

    assert strategy.is_active(hand, previous) is False
