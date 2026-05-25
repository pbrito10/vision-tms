from __future__ import annotations

from api.config_validation import validate_runtime_config


def _config(**tracking_overrides):
    tracking = {
        "zones": ["Porca", "Montagem", "Rodas", "Saida"],
        "two_hands_zones": ["Montagem"],
        "assembly_zone": "Montagem",
        "assembly_task_labels": {"Porca": "Montagem Porca"},
        "cycle_zone_order": ["Porca", "Montagem", "Rodas", "Montagem", "Saida"],
        "cycle_repeat_rules": [
            {
                "sequence": ["Rodas", "Montagem"],
                "min_repeats": 1,
                "max_repeats": 4,
            }
        ],
        "start_zone": "Porca",
        "exit_zone": "Saida",
    }
    tracking.update(tracking_overrides)
    return {"tracking": tracking}


def test_valid_runtime_tracking_config_has_no_errors() -> None:
    assert validate_runtime_config(_config()) == []


def test_requires_exit_zone_to_be_known_and_last_cycle_step() -> None:
    errors = validate_runtime_config(
        _config(
            exit_zone="Saida",
            cycle_zone_order=["Porca", "Saida", "Montagem"],
        )
    )

    assert "tracking.exit_zone 'Saida' must be the last cycle step." in errors


def test_rejects_unknown_cycle_zones() -> None:
    errors = validate_runtime_config(
        _config(cycle_zone_order=["Porca", "Zona Fantasma", "Saida"])
    )

    assert "tracking.cycle_zone_order references unknown zones: Zona Fantasma." in errors


def test_requires_start_zone_to_match_first_cycle_step() -> None:
    errors = validate_runtime_config(_config(start_zone="Rodas"))

    assert "tracking.start_zone must match the first cycle step 'Porca', got 'Rodas'." in errors


def test_validates_repeat_rules() -> None:
    errors = validate_runtime_config(
        _config(
            cycle_repeat_rules=[
                {
                    "sequence": ["Saida"],
                    "min_repeats": 0,
                    "max_repeats": 3,
                },
                {
                    "sequence": ["Porca", "Rodas"],
                    "min_repeats": 2,
                    "max_repeats": 1,
                },
            ]
        )
    )

    assert "tracking.cycle_repeat_rules[1].sequence cannot include the exit zone 'Saida'." in errors
    assert "tracking.cycle_repeat_rules[1].min_repeats must be at least 1." in errors
    assert "tracking.cycle_repeat_rules[2].sequence must appear contiguously in tracking.cycle_zone_order." in errors
    assert "tracking.cycle_repeat_rules[2].max_repeats must be greater than or equal to min_repeats." in errors
