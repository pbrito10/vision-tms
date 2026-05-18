from __future__ import annotations

from datetime import timedelta

from src.tracking.cycle_result import CycleResult
from src.tracking.task_event import TaskEvent


def _matches_order(actual: list[str], expected: list[str]) -> bool:
    """Verifica se a sequência real respeita a ordem esperada.

    Permite repetições consecutivas da mesma zona (ex: o operador vai três
    vezes às Rodas antes de avançar) mas não permite saltar zonas nem
    visitá-las fora de ordem.

    Algoritmo de ponteiro único: ptr aponta para a zona esperada atual.
    Ao encontrar a zona seguinte, avança o ptr. Qualquer outra zona falha.
    """
    if not expected:
        return True
    if not actual:
        return False

    ptr             = 0
    entered_current = False

    for zone in actual:
        if zone == expected[ptr]:
            entered_current = True
            continue
        if entered_current and ptr + 1 < len(expected) and zone == expected[ptr + 1]:
            ptr            += 1
            entered_current = True
            continue
        return False

    return entered_current and ptr == len(expected) - 1


class CycleTracker:
    """Deteta ciclos completos acumulando TaskEvents até à zona de saída.

    Um ciclo só fecha quando a zona de saída é concluída normalmente
    (was_forced=False). Timeouts acumulam-se no ciclo mas não o fecham —
    uma interrupção não é uma saída real.

    Tarefas was_forced=True também são excluídas da validação de ordem,
    porque representam tempo de espera, não passos de montagem.
    """

    def __init__(self, exit_zone: str, expected_order: list[str]) -> None:
        self._exit_zone:        str             = exit_zone
        self._expected_order:   list[str]       = expected_order
        self._tasks_in_cycle:   list[TaskEvent] = []
        self._completed_cycles: int             = 0

    def record(self, event: TaskEvent) -> CycleResult | None:
        """Acumula o evento. Devolve CycleResult se o ciclo ficou completo."""
        self._tasks_in_cycle.append(event)

        if self._is_cycle_complete(event):
            return self._close_cycle()

        return None

    def current_cycle_number(self) -> int:
        """Número do ciclo em curso (começa em 1; incrementa quando um ciclo fecha).

        Usado como callback nos construtores de OneHandStateMachine e TwoHandsStateMachine:
            machine = OneHandStateMachine(..., cycle_number_fn=tracker.current_cycle_number, ...)
        Cada TaskEvent produzido pela máquina regista o número do ciclo no momento da conclusão.
        """
        return self._completed_cycles + 1

    def current_sequence(self) -> list[str]:
        """Tarefas já confirmadas no ciclo atual, ignorando timeouts."""
        return [task.zone_name for task in self._tasks_in_cycle if not task.was_forced]

    def _is_cycle_complete(self, event: TaskEvent) -> bool:
        return event.zone_name == self._exit_zone and not event.was_forced

    def _close_cycle(self) -> CycleResult:
        """Fecha o ciclo atual, valida a ordem, reinicia o acumulador e devolve o resultado."""
        actual_sequence   = [t.zone_name for t in self._tasks_in_cycle if not t.was_forced]
        sequence_in_order = _matches_order(actual_sequence, self._expected_order)
        duration          = self._tasks_in_cycle[-1].end_time - self._tasks_in_cycle[0].start_time
        cycle_number      = self._completed_cycles + 1

        self._tasks_in_cycle    = []
        self._completed_cycles += 1

        return CycleResult(
            duration=duration,
            cycle_number=cycle_number,
            sequence_in_order=sequence_in_order,
            actual_sequence=actual_sequence,
        )
