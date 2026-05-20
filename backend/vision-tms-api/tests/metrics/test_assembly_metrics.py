from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from src.metrics.metrics_calculator import MetricsCalculator
from src.tracking.cycle_tracker import CycleTracker
from src.tracking.task_event import TaskEvent
from src.tracking.task_labeler import TaskLabeler

_T0 = datetime(2024, 3, 15, 9, 0, 0)


def _event(zone: str, start_s: float, end_s: float) -> TaskEvent:
    return TaskEvent.create(
        zone_name=zone,
        start_time=_T0 + timedelta(seconds=start_s),
        end_time=_T0 + timedelta(seconds=end_s),
        cycle_number=1,
        was_forced=False,
    )


def test_assembly_metric_is_split_by_previous_piece() -> None:
    metrics = MetricsCalculator(_T0, ["Porca", "Montagem", "Saida"])
    labeler = TaskLabeler(
        assembly_zone="Montagem",
        labels_by_previous_zone={"Porca": "Montagem Porca"},
    )

    for event in [_event("Porca", 0, 2), _event("Montagem", 3, 8)]:
        analysis = labeler.label(event)
        metrics.record(analysis.event)

    snapshot = metrics.snapshot()

    assert snapshot.task_metrics["Porca"].count() == 1
    assert snapshot.task_metrics["Montagem"].count() == 0
    assert snapshot.task_metrics["Montagem Porca"].count() == 1
    assert snapshot.task_metrics["Montagem Porca"].average() == timedelta(seconds=5)
    assert snapshot.bottleneck_zone == "Montagem Porca"


def test_assembly_after_completed_cycle_before_start_zone_is_interruption() -> None:
    tracker = CycleTracker(exit_zone="Saida", expected_order=["Porca", "Montagem", "Saida"])
    metrics = MetricsCalculator(_T0, ["Porca", "Montagem", "Saida"])
    labeler = TaskLabeler(
        assembly_zone="Montagem",
        labels_by_previous_zone={"Porca": "Montagem Porca"},
    )

    analysis_events = []
    for event in [
        _event("Porca", 0, 2),
        _event("Montagem", 3, 8),
        _event("Saida", 9, 10),
        _event("Montagem", 12, 16),
    ]:
        event = replace(event, cycle_number=tracker.current_cycle_number())
        tracker.record(event)
        analysis = labeler.label(event)
        analysis_events.append(analysis)
        if analysis.counts_as_interruption:
            metrics.record_interruption(analysis.event.duration)
        else:
            metrics.record(analysis.event)

    snapshot = metrics.snapshot()
    stray_assembly = analysis_events[-1]

    assert tracker.current_cycle_number() == 2
    assert stray_assembly.event.zone_name == "Montagem sem peca"
    assert stray_assembly.counts_as_interruption
    assert snapshot.interruption_time == timedelta(seconds=4)
    assert "Montagem sem peca" not in snapshot.task_metrics
    assert snapshot.task_metrics["Montagem Porca"].count() == 1
