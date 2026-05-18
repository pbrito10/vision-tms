from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from types import TracebackType

from src.detection.hand_detection import HandDetection
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
]


class DebugLogger:
    """CSV em tempo real com todos os eventos do pipeline.

    Cada linha é descarregada para disco imediatamente — se o processo terminar
    de forma inesperada, os dados até ao último frame ficam preservados.

    Cinco tipos de evento cobrem o ciclo de vida completo:
      ZONE_ENTER / ZONE_EXIT  — transições detetadas pelo ZoneClassifier
      TASK_COMPLETE           — dwell expirou, mão saiu normalmente
      TASK_TIMEOUT            — tarefa fechada por timeout (was_forced=True)
      CYCLE_COMPLETE          — zona de saída concluída; inclui order_ok
    """

    def __init__(self, output_dir: Path, session_start: datetime) -> None:
        filename = f"debug_{session_start.strftime('%Y-%m-%d_%Hh%M')}.csv"

        output_dir.mkdir(parents=True, exist_ok=True)
        self._file          = (output_dir / filename).open("w", newline="", encoding="utf-8")
        self._writer        = csv.DictWriter(self._file, fieldnames=_COLUMNS)
        self._session_start = session_start

        self._writer.writeheader()
        self._file.flush()

    def log_zone_enter(
        self,
        timestamp:     datetime,
        relative_time: timedelta,
        zone_name:     str,
        detection:     HandDetection,
        frame_idx:     int,
    ) -> None:
        """Regista no CSV a entrada de uma mão numa zona."""
        self._write_zone_row("ZONE_ENTER", timestamp, relative_time, zone_name, detection, frame_idx)

    def log_zone_exit(
        self,
        timestamp:     datetime,
        relative_time: timedelta,
        zone_name:     str,
        detection:     HandDetection,
        frame_idx:     int,
    ) -> None:
        """Regista no CSV a saída de uma mão de uma zona."""
        self._write_zone_row("ZONE_EXIT", timestamp, relative_time, zone_name, detection, frame_idx)

    def log_task_complete(self, task_event: TaskEvent) -> None:
        """Regista no CSV uma tarefa concluída normalmente (was_forced=False)."""
        self._write_task_row("TASK_COMPLETE", task_event)

    def log_task_timeout(self, task_event: TaskEvent) -> None:
        """Regista no CSV uma tarefa fechada por timeout (was_forced=True)."""
        self._write_task_row("TASK_TIMEOUT", task_event)

    def log_cycle_complete(self, cycle_result: CycleResult) -> None:
        """Regista no CSV a conclusão de um ciclo completo, incluindo se a sequência foi respeitada."""
        self._write({
            "timestamp_iso":     datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "relative_time_s":   "",
            "event_type":        "CYCLE_COMPLETE",
            "zone":              "",
            "hand":              "",
            "x_px":              "",
            "y_px":              "",
            "confidence":        "",
            "frame_idx":         "",
            "duration_s":        round(cycle_result.duration.total_seconds(), 3),
            "cycle_number":      cycle_result.cycle_number,
            "sequence_in_order": str(cycle_result.sequence_in_order).lower(),
        })

    def _write_zone_row(
        self,
        event_type:    str,
        timestamp:     datetime,
        relative_time: timedelta,
        zone_name:     str,
        detection:     HandDetection,
        frame_idx:     int,
    ) -> None:
        """Escreve uma linha de evento ZONE_ENTER ou ZONE_EXIT.

        O ponto de referência registado é o finger_mcp_centroid, não o pulso,
        consistente com o ponto usado pelo ZoneClassifier para classificação.
        """
        point = detection.keypoints.finger_mcp_centroid()
        self._write({
            "timestamp_iso":     timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "relative_time_s":   round(relative_time.total_seconds(), 3),
            "event_type":        event_type,
            "zone":              zone_name,
            "hand":              detection.hand_side.value,
            "x_px":              point.x,
            "y_px":              point.y,
            "confidence":        round(detection.confidence.value, 4),
            "frame_idx":         frame_idx,
            "duration_s":        "",
            "cycle_number":      "",
            "sequence_in_order": "",
        })

    def _write_task_row(self, event_type: str, task_event: TaskEvent) -> None:
        """Escreve uma linha de evento TASK_COMPLETE ou TASK_TIMEOUT.

        Posição e confiança ficam vazias — a tarefa não está associada a um único ponto.
        """
        relative = task_event.end_time - self._session_start
        self._write({
            "timestamp_iso":     task_event.end_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "relative_time_s":   round(relative.total_seconds(), 3),
            "event_type":        event_type,
            "zone":              task_event.zone_name,
            "hand":              "",
            "x_px":              "",
            "y_px":              "",
            "confidence":        "",
            "frame_idx":         "",
            "duration_s":        round(task_event.duration.total_seconds(), 3),
            "cycle_number":      task_event.cycle_number,
            "sequence_in_order": "",
        })

    def _write(self, row: dict) -> None:
        """Escreve a linha no CSV e faz flush imediato para garantir persistência."""
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        """Fecha o ficheiro CSV. Chamado automaticamente pelo context manager (__exit__)."""
        self._file.close()

    def __enter__(self) -> DebugLogger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val:  BaseException | None,
        exc_tb:   TracebackType | None,
    ) -> None:
        self.close()
