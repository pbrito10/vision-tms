from __future__ import annotations

from dataclasses import dataclass, replace

from src.tracking.task_event import TaskEvent


@dataclass(frozen=True)
class TaskAnalysisEvent:
    """TaskEvent preparado para metricas e outputs de analise."""

    event: TaskEvent
    counts_as_interruption: bool = False


class TaskLabeler:
    """Atribui nomes de analise sem alterar a logica fisica de tracking."""

    def __init__(self, assembly_zone: str | None, labels_by_previous_zone: dict[str, str]) -> None:
        self._assembly_zone = assembly_zone
        self._labels_by_previous_zone = labels_by_previous_zone
        self._current_cycle_number: int | None = None
        self._previous_piece_zone: str | None = None

    def label(self, event: TaskEvent) -> TaskAnalysisEvent:
        """Devolve o evento com o nome usado em metricas, Excel e Influx."""
        self._reset_context_if_needed(event.cycle_number)

        label, counts_as_interruption = self._label_for(event)
        self._remember_previous_piece(event)

        analysis_event = event if label == event.zone_name else replace(event, zone_name=label)
        return TaskAnalysisEvent(
            event=analysis_event,
            counts_as_interruption=counts_as_interruption,
        )

    def _reset_context_if_needed(self, cycle_number: int) -> None:
        if self._current_cycle_number == cycle_number:
            return
        self._current_cycle_number = cycle_number
        self._previous_piece_zone = None

    def _label_for(self, event: TaskEvent) -> tuple[str, bool]:
        if self._assembly_zone is None or event.zone_name != self._assembly_zone:
            return event.zone_name, False

        if self._previous_piece_zone is None:
            return self._unattributed_assembly_label(), True

        label = self._labels_by_previous_zone.get(self._previous_piece_zone)
        if label is None:
            return self._unattributed_assembly_label(), True

        return label, False

    def _unattributed_assembly_label(self) -> str:
        return f"{self._assembly_zone} sem peca"

    def _remember_previous_piece(self, event: TaskEvent) -> None:
        if event.was_forced or event.zone_name == self._assembly_zone:
            return
        self._previous_piece_zone = event.zone_name
