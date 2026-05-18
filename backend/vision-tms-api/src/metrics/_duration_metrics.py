from __future__ import annotations

import math
from datetime import timedelta


class _DurationMetrics:
    """Base para classes de métricas baseadas em coleções de durações.

    Encapsula armazenamento e estatísticas (mínimo, máximo, média, desvio padrão),
    eliminando duplicação entre TaskMetrics e CycleMetrics.

    Prefixo _ — privada ao package metrics, não para uso externo.
    """

    def __init__(self) -> None:
        self._durations: list[timedelta] = []

    def _add_duration(self, duration: timedelta) -> None:
        """Regista uma duração. Chamado pelas subclasses no seu add()."""
        self._durations.append(duration)

    def count(self) -> int:
        """Número de ocorrências registadas."""
        return len(self._durations)

    def minimum(self) -> timedelta:
        """Duração mínima observada. Requer count() > 0."""
        return min(self._durations)

    def maximum(self) -> timedelta:
        """Duração máxima observada. Requer count() > 0."""
        return max(self._durations)

    def average(self) -> timedelta:
        """Média aritmética das durações. Requer count() > 0."""
        total = sum((d.total_seconds() for d in self._durations), 0.0)
        return timedelta(seconds=total / self.count())

    def std_deviation(self) -> timedelta:
        """Desvio padrão das durações. Devolve timedelta(0) se count() < 2."""
        if self.count() < 2:
            return timedelta(0)
        mean     = self.average().total_seconds()
        variance = sum((d.total_seconds() - mean) ** 2 for d in self._durations) / self.count()
        return timedelta(seconds=math.sqrt(variance))
