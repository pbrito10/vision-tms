from datetime import datetime, timedelta

from src.output.excel_exporter import _cycle_diagnosis, _format_sequence
from src.tracking.cycle_result import CycleResult
from src.tracking.order_matching import RESULT_INCOMPLETE, RESULT_IN_ORDER


def test_format_sequence_uses_plain_task_names() -> None:
    assert _format_sequence(["Chassi", "Montagem", "Porca"]) == "Chassi, Montagem, Porca"


def test_format_sequence_removes_leading_arrows_from_task_names() -> None:
    assert _format_sequence(["-> Chassi", " -> Montagem", "Porca"]) == "Chassi, Montagem, Porca"


def test_format_sequence_skips_empty_steps() -> None:
    assert _format_sequence(["", "  ", "Chassi"]) == "Chassi"


def test_cycle_diagnosis_trusts_tracker_result_for_repeated_wheels_block() -> None:
    start = datetime(2026, 1, 1, 12, 0, 0)
    cycle_result = CycleResult(
        start_time=start,
        end_time=start + timedelta(seconds=30),
        duration=timedelta(seconds=30),
        cycle_number=1,
        sequence_in_order=True,
        actual_sequence=[
            "porca",
            "montagem",
            "chassi inferior",
            "montagem",
            "rodas",
            "montagem",
            "rodas",
            "montagem",
            "chassi superior",
            "montagem",
            "parafuso",
            "montagem",
            "saida",
        ],
        expected_sequence=[
            "porca",
            "montagem",
            "chassi inferior",
            "montagem",
            "rodas",
            "montagem",
            "chassi superior",
            "montagem",
            "parafuso",
            "montagem",
            "saida",
        ],
    )

    diagnosis = _cycle_diagnosis(cycle_result)

    assert diagnosis.result == RESULT_IN_ORDER
    assert diagnosis.problem == "Sem problema detetado."


def test_cycle_diagnosis_reports_missing_exit_after_valid_repeated_wheels_block() -> None:
    start = datetime(2026, 5, 27, 14, 9, 10)
    cycle_result = CycleResult(
        start_time=start,
        end_time=start + timedelta(seconds=48),
        duration=timedelta(seconds=48),
        cycle_number=3,
        sequence_in_order=False,
        actual_sequence=[
            "porca",
            "montagem",
            "chassi inferior",
            "montagem",
            "rodas",
            "montagem",
            "rodas",
            "montagem",
            "chassi superior",
            "montagem",
            "parafuso",
            "montagem",
        ],
        expected_sequence=[
            "porca",
            "montagem",
            "chassi inferior",
            "montagem",
            "rodas",
            "montagem",
            "chassi superior",
            "montagem",
            "parafuso",
            "montagem",
            "saida",
        ],
    )

    diagnosis = _cycle_diagnosis(cycle_result)

    assert diagnosis.result == RESULT_INCOMPLETE
    assert diagnosis.problem == 'Faltaram zonas esperadas: "saida".'
