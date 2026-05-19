from __future__ import annotations

from api.bench_repository import BenchRepository
from api.config_repository import ConfigRepository
from api.paths import BASE_DIR, BENCHES_PATH, CONFIG_PATH, PROGRAM_ID, ROI_PATH
from api.pipeline_process_manager import PipelineProcessManager
from api.program_state_repository import ProgramStateRepository
from api.roi_service import RoiService
from api.system_service import SystemService


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


__all__ = [
    "BASE_DIR",
    "BENCHES_PATH",
    "CONFIG_PATH",
    "PROGRAM_ID",
    "ROI_PATH",
    "BenchRepository",
    "ConfigRepository",
    "PipelineProcessManager",
    "ProgramStateRepository",
    "RoiService",
    "SystemService",
    "bench_repository",
    "config_repository",
    "process_manager",
    "program_state_repository",
    "roi_service",
    "system_service",
]
