from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi import Request
from fastapi.responses import Response, StreamingResponse

from api.camera_stream import CameraSnapshotService, CameraStreamService
from api.program_stream import ProgramFrameStreamService
from api.schemas import (
    BenchConfigResponse,
    CommandResponse,
    HealthResponse,
    Program,
    ProgramStateResponse,
    RuntimeStatus,
    SettingsResponse,
    StartProgramRequest,
)
from api.services import config_repository, system_service

router = APIRouter(prefix="/api")
camera_stream_service = CameraStreamService(config_repository)
camera_snapshot_service = CameraSnapshotService(config_repository)
program_stream_service = ProgramFrameStreamService(config_repository)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/system/status", response_model=RuntimeStatus)
def system_status() -> RuntimeStatus:
    return system_service.status()


@router.get("/programs", response_model=list[Program])
def programs() -> list[Program]:
    return system_service.programs()


@router.post("/program/start", response_model=CommandResponse)
def start_program(request: StartProgramRequest) -> CommandResponse:
    try:
        camera_stream_service.reset()
        status = system_service.start_program(request.program_id, request.bench_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CommandResponse(accepted=True, status=status)


@router.post("/program/stop", response_model=CommandResponse)
def stop_program() -> CommandResponse:
    return CommandResponse(accepted=True, status=system_service.stop_program())


@router.post("/camera-test/start", response_model=CommandResponse)
def start_camera_test() -> CommandResponse:
    try:
        camera_stream_service.reset()
        status = system_service.start_camera_test()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CommandResponse(accepted=True, status=status)


@router.post("/camera-test/stop", response_model=CommandResponse)
def stop_camera_test() -> CommandResponse:
    camera_stream_service.reset()
    return CommandResponse(accepted=True, status=system_service.stop_camera_test())


@router.get("/camera/stream")
def camera_stream() -> StreamingResponse:
    status = system_service.status()
    if status.mode.value == "program":
        raise HTTPException(status_code=409, detail="Camera is being used by the running program.")

    return StreamingResponse(
        camera_stream_service.frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/camera/snapshot")
def camera_snapshot() -> Response:
    status = system_service.status()
    if status.mode.value != "idle":
        raise HTTPException(
            status_code=409,
            detail="Camera is being used by the running program or camera test.",
        )

    try:
        camera_stream_service.stop()
        snapshot = camera_snapshot_service.capture()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=snapshot,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/program/stream")
def program_stream() -> StreamingResponse:
    return StreamingResponse(
        program_stream_service.frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/program/state", response_model=ProgramStateResponse)
def program_state() -> ProgramStateResponse:
    return system_service.program_state()


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    async def event_stream():
        last_payload = ""
        heartbeat_ticks = 0
        while not await request.is_disconnected():
            payload = json.dumps(system_service.live_snapshot(), ensure_ascii=False)
            if payload != last_payload:
                yield f"event: system\ndata: {payload}\n\n"
                last_payload = payload
                heartbeat_ticks = 0
            elif heartbeat_ticks >= 30:
                yield ": keep-alive\n\n"
                heartbeat_ticks = 0
            else:
                heartbeat_ticks += 1
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/bench-config", response_model=BenchConfigResponse)
def bench_config() -> BenchConfigResponse:
    return system_service.bench_config()


@router.put("/bench-config", response_model=BenchConfigResponse)
def update_bench_config(bench_update: BenchConfigResponse) -> BenchConfigResponse:
    try:
        return system_service.update_bench_config(bench_update)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/settings", response_model=SettingsResponse)
def settings() -> SettingsResponse:
    return system_service.settings()
