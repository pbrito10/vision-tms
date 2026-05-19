from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import yaml

from api.paths import CONFIG_PATH


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
