from __future__ import annotations

from datetime import datetime, timedelta

from src.metrics.cycle_metrics import CycleMetrics
from src.metrics.task_metrics import TaskMetrics
from src.output.metrics_snapshot import MetricsSnapshot
from src.tracking.cycle_result import CycleResult
from src.tracking.task_event import TaskEvent


class MetricsCalculator:
    """Agrega eventos em métricas online à medida que chegam do pipeline.

    A separação produtivo/interrupção é feita aqui com base em was_forced:
      - False → tarefa concluída normalmente → tempo produtivo
      - True  → tarefa fechada por timeout   → tempo de interrupção

    O tempo de transição não é medido diretamente — é o que sobra:
    sessão total − produtivo − interrupção. Pode incluir tempo entre zonas,
    hesitações do operador, ou qualquer período sem mão detetada.
    """

    def __init__(self, session_start: datetime, zone_names: list[str]) -> None:
        self._session_start = session_start

        self._task_metrics: dict[str, TaskMetrics] = {
            name: TaskMetrics() for name in zone_names
        }
        self._cycle_metrics     = CycleMetrics()
        self._productive_time   = timedelta(0)
        self._interruption_time = timedelta(0)

    def record(self, event: TaskEvent) -> None:
        if event.was_forced:
            self._interruption_time += event.duration
            return

        self._productive_time += event.duration

        # Zonas não previstas em settings.yaml chegam aqui se o operador
        # visitar uma zona fora do conjunto configurado — criamos a entrada
        # em vez de ignorar ou lançar excepção.
        if event.zone_name not in self._task_metrics:
            self._task_metrics[event.zone_name] = TaskMetrics()

        self._task_metrics[event.zone_name].add(event.duration)

    def record_cycle(self, cycle_result: CycleResult) -> None:
        """Regista as métricas de um ciclo completo (duração e se a sequência foi respeitada).

        Chamado pelo _MonitorSession sempre que o CycleTracker fecha um ciclo.
        """
        self._cycle_metrics.add(cycle_result.duration, cycle_result.sequence_in_order)

    def snapshot(self) -> MetricsSnapshot:
        now              = datetime.now()
        session_duration = now - self._session_start
        transition_time  = self._transition_time(session_duration)
        percentages      = self._percentages(session_duration)

        return MetricsSnapshot(
            task_metrics=dict(self._task_metrics),
            cycle_metrics=self._cycle_metrics,
            productive_time=self._productive_time,
            transition_time=transition_time,
            interruption_time=self._interruption_time,
            productive_percentage=percentages[0],
            transition_percentage=percentages[1],
            interruption_percentage=percentages[2],
            bottleneck_zone=self._bottleneck_zone(),
            session_duration=session_duration,
            captured_at=now,
        )

    def _transition_time(self, session_duration: timedelta) -> timedelta:
        transition = session_duration - self._productive_time - self._interruption_time
        # Pequenas variações de timing podem dar resultado ligeiramente negativo
        return max(transition, timedelta(0))

    def _percentages(self, session_duration: timedelta) -> tuple[float, float, float]:
        """Devolve (produtivo%, transição%, interrupção%) garantindo soma de 100%."""
        total_seconds = session_duration.total_seconds()
        if total_seconds == 0:
            return 0.0, 0.0, 0.0

        productive   = self._productive_time.total_seconds()   / total_seconds * 100
        interruption = self._interruption_time.total_seconds() / total_seconds * 100
        # Transição calculada como complemento para garantir que os três somam 100%
        transition   = max(0.0, 100.0 - productive - interruption)
        return productive, transition, interruption

    def _bottleneck_zone(self) -> str | None:
        """Zona com maior tempo médio de tarefa — None se ainda não há dados."""
        zones_with_data = [
            (name, metrics)
            for name, metrics in self._task_metrics.items()
            if metrics.count() > 0
        ]

        if not zones_with_data:
            return None

        return max(zones_with_data, key=lambda pair: pair[1].average().total_seconds())[0]
