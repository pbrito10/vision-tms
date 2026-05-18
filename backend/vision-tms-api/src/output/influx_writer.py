from __future__ import annotations

import logging
import math
import os
import queue
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from src.output.metrics_snapshot import MetricsSnapshot
from src.tracking.cycle_result import CycleResult
from src.tracking.task_event import TaskEvent

logger = logging.getLogger(__name__)


class NullInfluxWriter:
    def write(self, snapshot: MetricsSnapshot) -> None:
        pass

    def write_task_event(self, event: TaskEvent) -> None:
        pass

    def write_cycle_result(self, result: CycleResult) -> None:
        pass

    def close(self) -> None:
        pass


class InfluxWriter:
    """Writes live metrics to InfluxDB v2 without blocking the vision pipeline."""

    def __init__(self, config: dict[str, Any], session_start: datetime) -> None:
        self._line_name = config.get("system", {}).get("line_name", "vision-tms")
        self._program_name = config.get("system", {}).get("program_name", "industrial-assembly")
        self._session_id = session_start.strftime("%Y%m%d_%H%M%S")

        influx_config = config.get("influxdb", {})
        self._url = influx_config["url"].rstrip("/")
        self._org = influx_config["org"]
        self._bucket = influx_config["bucket"]
        self._token = influx_config.get("token") or os.environ.get(influx_config.get("token_env", "INFLUXDB_TOKEN"), "")
        self._prefix = influx_config.get("measurement_prefix", "vision_tms")
        self._batch_size = int(influx_config.get("batch_size", 50))
        self._flush_interval_s = float(influx_config.get("flush_interval_seconds", 1.0))
        self._timeout_s = float(influx_config.get("timeout_seconds", 1.5))

        self._queue: queue.Queue[str] = queue.Queue(maxsize=int(influx_config.get("queue_size", 1000)))
        self._stop_event = threading.Event()
        self._last_error_log = 0.0
        self._worker = threading.Thread(target=self._run, name="influx-writer", daemon=True)
        self._worker.start()

    @classmethod
    def from_config(cls, config: dict[str, Any], session_start: datetime) -> "InfluxWriter | NullInfluxWriter":
        influx_config = config.get("influxdb", {})
        if not influx_config.get("enabled", False):
            return NullInfluxWriter()

        required = ("url", "org", "bucket")
        missing = [key for key in required if not influx_config.get(key)]
        token = influx_config.get("token") or os.environ.get(influx_config.get("token_env", "INFLUXDB_TOKEN"), "")
        if missing or not token:
            logger.warning(
                "InfluxDB disabled: missing %s.",
                ", ".join(missing + ([] if token else ["token"])),
            )
            return NullInfluxWriter()

        return cls(config, session_start)

    def write(self, snapshot: MetricsSnapshot) -> None:
        timestamp = _timestamp_ns(snapshot.captured_at)
        cycle = snapshot.cycle_metrics
        cycle_count = cycle.count()
        fields = {
            "session_duration_s": snapshot.session_duration.total_seconds(),
            "cycle_count": cycle_count,
            "cycle_ok_count": cycle.count_in_order(),
            "cycle_review_count": cycle.count_out_of_order(),
            "productive_pct": snapshot.productive_percentage,
            "transition_pct": snapshot.transition_percentage,
            "interruption_pct": snapshot.interruption_percentage,
            "cycle_avg_s": 0.0,
        }
        if cycle_count > 0:
            fields.update({
                "cycle_avg_s": cycle.average().total_seconds(),
            })

        self._enqueue(_line(
            measurement=f"{self._prefix}_session",
            tags=self._base_tags(),
            fields=fields,
            timestamp=timestamp,
        ))

        for zone_name, metrics in snapshot.task_metrics.items():
            if metrics.count() == 0:
                continue
            self._enqueue(_line(
                measurement=f"{self._prefix}_zone",
                tags={**self._base_tags(), "zone": zone_name},
                fields={
                    "avg_s": metrics.average().total_seconds(),
                },
                timestamp=timestamp,
            ))

    def write_task_event(self, event: TaskEvent) -> None:
        self._enqueue(_line(
            measurement=f"{self._prefix}_task",
            tags={**self._base_tags(), "zone": event.zone_name, "cycle": str(event.cycle_number)},
            fields={
                "duration_s": event.duration.total_seconds(),
                "was_forced": event.was_forced,
            },
            timestamp=_timestamp_ns(event.end_time),
        ))

    def write_cycle_result(self, result: CycleResult) -> None:
        self._enqueue(_line(
            measurement=f"{self._prefix}_cycle",
            tags={**self._base_tags(), "cycle": str(result.cycle_number)},
            fields={
                "duration_s": result.duration.total_seconds(),
                "sequence_in_order": result.sequence_in_order,
                "step_count": len(result.actual_sequence),
            },
            timestamp=time.time_ns(),
        ))

    def close(self) -> None:
        self._stop_event.set()
        self._worker.join(timeout=2)

    def _base_tags(self) -> dict[str, str]:
        return {
            "line": self._line_name,
            "program": self._program_name,
            "session": self._session_id,
        }

    def _enqueue(self, line: str) -> None:
        try:
            self._queue.put_nowait(line)
        except queue.Full:
            self._log_error("InfluxDB queue full; dropping metric.")

    def _run(self) -> None:
        batch: list[str] = []
        last_flush = time.monotonic()

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                batch.append(self._queue.get(timeout=0.2))
            except queue.Empty:
                pass

            should_flush = (
                len(batch) >= self._batch_size
                or (batch and time.monotonic() - last_flush >= self._flush_interval_s)
                or (batch and self._stop_event.is_set())
            )
            if should_flush:
                self._post(batch)
                batch = []
                last_flush = time.monotonic()

    def _post(self, lines: list[str]) -> None:
        query = urllib.parse.urlencode({
            "org": self._org,
            "bucket": self._bucket,
            "precision": "ns",
        })
        request = urllib.request.Request(
            url=f"{self._url}/api/v2/write?{query}",
            data="\n".join(lines).encode("utf-8"),
            headers={
                "Authorization": f"Token {self._token}",
                "Content-Type": "text/plain; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                if response.status >= 300:
                    self._log_error(f"InfluxDB write failed with HTTP {response.status}.")
        except Exception as exc:
            self._log_error(f"InfluxDB write failed: {exc}")

    def _log_error(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_error_log >= 10:
            logger.error(message)
            self._last_error_log = now


def _timestamp_ns(value: datetime) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _line(measurement: str, tags: dict[str, str], fields: dict[str, Any], timestamp: int) -> str:
    tag_text = ",".join(f"{_escape_tag(key)}={_escape_tag(value)}" for key, value in tags.items())
    field_text = ",".join(
        f"{_escape_field(key)}={_field_value(value)}"
        for key, value in fields.items()
        if _is_valid_field(value)
    )
    return f"{_escape_measurement(measurement)},{tag_text} {field_text} {timestamp}"


def _is_valid_field(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def _field_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value}i"
    if isinstance(value, float):
        return str(value)
    return f'"{str(value).replace(chr(34), chr(92) + chr(34))}"'


def _escape_measurement(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


def _escape_tag(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")


def _escape_field(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")
