from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


REASON_LEFT_BEFORE_VALIDATION_TIME = "LEFT_BEFORE_VALIDATION_TIME"
REASON_LEFT_BEFORE_STILLNESS = "LEFT_BEFORE_STILLNESS"
REASON_LEFT_BEFORE_SECOND_HAND = "LEFT_BEFORE_SECOND_HAND"
REASON_SECOND_HAND_TIMEOUT = "SECOND_HAND_TIMEOUT"


@dataclass(frozen=True)
class TaskDiagnostic:
    """Diagnostico de uma tentativa que nao chegou a TASK_COMPLETE."""

    zone_name: str
    timestamp: datetime
    duration: timedelta
    cycle_number: int
    reason: str
