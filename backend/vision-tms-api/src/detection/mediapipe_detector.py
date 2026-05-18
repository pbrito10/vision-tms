from __future__ import annotations

from pathlib import Path
import time

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from src.detection.bounding_box import BoundingBox
from src.detection.detector_interface import DetectorInterface
from src.detection.hand_detection import HandDetection
from src.detection.keypoint import Keypoint
from src.detection.keypoint_collection import KeypointCollection
from src.shared.confidence import Confidence
from src.shared.hand_side import HandSide
from src.shared.point import Point

# Margem adicionada à bounding box calculada a partir dos landmarks, em píxeis
_BOUNDING_BOX_MARGIN_PX = 10

# Dict de mapeamento evita um if/elif por cada label que a API possa devolver
_HAND_SIDE_MAP: dict[str, HandSide] = {
    "Left": HandSide.LEFT,
    "Right": HandSide.RIGHT,
}


class MediapipeDetector(DetectorInterface):
    """Detector de mãos via MediaPipe Tasks API (HandLandmarker).

    Usa o modo VIDEO porque o pipeline processa frames de forma síncrona e sequencial.
    O modo LIVE_STREAM seria assíncrono (callbacks), o que complicaria a pipeline.
    O modo IMAGE trata cada frame como independente e perde o benefício do tracking.

    VIDEO requer timestamps em milissegundos monotonicamente crescentes —
    usamos time.monotonic() e não datetime.now() para garantir isso mesmo
    quando o relógio do sistema é ajustado.
    """

    def __init__(
        self,
        model_path: str,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.7,
    ) -> None:
        model_buffer = Path(model_path).read_bytes()
        base_options = mp_python.BaseOptions(model_asset_buffer=model_buffer)
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=max_num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            # presence_confidence: threshold para o modelo continuar a rastrear
            # uma mão já detetada. Usamos o mesmo valor de detection para consistência.
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)

    def detect(self, frame: np.ndarray) -> list[HandDetection]:
        """Processa um frame RGB e devolve as mãos detetadas.

        Recebe: frame em RGB (convertido em capture_process antes de entrar na queue).
        Devolve: lista de HandDetection, uma por mão; lista vazia se nenhuma for detetada.
        """
        height, width = frame.shape[:2]

        mp_image     = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        timestamp_ms = int(time.monotonic() * 1000)
        result       = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.hand_landmarks:
            return []

        return [
            self._build_detection(landmarks, handedness, width, height)
            for landmarks, handedness in zip(result.hand_landmarks, result.handedness)
        ]

    def _build_detection(
        self,
        landmarks,
        handedness,
        width: int,
        height: int,
    ) -> HandDetection:
        """Converte a saída bruta do MediaPipe num HandDetection do domínio.

        Extrai confiança e lado do objeto handedness, constrói os keypoints
        em píxeis e calcula a bounding box a partir dos landmarks.
        """
        # handedness é uma lista de Category ordenada por confiança — o primeiro é o mais provável
        category   = handedness[0]
        confidence = Confidence(value=round(category.score, 4))
        keypoints  = self._build_keypoints(landmarks, width, height, confidence)

        return HandDetection(
            keypoints=keypoints,
            bounding_box=self._compute_bounding_box(keypoints, width, height),
            confidence=confidence,
            hand_side=_HAND_SIDE_MAP[category.category_name],
        )

    def _build_keypoints(
        self,
        landmarks,
        width: int,
        height: int,
        confidence: Confidence,
    ) -> KeypointCollection:
        """Converte os 21 landmarks normalizados [0,1] para KeypointCollection em píxeis."""
        # A Tasks API não devolve confiança por landmark — usamos a confiança global da mão
        keypoint_list = [
            Keypoint(
                index=index,
                position=self._to_pixel_point(landmark, width, height),
                confidence=confidence,
            )
            for index, landmark in enumerate(landmarks)
        ]
        return KeypointCollection(keypoint_list)

    @staticmethod
    def _to_pixel_point(landmark, width: int, height: int) -> Point:
        return Point(x=int(landmark.x * width), y=int(landmark.y * height))

    def _compute_bounding_box(
        self,
        keypoints: KeypointCollection,
        width: int,
        height: int,
    ) -> BoundingBox:
        """Calcula a bounding box a partir dos extremos dos landmarks, com margem.

        A Tasks API não devolve bounding box — é calculada aqui a partir dos
        landmarks mínimos e máximos, com _BOUNDING_BOX_MARGIN_PX de padding.
        """
        x_coords, y_coords = self._extract_coords(keypoints)
        min_x, max_x = self._clamp_range(x_coords, width)
        min_y, max_y = self._clamp_range(y_coords, height)
        return BoundingBox(
            top_left=Point(x=min_x, y=min_y),
            bottom_right=Point(x=max_x, y=max_y),
        )

    @staticmethod
    def _extract_coords(keypoints: KeypointCollection) -> tuple[list[int], list[int]]:
        """Devolve (lista_x, lista_y) com as coordenadas em píxeis de todos os keypoints."""
        all_kp = keypoints.all()
        return [kp.position.x for kp in all_kp], [kp.position.y for kp in all_kp]

    @staticmethod
    def _clamp_range(values: list[int], frame_max: int) -> tuple[int, int]:
        """Aplica margem e limita ao intervalo [0, frame_max-1].

        Recebe: lista de coordenadas inteiras, dimensão máxima do frame.
        Devolve: (min_com_margem, max_com_margem) clampado ao frame.
        """
        return (
            max(0, min(values) - _BOUNDING_BOX_MARGIN_PX),
            min(frame_max - 1, max(values) + _BOUNDING_BOX_MARGIN_PX),
        )

    def release(self) -> None:
        self._landmarker.close()
