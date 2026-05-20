from __future__ import annotations

from src.tracking.task_event import TaskEvent


class ConsecutiveTaskMerger:
    """Coalesces consecutive normal task events from the same physical zone.

    A brief detection loss can split one operator action into two TaskEvents.
    Keeping one pending event lets us merge a repeated zone before it reaches
    metrics, Excel, InfluxDB or cycle validation.
    """

    def __init__(self) -> None:
        self._pending: TaskEvent | None = None

    def push(self, event: TaskEvent) -> TaskEvent | None:
        if self._pending is None:
            self._pending = event
            return None

        if self._should_merge(self._pending, event):
            self._pending = TaskEvent.create(
                zone_name=self._pending.zone_name,
                start_time=self._pending.start_time,
                end_time=event.end_time,
                cycle_number=self._pending.cycle_number,
                was_forced=False,
            )
            return None

        completed = self._pending
        self._pending = event
        return completed

    def flush(self) -> TaskEvent | None:
        completed = self._pending
        self._pending = None
        return completed

    def _should_merge(self, previous: TaskEvent, current: TaskEvent) -> bool:
        return (
            previous.zone_name == current.zone_name
            and not previous.was_forced
            and not current.was_forced
        )
