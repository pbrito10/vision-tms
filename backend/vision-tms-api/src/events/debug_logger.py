from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from types import TracebackType

from src.detection.hand_detection import HandDetection
from src.output.session_output import output_stamp
from src.tracking.cycle_result import CycleResult
from src.tracking.task_event import TaskEvent

_COLUMNS = [
    "timestamp_iso",
    "relative_time_s",
    "event_type",
    "zone",
    "hand",
    "x_px",
    "y_px",
    "confidence",
    "frame_idx",
    "duration_s",
    "cycle_number",
    "sequence_in_order",
    "actual_sequence",
    "is_anomaly",
    "reason",
    "task_start_iso",
    "task_start_relative_time_s",
    "logged_at_iso",
    "write_order",
]


class DebugLogger:
    """CSV em tempo real com os eventos do pipeline."""

    def __init__(self, output_dir: Path, session_start: datetime) -> None:
        filename = f"debug_{output_stamp(output_dir, session_start)}.csv"

        output_dir.mkdir(parents=True, exist_ok=True)
        self._path = output_dir / filename
        self._file = self._path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=_COLUMNS)
        self._session_start = session_start
        self._rows: list[dict] = []
        self._write_order = 0

        self._writer.writeheader()
        self._file.flush()

    @property
    def path(self) -> Path:
        return self._path

    def log_zone_enter(
        self,
        timestamp: datetime,
        relative_time: timedelta,
        zone_name: str,
        detection: HandDetection,
        frame_idx: int,
    ) -> None:
        self._write_zone_row("ZONE_ENTER", timestamp, relative_time, zone_name, detection, frame_idx)

    def log_zone_exit(
        self,
        timestamp: datetime,
        relative_time: timedelta,
        zone_name: str,
        detection: HandDetection,
        frame_idx: int,
    ) -> None:
        self._write_zone_row("ZONE_EXIT", timestamp, relative_time, zone_name, detection, frame_idx)

    def log_task_complete(self, task_event: TaskEvent) -> None:
        self._write_task_row("TASK_COMPLETE", task_event)

    def log_task_timeout(self, task_event: TaskEvent) -> None:
        self._write_task_row("TASK_TIMEOUT", task_event)

    def log_task_rejected(self, diagnostic) -> None:
        relative = diagnostic.timestamp - self._session_start
        row = self._empty_row()
        row.update({
            "timestamp_iso": diagnostic.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "relative_time_s": round(relative.total_seconds(), 3),
            "event_type": "TASK_REJECTED",
            "zone": diagnostic.zone_name,
            "duration_s": round(diagnostic.duration.total_seconds(), 3),
            "cycle_number": diagnostic.cycle_number,
            "reason": diagnostic.reason,
        })
        self._write(row)

    def log_detection_gap(
        self,
        gap_start: datetime,
        relative: timedelta,
        duration: timedelta,
        hand_side: str | None = None,
    ) -> None:
        row = self._empty_row()
        row.update({
            "timestamp_iso": gap_start.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "relative_time_s": round(relative.total_seconds(), 3),
            "event_type": "DETECTION_GAP",
            "hand": hand_side or "",
            "duration_s": round(duration.total_seconds(), 3),
        })
        self._write(row)

    def log_cycle_complete(self, cycle_result: CycleResult) -> None:
        relative = cycle_result.end_time - self._session_start
        row = self._empty_row()
        row.update({
            "timestamp_iso": self._format_timestamp(cycle_result.end_time),
            "relative_time_s": round(relative.total_seconds(), 3),
            "event_type": "CYCLE_COMPLETE",
            "duration_s": round(cycle_result.duration.total_seconds(), 3),
            "cycle_number": cycle_result.cycle_number,
            "sequence_in_order": str(cycle_result.sequence_in_order).lower(),
            "actual_sequence": " -> ".join(cycle_result.actual_sequence),
            "is_anomaly": str(cycle_result.is_anomaly).lower(),
        })
        self._write(row)

    def _write_zone_row(
        self,
        event_type: str,
        timestamp: datetime,
        relative_time: timedelta,
        zone_name: str,
        detection: HandDetection,
        frame_idx: int,
    ) -> None:
        point = detection.keypoints.finger_mcp_centroid()
        row = self._empty_row()
        row.update({
            "timestamp_iso": timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "relative_time_s": round(relative_time.total_seconds(), 3),
            "event_type": event_type,
            "zone": zone_name,
            "hand": detection.hand_side.value,
            "x_px": point.x,
            "y_px": point.y,
            "confidence": round(detection.confidence.value, 4),
            "frame_idx": frame_idx,
        })
        self._write(row)

    def _write_task_row(self, event_type: str, task_event: TaskEvent) -> None:
        start_relative = task_event.start_time - self._session_start
        end_relative = task_event.end_time - self._session_start
        row = self._empty_row()
        row.update({
            "timestamp_iso": self._format_timestamp(task_event.end_time),
            "relative_time_s": round(end_relative.total_seconds(), 3),
            "event_type": event_type,
            "zone": task_event.zone_name,
            "duration_s": round(task_event.duration.total_seconds(), 3),
            "cycle_number": task_event.cycle_number,
            "task_start_iso": self._format_timestamp(task_event.start_time),
            "task_start_relative_time_s": round(start_relative.total_seconds(), 3),
        })
        self._write(row)

    def _empty_row(self) -> dict:
        return {col: "" for col in _COLUMNS}

    def _write(self, row: dict) -> None:
        self._write_order += 1
        row["logged_at_iso"] = self._format_timestamp(datetime.now())
        row["write_order"] = self._write_order
        self._rows.append(dict(row))
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        self._rewrite_chronological()
        self._file.close()

    def _rewrite_chronological(self) -> None:
        self._file.seek(0)
        self._file.truncate()
        writer = csv.DictWriter(self._file, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerows(sorted(self._rows, key=self._sort_key))
        self._file.flush()

    def _sort_key(self, row: dict) -> tuple[str, int]:
        return (str(row.get("timestamp_iso") or ""), int(row.get("write_order") or 0))

    def _format_timestamp(self, timestamp: datetime) -> str:
        return timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

    def __enter__(self) -> DebugLogger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
