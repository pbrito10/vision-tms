from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class CycleResult:
    """Resultado de um ciclo completo de montagem.

    Produzido pelo CycleTracker quando a zona de saída é confirmada ou quando
    um novo arranque obriga a fechar o ciclo anterior como incompleto.
    Transporta timestamps, duração, número do ciclo, se a sequência foi
    respeitada e as zonas visitadas, para debug, métricas e exportação.
    """

    start_time: datetime
    end_time: datetime
    duration:           timedelta
    cycle_number:       int
    sequence_in_order:  bool        # True se as zonas foram visitadas na ordem de cycle_zone_order
    actual_sequence:    Sequence[str]   # Sequência real de zonas visitadas neste ciclo
    expected_sequence:  Sequence[str] = ()
    is_anomaly:         bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "actual_sequence", tuple(self.actual_sequence))
        object.__setattr__(self, "expected_sequence", tuple(self.expected_sequence))
