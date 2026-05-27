from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.detection.bounding_box import BoundingBox
from src.detection.hand_detection import HandDetection
from src.detection.keypoint import Keypoint
from src.detection.keypoint_collection import KeypointCollection
from src.shared.confidence import Confidence
from src.shared.hand_side import HandSide
from src.shared.point import Point
from src.tracking.activation_strategy import StillnessDwellStrategy, TimeDwellStrategy
from src.tracking.task_state_machine import OneHandStateMachine, TwoHandsStateMachine

_T0 = datetime(2026, 5, 26, 14, 0, 0)


def _zone(name: str):
    return SimpleNamespace(name=name)


def _hand(*, side: HandSide = HandSide.RIGHT, mcp: tuple[int, int] = (50, 50)) -> HandDetection:
    confidence = Confidence(0.9)
    keypoints = [
        Keypoint(
            index=index,
            position=Point(*(mcp if index in (5, 9, 13, 17) else (50, 50))),
            confidence=confidence,
        )
        for index in range(21)
    ]
    return HandDetection(
        keypoints=KeypointCollection(keypoints),
        bounding_box=BoundingBox(Point(0, 0), Point(100, 100)),
        confidence=confidence,
        hand_side=side,
    )


def _classified(zone_name: str, *, side: HandSide = HandSide.RIGHT):
    return [(_hand(side=side), _zone(zone_name))]


def test_one_hand_completes_when_leaving_on_validation_boundary() -> None:
    machine = OneHandStateMachine(
        dwell_time=timedelta(seconds=0.3),
        task_timeout=timedelta(seconds=30),
        cycle_number_fn=lambda: 1,
        strategy=StillnessDwellStrategy(velocity_threshold_px_per_frame=8.0),
    )

    assert machine.update(_classified("chassi superior"), _T0) is None
    assert machine.update(_classified("chassi superior"), _T0 + timedelta(seconds=0.1)) is None
    assert machine.update(_classified("chassi superior"), _T0 + timedelta(seconds=0.2)) is None

    event = machine.update([], _T0 + timedelta(seconds=0.3))

    assert event is not None
    assert event.zone_name == "chassi superior"
    assert event.duration == timedelta(seconds=0.3)
    assert machine.pop_diagnostics() == []


def test_two_hands_completes_when_one_hand_leaves_on_validation_boundary() -> None:
    machine = TwoHandsStateMachine(
        dwell_time=timedelta(seconds=0.3),
        task_timeout=timedelta(seconds=30),
        cycle_number_fn=lambda: 1,
        strategy=TimeDwellStrategy(),
    )
    both_hands = [
        (_hand(side=HandSide.LEFT), _zone("montagem")),
        (_hand(side=HandSide.RIGHT), _zone("montagem")),
    ]

    assert machine.update(both_hands, _T0) is None
    assert machine.update(both_hands, _T0 + timedelta(seconds=0.1)) is None

    event = machine.update(_classified("montagem", side=HandSide.LEFT), _T0 + timedelta(seconds=0.4))

    assert event is not None
    assert event.zone_name == "montagem"
    assert event.duration == timedelta(seconds=0.3)
    assert machine.pop_diagnostics() == []
