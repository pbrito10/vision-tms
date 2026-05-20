from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import threading
import time
from multiprocessing import get_context
from typing import Any

from api.paths import PROGRAM_ID, ROI_PATH
from api.schemas import RuntimeMode, RuntimeState


class PipelineProcessManager:
    """Owns child processes and exposes command-style start/stop operations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ctx = get_context("spawn")
        self._stop_event = None
        self._queues = []
        self._processes = []
        self._mode = RuntimeMode.IDLE
        self._state = RuntimeState.IDLE
        self._active_program_id: str | None = None
        self._message = "Ready"
        self._last_error: str | None = None

    def start_program(self, config: dict[str, Any]) -> None:
        from process_entrypoints import run_camera, run_detector, run_pipeline

        with self._lock:
            self._ensure_idle()
            config = self._runtime_config(config)
            frame_queue = self._ctx.Queue(maxsize=2)
            detection_queue = self._ctx.Queue(maxsize=5)
            stop_event = self._ctx.Event()
            queues = [frame_queue, detection_queue]
            self._start(
                mode=RuntimeMode.PROGRAM,
                active_program_id=PROGRAM_ID,
                message="Program is running",
                stop_event=stop_event,
                queues=queues,
                processes=[
                    self._ctx.Process(
                        target=run_camera,
                        name="camera",
                        args=(frame_queue, stop_event, config),
                    ),
                    self._ctx.Process(
                        target=run_detector,
                        name="detector",
                        args=(frame_queue, detection_queue, stop_event, config),
                    ),
                    self._ctx.Process(
                        target=run_pipeline,
                        name="pipeline",
                        args=(detection_queue, stop_event, config, str(ROI_PATH)),
                    ),
                ],
            )

    def start_camera_test(self, config: dict[str, Any]) -> None:
        from process_entrypoints import run_camera, run_detector, run_preview_pipeline

        with self._lock:
            self._ensure_idle()
            config = self._runtime_config(config)
            frame_queue = self._ctx.Queue(maxsize=2)
            detection_queue = self._ctx.Queue(maxsize=5)
            stop_event = self._ctx.Event()
            queues = [frame_queue, detection_queue]
            self._start(
                mode=RuntimeMode.CAMERA_TEST,
                active_program_id=None,
                message="Camera stream is running",
                stop_event=stop_event,
                queues=queues,
                processes=[
                    self._ctx.Process(
                        target=run_camera,
                        name="camera",
                        args=(frame_queue, stop_event, config),
                    ),
                    self._ctx.Process(
                        target=run_detector,
                        name="detector",
                        args=(frame_queue, detection_queue, stop_event, config),
                    ),
                    self._ctx.Process(
                        target=run_preview_pipeline,
                        name="preview",
                        args=(detection_queue, stop_event, config, str(ROI_PATH)),
                    ),
                ],
            )

    def stop(self) -> None:
        with self._lock:
            if self._state == RuntimeState.IDLE:
                return
            self._state = RuntimeState.STOPPING
            if self._stop_event is not None:
                self._stop_event.set()

            for process in self._processes:
                process.join(timeout=3)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)

            self._clear_runtime("Stopped")

    def snapshot(self) -> tuple[RuntimeMode, RuntimeState, str | None, str]:
        with self._lock:
            self._refresh_state()
            return self._mode, self._state, self._active_program_id, self._message

    def _start(
        self,
        *,
        mode: RuntimeMode,
        active_program_id: str | None,
        message: str,
        stop_event,
        queues: list,
        processes: list,
    ) -> None:
        self._mode = mode
        self._state = RuntimeState.RUNNING
        self._active_program_id = active_program_id
        self._message = message
        self._last_error = None
        self._stop_event = stop_event
        self._queues = queues
        self._processes = processes

        try:
            for process in self._processes:
                process.start()
                time.sleep(0.25)
        except Exception as exc:
            self._last_error = str(exc)
            if self._stop_event is not None:
                self._stop_event.set()
            for process in self._processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)
            self._clear_runtime("Failed to start")
            raise

    def _ensure_idle(self) -> None:
        self._refresh_state()
        if self._state != RuntimeState.IDLE:
            raise RuntimeError("Another runtime mode is already active.")

    def _runtime_config(self, config: dict[str, Any]) -> dict[str, Any]:
        runtime_config = deepcopy(config)
        session_started_at = datetime.now()
        runtime_config["_runtime"] = {
            "session_started_at": session_started_at.isoformat(timespec="microseconds"),
        }
        return runtime_config

    def _refresh_state(self) -> None:
        if self._state != RuntimeState.RUNNING:
            return
        stopped = [process for process in self._processes if not process.is_alive()]
        if stopped:
            names = ", ".join(process.name for process in stopped)
            message = self._last_error or f"Process stopped: {names}"
            if self._stop_event is not None:
                self._stop_event.set()
            for process in self._processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)
            self._clear_runtime(message)

    def _clear_runtime(self, message: str) -> None:
        self._processes = []
        self._queues = []
        self._stop_event = None
        self._mode = RuntimeMode.IDLE
        self._state = RuntimeState.IDLE
        self._active_program_id = None
        self._message = message
