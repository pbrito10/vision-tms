from __future__ import annotations

import json
from pathlib import Path

from src.roi.region_of_interest import RegionOfInterest
from src.roi.roi_collection import RoiCollection
from src.roi.roi_repository import RoiRepository


class JsonRoiRepository(RoiRepository):
    """Persiste ROIs em config/rois.json.

    Formato: lista de dicts com name, x1, y1, x2, y2.
    Se o ficheiro não existir, load() devolve collection vazia.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, collection: RoiCollection) -> None:
        """Serializa e escreve todas as zonas com indentação legível."""
        data = [roi.to_dict() for roi in collection.all()]
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def load(self) -> RoiCollection:
        """Carrega zonas do ficheiro. Devolve vazio se o ficheiro não existir."""
        if not self._path.exists():
            return RoiCollection()

        data = json.loads(self._path.read_text())
        collection = RoiCollection()
        for entry in data:
            collection.add(RegionOfInterest.from_dict(entry))
        return collection
