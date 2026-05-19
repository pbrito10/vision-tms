from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

from src.tracking.cycle_result import CycleResult
from src.tracking.task_event import TaskEvent


@dataclass(frozen=True)
class RepeatRule:
    """A repeatable block inside the expected cycle sequence."""

    sequence: tuple[str, ...]
    min_repeats: int
    max_repeats: int

    @classmethod
    def from_config(cls, raw: dict[str, Any]) -> "RepeatRule":
        sequence = tuple(str(zone) for zone in raw.get("sequence", []) if zone)
        min_repeats = int(raw.get("min_repeats", 1))
        max_repeats = int(raw.get("max_repeats", min_repeats))

        if not sequence:
            raise ValueError("Repeat rule sequence cannot be empty.")
        if min_repeats < 1:
            raise ValueError("Repeat rule min_repeats must be at least 1.")
        if max_repeats < min_repeats:
            raise ValueError("Repeat rule max_repeats must be greater than or equal to min_repeats.")

        return cls(sequence=sequence, min_repeats=min_repeats, max_repeats=max_repeats)


def _matches_order(
    actual: list[str],
    expected: list[str],
    repeat_rules: list[RepeatRule] | None = None,
) -> bool:
    """Verifica se a sequência real respeita a ordem esperada.

    Permite repetições consecutivas da mesma zona (ex: o operador vai três
    vezes às Rodas antes de avançar) mas não permite saltar zonas nem
    visitá-las fora de ordem. Também permite blocos repetíveis configurados,
    como Rodas → Montagem entre 1 e 4 vezes antes de continuar o ciclo.
    """
    if not expected:
        return True
    if not actual:
        return False

    rules_by_index = _rules_by_expected_index(expected, repeat_rules or [])
    return _match_from(actual, expected, rules_by_index, actual_index=0, expected_index=0)


def _match_from(
    actual: list[str],
    expected: list[str],
    rules_by_index: dict[int, RepeatRule],
    *,
    actual_index: int,
    expected_index: int,
) -> bool:
    if expected_index == len(expected):
        return actual_index == len(actual)

    repeat_rule = rules_by_index.get(expected_index)
    if repeat_rule is not None:
        return _match_repeat_rule(actual, expected, rules_by_index, repeat_rule, actual_index, expected_index)

    next_actual_index = _consume_zone_run(actual, actual_index, expected[expected_index])
    if next_actual_index is None:
        return False

    return _match_from(
        actual,
        expected,
        rules_by_index,
        actual_index=next_actual_index,
        expected_index=expected_index + 1,
    )


def _match_repeat_rule(
    actual: list[str],
    expected: list[str],
    rules_by_index: dict[int, RepeatRule],
    repeat_rule: RepeatRule,
    actual_index: int,
    expected_index: int,
) -> bool:
    cursor = actual_index
    next_expected_index = expected_index + len(repeat_rule.sequence)

    for repeat_count in range(1, repeat_rule.max_repeats + 1):
        next_cursor = _consume_sequence(actual, cursor, repeat_rule.sequence)
        if next_cursor is None:
            return False

        cursor = next_cursor
        if repeat_count < repeat_rule.min_repeats:
            continue

        if _match_from(
            actual,
            expected,
            rules_by_index,
            actual_index=cursor,
            expected_index=next_expected_index,
        ):
            return True

    return False


def _consume_sequence(actual: list[str], actual_index: int, expected_sequence: tuple[str, ...]) -> int | None:
    cursor = actual_index
    for expected_zone in expected_sequence:
        cursor = _consume_zone_run(actual, cursor, expected_zone)
        if cursor is None:
            return None
    return cursor


def _consume_zone_run(actual: list[str], actual_index: int, expected_zone: str) -> int | None:
    if actual_index >= len(actual) or actual[actual_index] != expected_zone:
        return None

    cursor = actual_index + 1
    while cursor < len(actual) and actual[cursor] == expected_zone:
        cursor += 1
    return cursor


def _rules_by_expected_index(expected: list[str], repeat_rules: list[RepeatRule]) -> dict[int, RepeatRule]:
    result: dict[int, RepeatRule] = {}
    for rule in repeat_rules:
        for index in range(0, len(expected) - len(rule.sequence) + 1):
            if tuple(expected[index:index + len(rule.sequence)]) == rule.sequence:
                result[index] = rule
                break
    return result


class CycleTracker:
    """Deteta ciclos completos acumulando TaskEvents até à zona de saída.

    Um ciclo só abre quando a primeira zona de expected_order é visitada,
    evitando ciclos falsos no arranque. Se a saída falhar e, depois de ja
    haver progresso, a primeira zona aparecer novamente, o ciclo anterior e
    fechado como incompleto e essa nova tarefa inicia outro ciclo.

    Um ciclo só fecha quando a zona de saída é concluída normalmente
    (was_forced=False). Timeouts acumulam-se no ciclo mas não o fecham —
    uma interrupção não é uma saída real.

    Tarefas was_forced=True também são excluídas da validação de ordem,
    porque representam tempo de espera, não passos de montagem.
    """

    def __init__(
        self,
        exit_zone: str,
        expected_order: list[str],
        repeat_rules: list[dict[str, Any]] | None = None,
    ) -> None:
        self._exit_zone:        str             = exit_zone
        self._expected_order:   list[str]       = expected_order
        self._repeat_rules:     list[RepeatRule] = [
            RepeatRule.from_config(rule)
            for rule in repeat_rules or []
        ]
        self._tasks_in_cycle:   list[TaskEvent] = []
        self._completed_cycles: int             = 0
        self._cycle_open:       bool            = not bool(expected_order)
        self._last_event_started_new_cycle: bool = False

    def record(self, event: TaskEvent) -> CycleResult | None:
        """Acumula o evento. Devolve CycleResult se o ciclo ficou completo."""
        self._last_event_started_new_cycle = False

        if not self._cycle_open:
            if event.was_forced or event.zone_name != self._expected_order[0]:
                return None
            self._cycle_open = True
        elif self._starts_next_cycle(event):
            previous_cycle = self._close_current_cycle()
            self._cycle_open = True
            self._last_event_started_new_cycle = True
            self._tasks_in_cycle.append(
                replace(event, cycle_number=self.current_cycle_number())
            )
            return previous_cycle

        self._tasks_in_cycle.append(event)

        if self._is_cycle_complete(event):
            return self._close_current_cycle()

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

    def last_event_started_new_cycle(self) -> bool:
        """True quando o ultimo evento fechou um ciclo incompleto e abriu outro."""
        return self._last_event_started_new_cycle

    def _is_cycle_complete(self, event: TaskEvent) -> bool:
        return event.zone_name == self._exit_zone and not event.was_forced

    def _starts_next_cycle(self, event: TaskEvent) -> bool:
        return (
            bool(self._expected_order)
            and not event.was_forced
            and event.zone_name == self._expected_order[0]
            and self._has_progress_beyond_start_zone()
        )

    def _has_progress_beyond_start_zone(self) -> bool:
        start_zone = self._expected_order[0]
        return any(
            task.zone_name != start_zone
            for task in self._tasks_in_cycle
            if not task.was_forced
        )

    def _close_current_cycle(self) -> CycleResult:
        """Fecha o ciclo atual, valida a ordem, reinicia o acumulador e devolve o resultado."""
        actual_sequence   = [t.zone_name for t in self._tasks_in_cycle if not t.was_forced]
        sequence_in_order = _matches_order(actual_sequence, self._expected_order, self._repeat_rules)
        duration          = self._tasks_in_cycle[-1].end_time - self._tasks_in_cycle[0].start_time
        cycle_number      = self._completed_cycles + 1
        start_time        = self._tasks_in_cycle[0].start_time
        end_time          = self._tasks_in_cycle[-1].end_time

        self._tasks_in_cycle    = []
        self._completed_cycles += 1
        self._cycle_open        = not bool(self._expected_order)

        return CycleResult(
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            cycle_number=cycle_number,
            sequence_in_order=sequence_in_order,
            actual_sequence=actual_sequence,
            expected_sequence=self._expected_order,
        )
