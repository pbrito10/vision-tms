from __future__ import annotations

from api.bench_repository import BenchRepository
from api.config_repository import ConfigRepository
from api.roi_service import RoiService
from api.schemas import BenchConfig, BenchZone


def _repository(tmp_path):
    config_repository = ConfigRepository(tmp_path / "settings.yaml")
    config_repository.save({
        "camera": {"width": 640, "height": 480, "perspective_path": ""},
        "tracking": {
            "assembly_zone": "Montagem",
            "assembly_task_labels": {
                "Porcas": "Aperto Porcas",
                "Zona Fantasma": "Montagem Fantasma",
            },
        },
    })
    return BenchRepository(
        config_repository=config_repository,
        roi_service=RoiService(tmp_path / "rois.json"),
        path=tmp_path / "benches.json",
    ), config_repository


def test_apply_derives_assembly_labels_from_active_bench(tmp_path) -> None:
    repository, config_repository = _repository(tmp_path)

    repository.apply(
        BenchConfig(
            id="line-a",
            name="Linha A",
            zones=[
                BenchZone(name="Porcas", x=0, y=0, width=10, height=10),
                BenchZone(name="Rodas", x=10, y=0, width=10, height=10),
                BenchZone(name="Montagem", x=20, y=0, width=10, height=10, two_hands=True),
                BenchZone(name="Saida", x=30, y=0, width=10, height=10),
            ],
            cycle_sequence=["Porcas", "Montagem", "Rodas", "Montagem", "Saida"],
            start_zone="Porcas",
            end_zone="Saida",
        )
    )

    tracking = config_repository.load()["tracking"]

    assert tracking["assembly_zone"] == "Montagem"
    assert tracking["assembly_task_labels"] == {
        "Porcas": "Aperto Porcas",
        "Rodas": "Montagem Rodas",
    }


def test_apply_uses_first_two_hands_zone_when_assembly_zone_changed(tmp_path) -> None:
    repository, config_repository = _repository(tmp_path)

    repository.apply(
        BenchConfig(
            id="line-a",
            name="Linha A",
            zones=[
                BenchZone(name="Porcas", x=0, y=0, width=10, height=10),
                BenchZone(name="Mesa de Montagem", x=10, y=0, width=10, height=10, two_hands=True),
                BenchZone(name="Saida", x=20, y=0, width=10, height=10),
            ],
            cycle_sequence=["Porcas", "Mesa de Montagem", "Saida"],
            start_zone="Porcas",
            end_zone="Saida",
        )
    )

    tracking = config_repository.load()["tracking"]

    assert tracking["assembly_zone"] == "Mesa de Montagem"
    assert tracking["assembly_task_labels"] == {
        "Porcas": "Mesa de Montagem Porcas",
    }
