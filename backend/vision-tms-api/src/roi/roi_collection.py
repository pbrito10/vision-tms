from __future__ import annotations

from src.roi.region_of_interest import RegionOfInterest
from src.shared.point import Point


class RoiCollection:
    """Coleção de zonas de trabalho com lookup O(1) por nome.

    Mutável quando a configuração de bancada guarda zonas. Durante a análise,
    depois de carregada do JSON, não é modificada.
    """

    def __init__(self) -> None:
        self._rois: dict[str, RegionOfInterest] = {}

    def add(self, roi: RegionOfInterest) -> None:
        """Adiciona ou substitui uma zona — uma zona por nome."""
        self._rois[roi.name] = roi

    def remove(self, name: str) -> None:
        self._rois.pop(name, None)

    def find_zone_for_point(self, point: Point) -> RegionOfInterest | None:
        """Primeira zona que contém o ponto, ou None. Ordem = ordem de inserção."""
        for roi in self._rois.values():
            if roi.contains(point):
                return roi
        return None

    def get(self, name: str) -> RegionOfInterest | None:
        """Devolve a zona com o nome indicado, ou None se não existir."""
        return self._rois.get(name)

    def contains(self, name: str) -> bool:
        """True se existe uma zona com este nome na coleção."""
        return name in self._rois

    def is_empty(self) -> bool:
        """True se a coleção não tem nenhuma zona definida."""
        return len(self._rois) == 0

    def all(self) -> list[RegionOfInterest]:
        """Devolve todas as zonas por ordem de inserção."""
        return list(self._rois.values())
