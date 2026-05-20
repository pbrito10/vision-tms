from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from api.bench_repository import BenchRepository
from api.config_repository import ConfigRepository
from api.model_utils import model_dump
from api.paths import BASE_DIR, PROGRAM_ID
from api.pipeline_process_manager import PipelineProcessManager
from api.program_state_repository import ProgramStateRepository
from api.roi_service import RoiService
from api.schemas import (
    BenchConfigResponse,
    CameraSettings,
    CheckStatus,
    DetectionSettings,
    Program,
    ProgramStateResponse,
    RuntimeState,
    RuntimeStatus,
    SettingsResponse,
    SystemCheck,
    SystemSettings,
    TrackingSettings,
)

logger = logging.getLogger(__name__)


class SystemService:
    """Application-facing use cases consumed by the FastAPI routes."""

    def __init__(
        self,
        config_repository: ConfigRepository,
        roi_service: RoiService,
        bench_repository: BenchRepository,
        program_state_repository: ProgramStateRepository,
        process_manager: PipelineProcessManager,
    ) -> None:
        self._config_repository = config_repository
        self._roi_service = roi_service
        self._bench_repository = bench_repository
        self._program_state_repository = program_state_repository
        self._process_manager = process_manager

    def programs(self) -> list[Program]:
        config = self._config_repository.load()
        tracking = config["tracking"]
        return [
            Program(
                id=PROGRAM_ID,
                name=config.get("system", {}).get("program_name", "Industrial Assembly"),
                part_number=config.get("system", {}).get("part_number", "ITR-001"),
                tolerance=f"{tracking['dwell_time_seconds']}s dwell",
                zone_order=tracking["cycle_zone_order"],
                start_zone=tracking.get("start_zone") or self._infer_start_zone(tracking),
                exit_zone=tracking["exit_zone"],
                two_hands_zones=tracking["two_hands_zones"],
            )
        ]

    def program_state(self) -> ProgramStateResponse:
        return self._program_state_repository.load()

    def live_snapshot(self) -> dict[str, Any]:
        return {
            "status": model_dump(self.status()),
            "program_state": model_dump(self.program_state()),
        }

    def settings(self) -> SettingsResponse:
        config = self._config_repository.load()
        return SettingsResponse(
            system=SystemSettings(**config.get("system", {})),
            camera=CameraSettings(**self._effective_camera_settings(config.get("camera", {}))),
            detection=DetectionSettings(**config.get("detection", {})),
            tracking=TrackingSettings(**config.get("tracking", {})),
        )

    def bench_config(self) -> BenchConfigResponse:
        return self._bench_repository.load()

    def update_bench_config(self, update: BenchConfigResponse) -> BenchConfigResponse:
        return self._bench_repository.save(update)

    def status(self) -> RuntimeStatus:
        mode, state, active_program_id, message = self._process_manager.snapshot()
        active_bench = self._bench_repository.active_bench()
        return RuntimeStatus(
            mode=mode,
            run_state=state,
            active_program_id=active_program_id,
            active_bench_id=active_bench.id if active_bench else None,
            active_bench_name=active_bench.name if active_bench else None,
            message=message,
            updated_at=datetime.now().isoformat(timespec="seconds"),
            system_checks=self._checks(state),
        )

    def start_program(self, program_id: str | None, bench_id: str | None) -> RuntimeStatus:
        if program_id and program_id != PROGRAM_ID:
            raise ValueError(f"Unknown program '{program_id}'.")

        self._bench_repository.activate(bench_id)
        config = self._config_repository.load()
        errors = self._roi_service.validate(config)
        if errors:
            raise RuntimeError(" ".join(errors))

        self._clear_program_frame(config)
        self._program_state_repository.clear()
        self._process_manager.start_program(config)
        return self.status()

    def stop_program(self) -> RuntimeStatus:
        self._process_manager.stop()
        return self.status()

    def start_camera_test(self) -> RuntimeStatus:
        self._process_manager.start_camera_test(self._config_repository.load())
        return self.status()

    def stop_camera_test(self) -> RuntimeStatus:
        self._process_manager.stop()
        return self.status()

    def _checks(self, state: RuntimeState) -> list[SystemCheck]:
        config = self._config_repository.load()
        bench_config = self._bench_repository.load()
        roi_errors = self._roi_service.validate(config)
        bench_ready = bool(bench_config.benches)
        roi_value = "Ready" if not roi_errors else roi_errors[0]
        if len(roi_errors) > 1:
            roi_value = f"{len(roi_errors)} issue(s)"

        return [
            SystemCheck(
                name="API",
                value="Online",
                status=CheckStatus.OK,
            ),
            SystemCheck(
                name="Runtime",
                value=state.value,
                status=CheckStatus.OK if state != RuntimeState.ERROR else CheckStatus.ERROR,
            ),
            SystemCheck(
                name="Benches",
                value="Ready" if bench_ready else "No local bench configuration",
                status=CheckStatus.OK if bench_ready else CheckStatus.WARNING,
            ),
            SystemCheck(
                name="ROIs",
                value=roi_value,
                status=CheckStatus.OK if not roi_errors else CheckStatus.WARNING,
            ),
        ]

    def _infer_start_zone(self, tracking: dict[str, Any]) -> str | None:
        sequence = tracking.get("cycle_zone_order", [])
        if sequence:
            return sequence[0]
        zones = tracking.get("zones", [])
        return zones[0] if zones else None

    def _clear_program_frame(self, config: dict[str, Any]) -> None:
        raw_path = Path(config.get("dashboard", {}).get("frame_path", "dashboard/data/program_frame.jpg"))
        frame_path = raw_path if raw_path.is_absolute() else BASE_DIR / raw_path
        try:
            frame_path.unlink()
        except FileNotFoundError:
            pass

    def _effective_camera_settings(self, camera_config: dict[str, Any]) -> dict[str, Any]:
        settings = dict(camera_config)
        perspective_path = settings.get("perspective_path")
        if not perspective_path:
            return settings

        try:
            import numpy as np

            path = Path(perspective_path)
            if not path.is_absolute():
                path = BASE_DIR / path
            if not path.exists():
                return settings

            output_width, output_height = np.load(path)["output_size"].tolist()
            settings["width"] = int(output_width)
            settings["height"] = int(output_height)
        except Exception:
            logger.exception("Failed to read perspective output size from %s", perspective_path)

        return settings
