from __future__ import annotations

from datetime import timedelta

from src.metrics._duration_metrics import _DurationMetrics


class TaskMetrics(_DurationMetrics):
    """Agrega as durações de uma tarefa específica e calcula estatísticas.

    Cada instância corresponde a uma zona — o MetricsCalculator mantém
    uma por cada ROI definida.

    Só recebe durações de tarefas was_forced=False — a filtragem é
    responsabilidade do MetricsCalculator, não desta classe.
    """

    def add(self, duration: timedelta) -> None:
        """Regista uma nova duração observada."""
        self._add_duration(duration)
