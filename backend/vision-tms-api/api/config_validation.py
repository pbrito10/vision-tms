from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def validate_runtime_config(config: Mapping[str, Any]) -> list[str]:
    """Return human-readable runtime configuration errors."""
    errors: list[str] = []
    tracking = config.get("tracking")
    if not isinstance(tracking, Mapping):
        return ["tracking config must be a mapping."]

    zones = _string_list(tracking.get("zones"))
    cycle_order = _string_list(tracking.get("cycle_zone_order"))
    two_hands_zones = _string_list(tracking.get("two_hands_zones", []))
    exit_zone = _string_value(tracking.get("exit_zone"))
    start_zone = _string_value(tracking.get("start_zone"))
    assembly_zone = _string_value(tracking.get("assembly_zone"))

    errors.extend(_validate_zones(zones))
    errors.extend(_validate_cycle_order(cycle_order, zones, start_zone, exit_zone))
    errors.extend(_validate_named_zones("two_hands_zones", two_hands_zones, zones))
    if assembly_zone:
        errors.extend(_validate_named_zones("assembly_zone", [assembly_zone], zones))
    errors.extend(_validate_assembly_labels(tracking.get("assembly_task_labels", {}), zones))
    errors.extend(_validate_repeat_rules(tracking.get("cycle_repeat_rules", []), zones, cycle_order, exit_zone))
    return errors


def _validate_zones(zones: list[str] | None) -> list[str]:
    if not zones:
        return ["tracking.zones must contain at least one zone."]

    duplicates = _duplicates(zones)
    if duplicates:
        return [f"tracking.zones contains duplicate zones: {', '.join(duplicates)}."]
    return []


def _validate_cycle_order(
    cycle_order: list[str] | None,
    zones: list[str] | None,
    start_zone: str | None,
    exit_zone: str | None,
) -> list[str]:
    errors: list[str] = []
    if not cycle_order:
        return ["tracking.cycle_zone_order must contain at least one step."]

    valid_zones = set(zones or [])
    unknown = sorted(set(cycle_order) - valid_zones)
    if unknown:
        errors.append(f"tracking.cycle_zone_order references unknown zones: {', '.join(unknown)}.")

    first_zone = cycle_order[0]
    if start_zone:
        if start_zone not in valid_zones:
            errors.append(f"tracking.start_zone references unknown zone '{start_zone}'.")
        if start_zone != first_zone:
            errors.append(
                f"tracking.start_zone must match the first cycle step '{first_zone}', got '{start_zone}'."
            )

    if not exit_zone:
        errors.append("tracking.exit_zone must be configured.")
    elif exit_zone not in valid_zones:
        errors.append(f"tracking.exit_zone references unknown zone '{exit_zone}'.")
    elif exit_zone not in cycle_order:
        errors.append(f"tracking.exit_zone '{exit_zone}' must appear in tracking.cycle_zone_order.")
    elif cycle_order[-1] != exit_zone:
        errors.append(f"tracking.exit_zone '{exit_zone}' must be the last cycle step.")

    if len(cycle_order) > 1 and first_zone == exit_zone:
        errors.append("tracking.cycle_zone_order cannot start with the exit zone.")

    return errors


def _validate_repeat_rules(
    raw_rules: Any,
    zones: list[str] | None,
    cycle_order: list[str] | None,
    exit_zone: str | None,
) -> list[str]:
    if raw_rules in (None, []):
        return []
    if not isinstance(raw_rules, list):
        return ["tracking.cycle_repeat_rules must be a list."]

    errors: list[str] = []
    valid_zones = set(zones or [])
    for index, raw_rule in enumerate(raw_rules, start=1):
        prefix = f"tracking.cycle_repeat_rules[{index}]"
        if not isinstance(raw_rule, Mapping):
            errors.append(f"{prefix} must be a mapping.")
            continue

        sequence = _string_list(raw_rule.get("sequence"))
        if not sequence:
            errors.append(f"{prefix}.sequence must contain at least one zone.")
            continue

        unknown = sorted(set(sequence) - valid_zones)
        if unknown:
            errors.append(f"{prefix}.sequence references unknown zones: {', '.join(unknown)}.")
        if exit_zone and exit_zone in sequence:
            errors.append(f"{prefix}.sequence cannot include the exit zone '{exit_zone}'.")
        if cycle_order and not _contains_subsequence(cycle_order, sequence):
            errors.append(f"{prefix}.sequence must appear contiguously in tracking.cycle_zone_order.")

        min_repeats = _integer_value(raw_rule.get("min_repeats", 1))
        max_repeats = _integer_value(raw_rule.get("max_repeats", min_repeats))
        if min_repeats is None:
            errors.append(f"{prefix}.min_repeats must be an integer.")
            continue
        if max_repeats is None:
            errors.append(f"{prefix}.max_repeats must be an integer.")
            continue
        if min_repeats < 1:
            errors.append(f"{prefix}.min_repeats must be at least 1.")
        if max_repeats < min_repeats:
            errors.append(f"{prefix}.max_repeats must be greater than or equal to min_repeats.")

    return errors


def _validate_assembly_labels(raw_labels: Any, zones: list[str] | None) -> list[str]:
    if raw_labels in (None, {}):
        return []
    if not isinstance(raw_labels, Mapping):
        return ["tracking.assembly_task_labels must be a mapping."]

    errors: list[str] = []
    valid_zones = set(zones or [])
    unknown = sorted(str(zone) for zone in raw_labels if str(zone).strip() not in valid_zones)
    if unknown:
        errors.append(f"tracking.assembly_task_labels references unknown zones: {', '.join(unknown)}.")

    empty_labels = sorted(str(zone) for zone, label in raw_labels.items() if not str(label).strip())
    if empty_labels:
        errors.append(f"tracking.assembly_task_labels contains empty labels for: {', '.join(empty_labels)}.")
    return errors


def _validate_named_zones(field: str, values: list[str] | None, zones: list[str] | None) -> list[str]:
    if not values:
        return []
    valid_zones = set(zones or [])
    unknown = sorted(set(values) - valid_zones)
    if unknown:
        return [f"tracking.{field} references unknown zones: {', '.join(unknown)}."]
    return []


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    result = [str(item).strip() for item in value]
    if any(not item for item in result):
        return None
    return result


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integer_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _contains_subsequence(values: list[str], subsequence: list[str]) -> bool:
    last_start = len(values) - len(subsequence) + 1
    return any(values[index:index + len(subsequence)] == subsequence for index in range(max(last_start, 0)))
