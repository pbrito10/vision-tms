from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.roi.roi_collection import RoiCollection

_SCHEMA_VERSION = 1
_SNAPSHOT_SUFFIX = "_config.json"


def snapshot_path_for_csv(csv_path: Path) -> Path:
    return csv_path.with_name(f"{csv_path.stem}{_SNAPSHOT_SUFFIX}")


def write_session_config_snapshot(
    csv_path: Path,
    config: dict[str, Any],
    rois: RoiCollection,
) -> Path:
    """Guarda a configuracao e as ROIs usadas pela sessao."""
    path = snapshot_path_for_csv(csv_path)
    data = {
        "schema_version": _SCHEMA_VERSION,
        "source_csv": csv_path.name,
        "config": deepcopy(config),
        "rois": [roi.to_dict() for roi in rois.all()],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_session_config_snapshot(csv_path: Path) -> dict[str, Any] | None:
    path = snapshot_path_for_csv(csv_path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def expected_order_from_snapshot(csv_path: Path) -> list[str] | None:
    snapshot = load_session_config_snapshot(csv_path)
    if snapshot is None:
        return None

    config = snapshot.get("config")
    if not isinstance(config, dict):
        return None

    tracking = config.get("tracking")
    if not isinstance(tracking, dict):
        return None

    order = tracking.get("cycle_zone_order")
    if not isinstance(order, list) or not all(isinstance(zone, str) for zone in order):
        return None

    return list(order)
