from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.paths import ROI_PATH
from api.schemas import BenchZone


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
