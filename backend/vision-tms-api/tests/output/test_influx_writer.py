from __future__ import annotations

from datetime import datetime, timedelta

from src.output.influx_writer import InfluxWriter, _timestamp_ns
from src.tracking.cycle_result import CycleResult


def test_cycle_result_line_uses_cycle_end_timestamp() -> None:
    end_time = datetime(2026, 5, 26, 15, 57, 4)
    result = CycleResult(
        start_time=end_time - timedelta(seconds=3),
        end_time=end_time,
        duration=timedelta(seconds=3),
        cycle_number=1,
        sequence_in_order=True,
        actual_sequence=["porca", "saida"],
        expected_sequence=["porca", "saida"],
    )
    captured = []
    writer = InfluxWriter.__new__(InfluxWriter)
    writer._prefix = "vision_tms"
    writer._line_name = "Line A-07"
    writer._program_name = "Industrial Assembly"
    writer._session_id = "20260526_155700"
    writer._enqueue = captured.append

    writer.write_cycle_result(result)

    assert len(captured) == 1
    assert captured[0].endswith(f" {_timestamp_ns(end_time)}")
