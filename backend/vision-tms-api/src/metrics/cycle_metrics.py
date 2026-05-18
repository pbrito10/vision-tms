from __future__ import annotations

from datetime import timedelta

from src.metrics._duration_metrics import _DurationMetrics


class CycleMetrics(_DurationMetrics):
    """Agrega os tempos de ciclos completos e calcula estatísticas.

    Separado de TaskMetrics por SRP — um ciclo engloba múltiplas tarefas
    e tempos de transição, tendo semântica distinta de uma tarefa individual.
    """

    def __init__(self) -> None:
        super().__init__()
        self._in_order_count: int = 0

    def add(self, duration: timedelta, sequence_in_order: bool) -> None:
        """Regista a duração de um ciclo completo e se a sequência de zonas foi respeitada."""
        self._add_duration(duration)
        if sequence_in_order:
            self._in_order_count += 1

    def count_in_order(self) -> int:
        """Ciclos em que as zonas foram visitadas na ordem definida em cycle_zone_order."""
        return self._in_order_count

    def count_out_of_order(self) -> int:
        """Ciclos com zonas visitadas fora da ordem esperada."""
        return self.count() - self._in_order_count

    def recent_durations(self, limit: int) -> list[timedelta]:
        """Últimas durações de ciclo registadas, preservando ordem cronológica."""
        return self._durations[-limit:]
