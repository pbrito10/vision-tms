from __future__ import annotations
from abc import ABC, abstractmethod

import numpy as np

from src.detection.hand_detection import HandDetection


class DetectorInterface(ABC):
    """Contrato que qualquer detector de mãos tem de cumprir.

    O resto do sistema depende desta interface — trocar MediaPipe
    por outro modelo não exige alterar mais nenhum ficheiro.
    """

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[HandDetection]:
        """Recebe um frame RGB e devolve as mãos detetadas.

        O frame chega sempre em RGB — a conversão BGR→RGB é feita
        no processo da câmara antes de entrar na queue.
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """Liberta os recursos do detector (chamado no finally do pipeline)."""
        ...
