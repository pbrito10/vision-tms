from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

RESULT_IN_ORDER = "Em ordem"
RESULT_INCOMPLETE = "Sequencia incompleta"
RESULT_OUT_OF_ORDER = "Fora de ordem"

_OCCURRENCE_LIMITS = {
    "Rodas": (1, 4),
}


@dataclass(frozen=True)
class OrderDiagnosis:
    result: str
    problem: str


def diagnose_order(actual: Sequence[str], expected: Sequence[str]) -> OrderDiagnosis:
    """Explica como a sequencia registada se compara com a ordem esperada."""
    actual_list = list(actual)
    expected_list = list(expected)

    if not expected_list:
        return OrderDiagnosis(RESULT_IN_ORDER, "Sem ordem esperada definida.")

    if not actual_list:
        return OrderDiagnosis(
            RESULT_INCOMPLETE,
            f"Nao foram registadas zonas completas. Faltaram zonas esperadas: {_join_zones(expected_list)}.",
        )

    ptr = 0
    entered_current = False
    occurrences: dict[int, int] = {}
    missing: list[str] = []

    for zone in actual_list:
        if ptr >= len(expected_list):
            return OrderDiagnosis(
                RESULT_OUT_OF_ORDER,
                f'A sequencia esperada ja estava completa, mas apareceu "{zone}".',
            )

        if zone == expected_list[ptr]:
            entered_current = True
            count = _record_occurrence(occurrences, ptr)
            if _exceeds_occurrence_limit(zone, count):
                return _too_many_occurrences_diagnosis(zone, count)
            continue

        if _can_repeat_previous_limited_zone(zone, expected_list, ptr, entered_current):
            ptr -= 1
            entered_current = True
            count = _record_occurrence(occurrences, ptr)
            if _exceeds_occurrence_limit(zone, count):
                return _too_many_occurrences_diagnosis(zone, count)
            continue

        search_start = ptr + 1 if entered_current else ptr
        next_index = _find_from(expected_list, zone, search_start)
        if next_index is not None:
            missing_start = ptr + 1 if entered_current else ptr
            missing.extend(expected_list[missing_start:next_index])
            ptr = next_index
            entered_current = True
            count = _record_occurrence(occurrences, ptr)
            if _exceeds_occurrence_limit(zone, count):
                return _too_many_occurrences_diagnosis(zone, count)
            continue

        expected_zone = _next_expected_zone(expected_list, ptr, entered_current)
        return OrderDiagnosis(
            RESULT_OUT_OF_ORDER,
            f'Esperava "{expected_zone}", mas apareceu "{zone}".',
        )

    if ptr == len(expected_list) - 1 and entered_current and not missing:
        return OrderDiagnosis(RESULT_IN_ORDER, "Sem problema detetado.")

    missing_start = ptr + 1 if entered_current else ptr
    missing.extend(expected_list[missing_start:])
    return OrderDiagnosis(
        RESULT_INCOMPLETE,
        f"Faltaram zonas esperadas: {_join_zones(missing)}.",
    )


def _find_from(values: Sequence[str], target: str, start: int) -> int | None:
    for idx in range(start, len(values)):
        if values[idx] == target:
            return idx
    return None


def _next_expected_zone(expected: Sequence[str], ptr: int, entered_current: bool) -> str:
    if entered_current and ptr + 1 < len(expected):
        return expected[ptr + 1]
    return expected[ptr]


def _record_occurrence(occurrences: dict[int, int], expected_index: int) -> int:
    count = occurrences.get(expected_index, 0) + 1
    occurrences[expected_index] = count
    return count


def _can_repeat_previous_limited_zone(
    zone: str,
    expected: Sequence[str],
    ptr: int,
    entered_current: bool,
) -> bool:
    return (
        entered_current
        and ptr > 0
        and zone == expected[ptr - 1]
        and zone in _OCCURRENCE_LIMITS
    )


def _exceeds_occurrence_limit(zone: str, count: int) -> bool:
    limit = _OCCURRENCE_LIMITS.get(zone)
    if limit is None:
        return False
    _, max_count = limit
    return count > max_count


def _too_many_occurrences_diagnosis(zone: str, count: int) -> OrderDiagnosis:
    min_count, max_count = _OCCURRENCE_LIMITS[zone]
    return OrderDiagnosis(
        RESULT_OUT_OF_ORDER,
        f'A zona "{zone}" apareceu {count} vezes; o intervalo aceite e {min_count} a {max_count} presencas.',
    )


def _join_zones(zones: Sequence[str]) -> str:
    return ", ".join(f'"{zone}"' for zone in zones)
