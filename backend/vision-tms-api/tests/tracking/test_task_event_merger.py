from __future__ import annotations

from datetime import datetime, timedelta

from src.tracking.task_event import TaskEvent
from src.tracking.task_event_merger import ConsecutiveTaskMerger


def _event(zone: str, start_s: float, end_s: float, *, was_forced: bool = False) -> TaskEvent:
    base = datetime(2026, 5, 20, 10, 0, 0)
    return TaskEvent.create(
        zone_name=zone,
        start_time=base + timedelta(seconds=start_s),
        end_time=base + timedelta(seconds=end_s),
        cycle_number=1,
        was_forced=was_forced,
    )


def test_merges_consecutive_equal_zones_into_one_duration() -> None:
    merger = ConsecutiveTaskMerger()

    assert merger.push(_event("Rodas", 1.0, 2.0)) is None
    assert merger.push(_event("Rodas", 2.4, 4.0)) is None

    merged = merger.flush()

    assert merged is not None
    assert merged.zone_name == "Rodas"
    assert merged.start_time == datetime(2026, 5, 20, 10, 0, 1)
    assert merged.end_time == datetime(2026, 5, 20, 10, 0, 4)
    assert merged.duration == timedelta(seconds=3)


def test_emits_previous_when_next_zone_is_different() -> None:
    merger = ConsecutiveTaskMerger()

    first = _event("Rodas", 1.0, 2.0)
    second = _event("Montagem", 3.0, 5.0)

    assert merger.push(first) is None
    assert merger.push(second) == first
    assert merger.flush() == second


def test_does_not_merge_forced_events() -> None:
    merger = ConsecutiveTaskMerger()

    first = _event("Rodas", 1.0, 2.0)
    forced = _event("Rodas", 2.4, 4.0, was_forced=True)

    assert merger.push(first) is None
    assert merger.push(forced) == first
    assert merger.flush() == forced
