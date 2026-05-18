from __future__ import annotations
from abc import ABC, abstractmethod

from src.roi.roi_collection import RoiCollection


class RoiRepository(ABC):
    """Contrato para persistência de ROIs — independente do formato de armazenamento.

    O resto do sistema depende desta interface; trocar JSON por base de dados
    não exige alterar mais nenhum ficheiro. (Dependency Inversion)
    """

    @abstractmethod
    def save(self, collection: RoiCollection) -> None:
        """Persiste todas as zonas da collection."""
        ...

    @abstractmethod
    def load(self) -> RoiCollection:
        """Carrega as zonas guardadas. Devolve collection vazia se não existirem."""
        ...
