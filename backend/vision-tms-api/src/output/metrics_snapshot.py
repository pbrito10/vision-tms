from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.metrics.cycle_metrics import CycleMetrics
from src.metrics.task_metrics import TaskMetrics


@dataclass(frozen=True)
class MetricsSnapshot:
    """Snapshot imutável de todas as métricas num dado momento.

    Transporta o estado calculado pelo MetricsCalculator para os
    consumidores de forma tipada, sem dicts genéricos cujas chaves e tipos
    são desconhecidos.

    As três percentagens somam 100% (dentro de margem de arredondamento).
    """

    # Métricas por zona — só tarefas was_forced=False
    task_metrics: dict[str, TaskMetrics]

    # Métricas de ciclos completos
    cycle_metrics: CycleMetrics

    # Decomposição do tempo da sessão
    productive_time:    timedelta
    transition_time:    timedelta
    interruption_time:  timedelta

    # Percentagens correspondentes (0.0–100.0)
    productive_percentage:    float
    transition_percentage:    float
    interruption_percentage:  float

    # Zona que mais atrasa o ciclo; None se ainda não há dados suficientes
    bottleneck_zone: str | None

    session_duration: timedelta
    captured_at:      datetime
