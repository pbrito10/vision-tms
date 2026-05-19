from __future__ import annotations

import json
from pathlib import Path

from api.config_repository import ConfigRepository
from api.paths import BASE_DIR
from api.schemas import ProgramStateResponse


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
