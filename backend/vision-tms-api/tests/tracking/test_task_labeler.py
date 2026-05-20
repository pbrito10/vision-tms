from __future__ import annotations

from datetime import datetime, timedelta

from src.tracking.task_event import TaskEvent
from src.tracking.task_labeler import TaskLabeler

_T0 = datetime(2024, 3, 15, 9, 0, 0)


def _event(zone: str, cycle: int = 1, forced: bool = False) -> TaskEvent:
    return TaskEvent.create(
        zone,
        _T0,
        _T0 + timedelta(seconds=1),
        cycle_number=cycle,
        was_forced=forced,
    )


def _labeler() -> TaskLabeler:
    return TaskLabeler(
        assembly_zone="Montagem",
        labels_by_previous_zone={
            "Chassi Inferior": "Montagem Chassi Inferior",
            "Porca": "Montagem Porca",
        },
    )


def test_labels_assembly_from_previous_piece_zone() -> None:
    labeler = _labeler()

    piece = labeler.label(_event("Chassi Inferior"))
    assembly = labeler.label(_event("Montagem"))

    assert piece.event.zone_name == "Chassi Inferior"
    assert not piece.counts_as_interruption
    assert assembly.event.zone_name == "Montagem Chassi Inferior"
    assert not assembly.counts_as_interruption


def test_assembly_without_previous_piece_counts_as_interruption() -> None:
    labeler = _labeler()

    analysis = labeler.label(_event("Montagem"))

    assert analysis.event.zone_name == "Montagem sem peca"
    assert analysis.counts_as_interruption


def test_resets_context_when_cycle_changes() -> None:
    labeler = _labeler()

    labeler.label(_event("Porca", cycle=1))
    analysis = labeler.label(_event("Montagem", cycle=2))

    assert analysis.event.zone_name == "Montagem sem peca"
    assert analysis.counts_as_interruption


def test_forced_piece_does_not_set_previous_piece_context() -> None:
    labeler = _labeler()

    labeler.label(_event("Porca", forced=True))
    analysis = labeler.label(_event("Montagem"))

    assert analysis.event.zone_name == "Montagem sem peca"
    assert analysis.counts_as_interruption


def test_unknown_previous_piece_counts_assembly_as_interruption() -> None:
    labeler = _labeler()

    labeler.label(_event("Saida"))
    analysis = labeler.label(_event("Montagem"))

    assert analysis.event.zone_name == "Montagem sem peca"
    assert analysis.counts_as_interruption


def test_disabled_assembly_labeler_keeps_zone_name() -> None:
    labeler = TaskLabeler(assembly_zone=None, labels_by_previous_zone={})

    analysis = labeler.label(_event("Montagem"))

    assert analysis.event.zone_name == "Montagem"
    assert not analysis.counts_as_interruption
