from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class TaskEvent:
    """Value object que representa uma tarefa concluída (ou interrompida por timeout).

    Produzido pela TaskStateMachine e consumido por MetricsCalculator,
    DebugLogger e ExcelExporter.

    was_forced=True indica que a tarefa foi fechada por timeout — a duração
    está inflacionada e não entra nas métricas de tarefa, mas sim nas de
    interrupção.
    """

    zone_name:    str
    start_time:   datetime
    end_time:     datetime
    duration:     timedelta
    cycle_number: int
    was_forced:   bool

    @classmethod
    def create(
        cls,
        zone_name: str,
        start_time: datetime,
        end_time: datetime,
        cycle_number: int,
        was_forced: bool,
    ) -> TaskEvent:
        """Constrói um TaskEvent calculando a duração automaticamente."""
        return cls(
            zone_name=zone_name,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            cycle_number=cycle_number,
            was_forced=was_forced,
        )
