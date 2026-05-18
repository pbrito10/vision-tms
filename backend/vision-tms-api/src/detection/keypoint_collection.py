from __future__ import annotations
from dataclasses import dataclass, field

from src.detection.keypoint import Keypoint
from src.shared.point import Point

_FINGERTIP_INDICES  = [4, 8, 12, 16, 20]
_FINGER_MCP_INDICES = [5, 9, 13, 17]   # MCP do indicador, médio, anelar e mindinho
_EXPECTED_COUNT     = 21


@dataclass(frozen=True)
class KeypointCollection:
    """Os 21 landmarks de uma mão encapsulados numa coleção com semântica própria."""

    _keypoints: list[Keypoint] = field(repr=False)

    def __post_init__(self) -> None:
        if len(self._keypoints) != _EXPECTED_COUNT:
            raise ValueError(
                f"KeypointCollection exige {_EXPECTED_COUNT} keypoints, "
                f"recebidos {len(self._keypoints)}"
            )

    def wrist(self) -> Keypoint:
        """Pulso (índice 0)."""
        return self._keypoints[0]

    def centroid(self) -> Point:
        """Centro geométrico dos 21 pontos."""
        avg_x = sum(kp.position.x for kp in self._keypoints) // _EXPECTED_COUNT
        avg_y = sum(kp.position.y for kp in self._keypoints) // _EXPECTED_COUNT
        return Point(x=avg_x, y=avg_y)

    def finger_mcp_centroid(self) -> Point:
        """Centro dos MCP dos quatro dedos — ponto de referência para deteção de zona.

        Porquê MCP e não pulso ou fingertips?

        O pulso fica fora da ROI quando o operador estica o braço para uma caixa
        — os dedos já estão dentro, o pulso ainda não.

        As fingertips movem-se significativamente ao fechar a mão para agarrar
        uma peça, tornando-as instáveis exactamente no momento que mais interessa.

        Os MCP ficam fixos na palma independentemente do estado do grasping e
        estão posicionados sobre a zona de trabalho. Excluímos o polegar (índice 2)
        porque se move num plano diferente dos outros quatro e introduziria desvio.
        """
        mcps  = [self._keypoints[i] for i in _FINGER_MCP_INDICES]
        avg_x = sum(kp.position.x for kp in mcps) // len(_FINGER_MCP_INDICES)
        avg_y = sum(kp.position.y for kp in mcps) // len(_FINGER_MCP_INDICES)
        return Point(x=avg_x, y=avg_y)

    def fingertips(self) -> list[Keypoint]:
        """Pontas dos cinco dedos (índices 4, 8, 12, 16, 20)."""
        return [self._keypoints[i] for i in _FINGERTIP_INDICES]

    def by_index(self, index: int) -> Keypoint:
        """Acesso por índice MediaPipe (0–20)."""
        if not (0 <= index < _EXPECTED_COUNT):
            raise ValueError(f"Índice de keypoint inválido: {index} (deve ser 0–20)")
        return self._keypoints[index]

    def all(self) -> list[Keypoint]:
        return list(self._keypoints)
