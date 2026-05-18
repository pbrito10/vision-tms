from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RuntimeState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class RuntimeMode(str, Enum):
    IDLE = "idle"
    PROGRAM = "program"
    CAMERA_TEST = "camera_test"


class CheckStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "vision-tms-api"


class SystemCheck(BaseModel):
    name: str
    value: str
    status: CheckStatus


class Program(BaseModel):
    id: str
    name: str
    part_number: str
    tolerance: str
    zone_order: list[str]
    start_zone: str | None = None
    exit_zone: str
    two_hands_zones: list[str]


class RuntimeStatus(BaseModel):
    mode: RuntimeMode
    run_state: RuntimeState
    active_program_id: str | None = None
    active_bench_id: str | None = None
    active_bench_name: str | None = None
    message: str
    updated_at: str
    system_checks: list[SystemCheck]


class CameraSettings(BaseModel):
    index: int = 0
    width: int = 640
    height: int = 480
    flip: bool = False


class DetectionSettings(BaseModel):
    max_num_hands: int = 2
    min_detection_confidence: float = 0.7
    min_tracking_confidence: float = 0.7


class TrackingSettings(BaseModel):
    dwell_time_seconds: float = 0.5
    task_timeout_seconds: float = 30.0
    stillness_threshold_px: float = 5.0
    zones: list[str] = Field(default_factory=list)
    two_hands_zones: list[str] = Field(default_factory=list)
    cycle_zone_order: list[str] = Field(default_factory=list)
    start_zone: str | None = None
    exit_zone: str = ""


class SystemSettings(BaseModel):
    line_name: str = "Line A-07"
    program_name: str = "Industrial Assembly"
    part_number: str = "ITR-001"
    camera_serial: str = "CAM-TMS-01-9482"


class SettingsResponse(BaseModel):
    system: SystemSettings = Field(default_factory=SystemSettings)
    camera: CameraSettings = Field(default_factory=CameraSettings)
    detection: DetectionSettings = Field(default_factory=DetectionSettings)
    tracking: TrackingSettings = Field(default_factory=TrackingSettings)


class BenchZone(BaseModel):
    name: str
    x: int
    y: int
    width: int
    height: int
    two_hands: bool = False


class BenchConfig(BaseModel):
    id: str
    name: str
    zones: list[BenchZone] = Field(default_factory=list)
    cycle_sequence: list[str] = Field(default_factory=list)
    start_zone: str | None = None
    end_zone: str | None = None


class BenchConfigResponse(BaseModel):
    active_bench_id: str | None = None
    benches: list[BenchConfig] = Field(default_factory=list)


class ProgramStateResponse(BaseModel):
    captured_at: str | None = None
    current_zone: str | None = None
    current_step_index: int | None = None
    completed_steps: list[str] = Field(default_factory=list)
    expected_sequence: list[str] = Field(default_factory=list)
    cycle_number: int = 1


class StartProgramRequest(BaseModel):
    program_id: str | None = "industrial-assembly"
    bench_id: str | None = None


class CommandResponse(BaseModel):
    accepted: bool
    status: RuntimeStatus
