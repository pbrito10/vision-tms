from __future__ import annotations

from abc import ABC, abstractmethod

from src.detection.hand_detection import HandDetection


class ActivationStrategy(ABC):
    """Define quando o dwell timer avança.

    Stateless por design — pode ser partilhada entre várias mãos/máquinas
    sem risco de estado cruzado. O contexto necessário (frame atual e anterior)
    é passado em cada chamada.
    """

    @abstractmethod
    def is_active(
        self,
        detection: HandDetection,
        previous: HandDetection | None,
    ) -> bool:
        """True se o critério de ativação está cumprido neste frame."""


class TimeDwellStrategy(ActivationStrategy):
    """Timer avança sempre que a mão está na zona, sem verificar movimento.

    Útil para depuração ou zonas onde qualquer presença conta.
    """

    def is_active(self, detection: HandDetection, previous: HandDetection | None) -> bool:
        return True


class StillnessDwellStrategy(ActivationStrategy):
    """Timer só avança quando a mão está suficientemente parada.

    Distingue uma passagem lenta (mão nunca para) de uma tarefa rápida
    (mão para brevemente). Sem este filtro, qualquer trânsito lento pela
    zona seria registado como tarefa.

    O threshold em px/frame depende da resolução e da distância câmara-bancada.
    A 640x480, valores entre 3 e 8 px/frame funcionam bem na prática.
    """

    def __init__(self, velocity_threshold_px_per_frame: float) -> None:
        self._threshold = velocity_threshold_px_per_frame

    def is_active(self, detection: HandDetection, previous: HandDetection | None) -> bool:
        if previous is None:
            # Primeiro frame nesta zona — sem referência anterior para calcular velocidade
            return False

        velocity = detection.wrist().position.distance_to(previous.wrist().position)
        return velocity < self._threshold
