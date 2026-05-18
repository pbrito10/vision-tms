"""Funções de desenho sobre frames OpenCV.

Todas operam in-place sobre o frame BGR e não guardam estado.
"""
from __future__ import annotations

import cv2
import numpy as np

from src.detection.hand_detection import HandDetection
from src.roi.region_of_interest import RegionOfInterest
from src.roi.roi_collection import RoiCollection

_FONT           = cv2.FONT_HERSHEY_SIMPLEX
_LINE_THICKNESS = 2
_KEYPOINT_RADIUS = 4
_FILL_ALPHA     = 0.2

# Ligações entre landmarks — topologia padrão do MediaPipe para a mão humana
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Polegar
    (0, 5), (5, 6), (6, 7), (7, 8),        # Indicador
    (0, 9), (9, 10), (10, 11), (11, 12),   # Médio
    (0, 13), (13, 14), (14, 15), (15, 16), # Anelar
    (0, 17), (17, 18), (18, 19), (19, 20), # Mindinho
    (5, 9), (9, 13), (13, 17),             # Palma
]

_HAND_COLORS: dict[str, tuple[int, int, int]] = {
    "left":  (255, 100, 0),
    "right": (0, 200, 50),
}

_ZONE_COLOR_DEFAULT  = (50, 205, 50)
_ZONE_COLOR_ASSEMBLY = (0, 165, 255)
_ZONE_COLOR_EXIT     = (255, 100, 0)

_ZONE_COLOR_MAP: dict[str, tuple[int, int, int]] = {
    "Montagem": _ZONE_COLOR_ASSEMBLY,
    "Saida":    _ZONE_COLOR_EXIT,
}


def zone_color(name: str) -> tuple[int, int, int]:
    """Devolve a cor BGR da zona pelo nome. Usa _ZONE_COLOR_MAP; fallback para verde."""
    return _ZONE_COLOR_MAP.get(name, _ZONE_COLOR_DEFAULT)


def _draw_skeleton(frame: np.ndarray, keypoints, color: tuple[int, int, int]) -> None:
    for start_idx, end_idx in _HAND_CONNECTIONS:
        start = keypoints.by_index(start_idx).position
        end   = keypoints.by_index(end_idx).position
        cv2.line(frame, (start.x, start.y), (end.x, end.y), color, _LINE_THICKNESS)


def _draw_keypoints(frame: np.ndarray, keypoints, color: tuple[int, int, int]) -> None:
    for kp in keypoints.all():
        cv2.circle(frame, (kp.position.x, kp.position.y), _KEYPOINT_RADIUS, color, -1)


def draw_hand(frame: np.ndarray, detection: HandDetection) -> None:
    """Desenha esqueleto, keypoints e label no frame (in-place).

    A cor depende do lado da mão (azul para esquerda, verde para direita).
    O label é ancorado ao pulso (landmark 0) com o lado e a confiança em percentagem.
    """
    color = _HAND_COLORS[detection.hand_side.value]
    _draw_skeleton(frame, detection.keypoints, color)
    _draw_keypoints(frame, detection.keypoints, color)

    # Label ancorada ao pulso (landmark 0)
    wrist = detection.keypoints.by_index(0).position
    label = f"{detection.hand_side.value}  {detection.confidence.as_percentage():.0f}%"
    cv2.putText(frame, label, (wrist.x, wrist.y - 10), _FONT, 0.5, color, 1)


def draw_detections(frame: np.ndarray, detections: list[HandDetection]) -> None:
    """Desenha todas as mãos detetadas no frame. Chama draw_hand para cada uma."""
    for detection in detections:
        draw_hand(frame, detection)


def draw_roi(
    frame: np.ndarray,
    roi: RegionOfInterest,
    color: tuple[int, int, int],
    *,
    selected: bool = False,
) -> None:
    """Desenha uma ROI no frame (in-place): preenchimento semi-transparente + contorno + nome.

    selected=True usa contorno mais espesso para indicar a zona ativa no modo de desenho.
    """
    tl = (roi.top_left.x, roi.top_left.y)
    br = (roi.bottom_right.x, roi.bottom_right.y)

    overlay = frame.copy()
    cv2.rectangle(overlay, tl, br, color, -1)
    cv2.addWeighted(overlay, _FILL_ALPHA, frame, 1 - _FILL_ALPHA, 0, frame)

    thickness = _LINE_THICKNESS
    if selected:
        thickness = _LINE_THICKNESS + 1
    cv2.rectangle(frame, tl, br, color, thickness)

    cv2.putText(frame, roi.name, (tl[0] + 5, tl[1] + 20), _FONT, 0.6, color, 2)


def draw_rois(
    frame: np.ndarray,
    rois: RoiCollection,
    *,
    selected_name: str | None = None,
) -> None:
    """Desenha todas as ROIs da coleção, destacando a zona com nome selected_name (se fornecido)."""
    for roi in rois.all():
        color = zone_color(roi.name)
        draw_roi(frame, roi, color, selected=roi.name == selected_name)


def draw_fps(frame: np.ndarray, fps: float) -> None:
    """Escreve FPS e resolução no canto superior esquerdo do frame."""
    h, w = frame.shape[:2]
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25), _FONT, 0.6, (255, 255, 255), 1)
    cv2.putText(frame, f"{w}x{h}", (10, 50), _FONT, 0.6, (255, 255, 255), 1)
