from __future__ import annotations

import csv
from datetime import datetime, timedelta

from src.events.debug_logger import DebugLogger
from src.tracking.cycle_result import CycleResult
from src.tracking.task_event import TaskEvent

_T0 = datetime(2026, 5, 26, 15, 57, 0)


def _read_rows(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_final_csv_is_rewritten_in_chronological_event_order(tmp_path) -> None:
    logger = DebugLogger(tmp_path, _T0)
    logger.log_detection_gap(
        _T0 + timedelta(seconds=10),
        timedelta(seconds=10),
        timedelta(seconds=1),
        "right",
    )
    logger.log_task_complete(
        TaskEvent.create(
            zone_name="porca",
            start_time=_T0 + timedelta(seconds=2),
            end_time=_T0 + timedelta(seconds=3),
            cycle_number=1,
            was_forced=False,
        )
    )

    path = logger.path
    logger.close()

    rows = _read_rows(path)

    assert [row["event_type"] for row in rows] == ["TASK_COMPLETE", "DETECTION_GAP"]
    assert [row["write_order"] for row in rows] == ["2", "1"]


def test_task_rows_include_start_time_for_duration_audit(tmp_path) -> None:
    logger = DebugLogger(tmp_path, _T0)
    logger.log_task_complete(
        TaskEvent.create(
            zone_name="porca",
            start_time=_T0 + timedelta(seconds=4),
            end_time=_T0 + timedelta(seconds=5.25),
            cycle_number=1,
            was_forced=False,
        )
    )

    path = logger.path
    logger.close()

    row = _read_rows(path)[0]

    assert row["timestamp_iso"] == "2026-05-26T15:57:05.250"
    assert row["relative_time_s"] == "5.25"
    assert row["duration_s"] == "1.25"
    assert row["task_start_iso"] == "2026-05-26T15:57:04.000"
    assert row["task_start_relative_time_s"] == "4.0"


def test_cycle_complete_uses_cycle_end_time(tmp_path) -> None:
    logger = DebugLogger(tmp_path, _T0)
    logger.log_cycle_complete(
        CycleResult(
            start_time=_T0 + timedelta(seconds=1),
            end_time=_T0 + timedelta(seconds=4),
            duration=timedelta(seconds=3),
            cycle_number=1,
            sequence_in_order=True,
            actual_sequence=["porca", "saida"],
            expected_sequence=["porca", "saida"],
        )
    )

    path = logger.path
    logger.close()

    row = _read_rows(path)[0]

    assert row["timestamp_iso"] == "2026-05-26T15:57:04.000"
    assert row["relative_time_s"] == "4.0"
