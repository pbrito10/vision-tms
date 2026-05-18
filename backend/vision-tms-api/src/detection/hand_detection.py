from __future__ import annotations
from dataclasses import dataclass

from src.detection.bounding_box import BoundingBox
from src.detection.keypoint import Keypoint
from src.detection.keypoint_collection import KeypointCollection
from src.shared.confidence import Confidence
from src.shared.hand_side import HandSide
from src.shared.point import Point


@dataclass(frozen=True)
class HandDetection:
    """Todos os dados de uma mão detetada num frame.

    Agrupa keypoints, bounding box, confiança e lado numa estrutura
    imutável — o detector produz-a, o resto do sistema consome-a.
    """

    keypoints: KeypointCollection
    bounding_box: BoundingBox
    confidence: Confidence
    hand_side: HandSide

    # Atalhos que delegam na KeypointCollection para não forçar
    # o código externo a aceder sempre a .keypoints.xxx

    def centroid(self) -> Point:
        """Centro geométrico dos 21 keypoints (média de todos os landmarks).

        Menos preciso do que finger_mcp_centroid() para localização na zona de trabalho
        porque inclui os dedos, que se movem muito ao agarrar peças. Disponível para
        usos externos que não precisem da precisão do MCP.
        """
        return self.keypoints.centroid()

    def wrist(self) -> Keypoint:
        """Landmark 0 — base do pulso.

        Usado como ponto de referência para:
          - calcular velocidade de movimento (StillnessDwellStrategy)
          - ancorar o label de identificação da mão (frame_annotator)
        Não é usado para determinar em que zona a mão está — ver finger_mcp_centroid().
        """
        return self.keypoints.wrist()
