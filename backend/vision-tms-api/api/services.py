from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import yaml

from api.schemas import (
    BenchConfig,
    BenchConfigResponse,
    BenchZone,
    CameraSettings,
    CheckStatus,
    DetectionSettings,
    Program,
    ProgramStateResponse,
    RuntimeMode,
    RuntimeState,
    RuntimeStatus,
    SettingsResponse,
    SystemCheck,
    SystemSettings,
    TrackingSettings,
)

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"
ROI_PATH = BASE_DIR / "config" / "rois.json"
BENCHES_PATH = BASE_DIR / "config" / "benches.json"
PROGRAM_ID = "industrial-assembly"


class ConfigRepository:
    """Loads and stores the YAML configuration used by the vision pipeline."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self._path = path
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            with self._path.open(encoding="utf-8") as file:
                return yaml.safe_load(file) or {}

    def save(self, config: dict[str, Any]) -> None:
        with self._lock:
            text = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
            self._path.write_text(text, encoding="utf-8")


class RoiService:
    """Validates the stored ROIs against the active tracking configuration."""

    def __init__(self, roi_path: Path = ROI_PATH) -> None:
        self._roi_path = roi_path

    def names(self) -> set[str]:
        if not self._roi_path.exists():
            return set()
        try:
            data = json.loads(self._roi_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return set()
        return {entry.get("name") for entry in data if entry.get("name")}

    def load_zones(self, two_hands_zones: set[str]) -> list[BenchZone]:
        if not self._roi_path.exists():
            return []

        try:
            data = json.loads(self._roi_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        return [
            BenchZone(
                name=entry["name"],
                x=entry["x1"],
                y=entry["y1"],
                width=entry["x2"] - entry["x1"],
                height=entry["y2"] - entry["y1"],
                two_hands=entry["name"] in two_hands_zones,
            )
            for entry in data
        ]

    def save_zones(self, zones: list[BenchZone]) -> None:
        data = [
            {
                "name": zone.name,
                "x1": zone.x,
                "y1": zone.y,
                "x2": zone.x + zone.width,
                "y2": zone.y + zone.height,
            }
            for zone in zones
        ]
        self._roi_path.parent.mkdir(parents=True, exist_ok=True)
        self._roi_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def validate(self, config: dict[str, Any]) -> list[str]:
        roi_names = self.names()
        if not roi_names:
            return ["No ROIs are configured yet."]

        tracking = config["tracking"]
        required = (
            {tracking["exit_zone"]}
            | {tracking.get("start_zone", "")}
            | set(tracking["two_hands_zones"])
            | set(tracking["cycle_zone_order"])
        )
        required.discard("")
        required.discard(None)
        return [f"ROI missing for zone '{zone}'." for zone in sorted(required - roi_names)]


class BenchRepository:
    """Persists named bench layouts and applies one layout to the vision pipeline."""

    def __init__(
        self,
        config_repository: ConfigRepository,
        roi_service: RoiService,
        path: Path = BENCHES_PATH,
    ) -> None:
        self._config_repository = config_repository
        self._roi_service = roi_service
        self._path = path
        self._lock = threading.RLock()

    def load(self) -> BenchConfigResponse:
        with self._lock:
            if not self._path.exists():
                collection = self._migration_collection()
                self._write(collection)
                return collection

            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                collection = self._migration_collection()
                self._write(collection)
                return collection

            try:
                return self._clean_collection(raw)
            except (TypeError, ValueError):
                collection = self._migration_collection()
                self._write(collection)
                return collection

    def save(self, update: BenchConfigResponse) -> BenchConfigResponse:
        with self._lock:
            collection = self._clean_collection(_model_dump(update))
            self._write(collection)
            self.apply(self._active_bench(collection))
            return collection

    def activate(self, bench_id: str | None) -> BenchConfig:
        with self._lock:
            collection = self.load()
            bench = self._bench_by_id(collection, bench_id or collection.active_bench_id)
            collection.active_bench_id = bench.id
            self._write(collection)
            self.apply(bench)
            return bench

    def active_bench(self) -> BenchConfig | None:
        collection = self.load()
        if not collection.benches:
            return None
        return self._active_bench(collection)

    def apply(self, bench: BenchConfig) -> None:
        config = self._config_repository.load()
        tracking = config.setdefault("tracking", {})
        zones = bench.zones

        tracking["zones"] = [zone.name for zone in zones]
        tracking["two_hands_zones"] = [zone.name for zone in zones if zone.two_hands]
        tracking["cycle_zone_order"] = bench.cycle_sequence
        tracking["start_zone"] = bench.start_zone
        tracking["exit_zone"] = bench.end_zone

        self._roi_service.save_zones(zones)
        self._config_repository.save(config)

    def _migration_collection(self) -> BenchConfigResponse:
        config = self._config_repository.load()
        system = config.get("system", {})
        tracking = config.get("tracking", {})
        two_hands_zones = set(tracking.get("two_hands_zones", []))
        zones = self._roi_service.load_zones(two_hands_zones) or self._zones_from_tracking(tracking)

        bench = BenchConfig(
            id="default",
            name=system.get("line_name", "Bancada 1"),
            zones=zones,
            cycle_sequence=tracking.get("cycle_zone_order", []),
            start_zone=tracking.get("start_zone") or self._infer_start_zone(tracking),
            end_zone=tracking.get("exit_zone"),
        )
        return BenchConfigResponse(active_bench_id=bench.id, benches=[bench])

    def _zones_from_tracking(self, tracking: dict[str, Any]) -> list[BenchZone]:
        two_hands_zones = set(tracking.get("two_hands_zones", []))
        zones = []
        for index, name in enumerate(tracking.get("zones", [])):
            zones.append(
                BenchZone(
                    name=name,
                    x=24 + (index % 3) * 150,
                    y=24 + (index // 3) * 110,
                    width=120,
                    height=90,
                    two_hands=name in two_hands_zones,
                )
            )
        return zones

    def _clean_collection(self, raw: dict[str, Any]) -> BenchConfigResponse:
        if "benches" not in raw and "zones" in raw:
            raw = {
                "active_bench_id": "default",
                "benches": [{"id": "default", "name": "Bancada 1", **raw}],
            }

        benches = [self._clean_bench(BenchConfig(**bench)) for bench in raw.get("benches", [])]
        if not benches:
            raise ValueError("At least one bench is required.")

        bench_ids = [bench.id for bench in benches]
        if len(set(bench_ids)) != len(bench_ids):
            raise ValueError("Bench ids must be unique.")

        active_bench_id = (raw.get("active_bench_id") or bench_ids[0]).strip()
        if active_bench_id not in bench_ids:
            raise ValueError("Active bench must be one of the saved benches.")

        return BenchConfigResponse(active_bench_id=active_bench_id, benches=benches)

    def _clean_bench(self, bench: BenchConfig) -> BenchConfig:
        bench_id = bench.id.strip()
        name = bench.name.strip()
        if not bench_id:
            raise ValueError("Every bench must have an id.")
        if not name:
            raise ValueError("Every bench must have a name.")
        if not bench.zones:
            raise ValueError(f"Bench '{name}' must have at least one zone.")

        zones = [
            BenchZone(
                name=zone.name.strip(),
                x=zone.x,
                y=zone.y,
                width=zone.width,
                height=zone.height,
                two_hands=zone.two_hands,
            )
            for zone in bench.zones
        ]
        zone_names = [zone.name for zone in zones]
        if any(not zone_name for zone_name in zone_names):
            raise ValueError(f"Bench '{name}' has a zone without a name.")
        if len(set(zone_names)) != len(zone_names):
            raise ValueError(f"Bench '{name}' has duplicate zone names.")

        for zone in zones:
            if zone.width <= 0 or zone.height <= 0:
                raise ValueError(f"Zone '{zone.name}' must have positive width and height.")
            if zone.x < 0 or zone.y < 0:
                raise ValueError(f"Zone '{zone.name}' cannot have negative coordinates.")

        cycle_sequence = [step.strip() for step in bench.cycle_sequence]
        if not cycle_sequence:
            raise ValueError(f"Bench '{name}' must have a cycle sequence.")

        valid_names = set(zone_names)
        missing_sequence = sorted(set(cycle_sequence) - valid_names)
        if missing_sequence:
            raise ValueError(
                f"Bench '{name}' sequence references unknown zones: {', '.join(missing_sequence)}."
            )

        start_zone = bench.start_zone.strip() if bench.start_zone else zone_names[0]
        end_zone = bench.end_zone.strip() if bench.end_zone else zone_names[-1]
        if start_zone not in valid_names:
            raise ValueError(f"Bench '{name}' start zone must be one of the configured zones.")
        if end_zone not in valid_names:
            raise ValueError(f"Bench '{name}' end zone must be one of the configured zones.")

        return BenchConfig(
            id=bench_id,
            name=name,
            zones=zones,
            cycle_sequence=cycle_sequence,
            start_zone=start_zone,
            end_zone=end_zone,
        )

    def _bench_by_id(self, collection: BenchConfigResponse, bench_id: str | None) -> BenchConfig:
        for bench in collection.benches:
            if bench.id == bench_id:
                return bench
        raise ValueError(f"Unknown bench '{bench_id}'.")

    def _active_bench(self, collection: BenchConfigResponse) -> BenchConfig:
        return self._bench_by_id(collection, collection.active_bench_id)

    def _write(self, collection: BenchConfigResponse) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = _model_dump(collection)
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _infer_start_zone(self, tracking: dict[str, Any]) -> str | None:
        sequence = tracking.get("cycle_zone_order", [])
        if sequence:
            return sequence[0]
        zones = tracking.get("zones", [])
        return zones[0] if zones else None


class ProgramStateRepository:
    """Reads the lightweight state JSON produced by the running monitor process."""

    def __init__(self, config_repository: ConfigRepository) -> None:
        self._config_repository = config_repository

    def load(self) -> ProgramStateResponse:
        state_path = self._state_path()
        if not state_path.exists():
            return ProgramStateResponse()

        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ProgramStateResponse()

        return ProgramStateResponse(**raw)

    def clear(self) -> None:
        try:
            self._state_path().unlink()
        except FileNotFoundError:
            pass

    def _state_path(self) -> Path:
        config = self._config_repository.load()
        raw_path = Path(config.get("dashboard", {}).get("state_path", "dashboard/data/program_state.json"))
        if raw_path.is_absolute():
            return raw_path
        return BASE_DIR / raw_path


class PipelineProcessManager:
    """Owns child processes and exposes command-style start/stop operations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ctx = get_context("spawn")
        self._stop_event = None
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
            frame_queue = self._ctx.Queue(maxsize=2)
            detection_queue = self._ctx.Queue(maxsize=5)
            stop_event = self._ctx.Event()
            self._start(
                mode=RuntimeMode.PROGRAM,
                active_program_id=PROGRAM_ID,
                message="Program is running",
                stop_event=stop_event,
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
        with self._lock:
            self._ensure_idle()
            self._mode = RuntimeMode.CAMERA_TEST
            self._state = RuntimeState.RUNNING
            self._active_program_id = None
            self._message = "Camera stream is running"
            self._last_error = None
            self._stop_event = None
            self._processes = []

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
        processes: list,
    ) -> None:
        self._mode = mode
        self._state = RuntimeState.RUNNING
        self._active_program_id = active_program_id
        self._message = message
        self._last_error = None
        self._stop_event = stop_event
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
        self._stop_event = None
        self._mode = RuntimeMode.IDLE
        self._state = RuntimeState.IDLE
        self._active_program_id = None
        self._message = message


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
            "status": _model_dump(self.status()),
            "program_state": _model_dump(self.program_state()),
        }

    def settings(self) -> SettingsResponse:
        config = self._config_repository.load()
        return SettingsResponse(
            system=SystemSettings(**config.get("system", {})),
            camera=CameraSettings(**config.get("camera", {})),
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
        roi_errors = self._roi_service.validate(config)

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
                name="ROIs",
                value="Ready" if not roi_errors else f"{len(roi_errors)} issue(s)",
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

def _model_dump(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "json"):
        return json.loads(model.json())
    return model.dict()


config_repository = ConfigRepository()
roi_service = RoiService()
bench_repository = BenchRepository(config_repository, roi_service)
program_state_repository = ProgramStateRepository(config_repository)
process_manager = PipelineProcessManager()
system_service = SystemService(
    config_repository=config_repository,
    roi_service=roi_service,
    bench_repository=bench_repository,
    program_state_repository=program_state_repository,
    process_manager=process_manager,
)
