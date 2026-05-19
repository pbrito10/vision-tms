from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from api.config_repository import ConfigRepository
from api.model_utils import model_dump
from api.paths import BENCHES_PATH
from api.roi_service import RoiService
from api.schemas import BenchConfig, BenchConfigResponse, BenchZone


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
            collection = self._clean_collection(model_dump(update))
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
        data = model_dump(collection)
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _infer_start_zone(self, tracking: dict[str, Any]) -> str | None:
        sequence = tracking.get("cycle_zone_order", [])
        if sequence:
            return sequence[0]
        zones = tracking.get("zones", [])
        return zones[0] if zones else None
