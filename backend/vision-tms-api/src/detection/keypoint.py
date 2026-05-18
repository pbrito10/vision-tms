from __future__ import annotations
from dataclasses import dataclass

from src.shared.confidence import Confidence
from src.shared.point import Point


@dataclass(frozen=True)
class Keypoint:
    """Uma articulação da mão: posição em píxeis, confiança e índice (0–20).

    Convenção dos 21 pontos (MediaPipe):
        0        : Pulso
        1–4      : Polegar (base → ponta)
        5–8      : Indicador
        9–12     : Médio
        13–16    : Anelar
        17–20    : Mindinho
    """

    index: int
    position: Point
    confidence: Confidence
