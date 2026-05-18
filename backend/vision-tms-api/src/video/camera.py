from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np


class Camera:
    """Abstração sobre cv2.VideoCapture para isolar o resto do sistema do OpenCV.

    Abre a câmara no construtor e expõe apenas o que o sistema precisa:
    ler frames, consultar FPS e libertar o recurso.
    """

    def __init__(self, index: int, width: int, height: int,
                 calibration_path: str | None = None,
                 perspective_path: str | None = None,
                 flip: bool = False,
                 open_timeout_seconds: float = 5.0,
                 open_retry_interval_seconds: float = 0.2) -> None:
        """Abre a câmara e configura a resolução pedida.
        :param index: int - índice da câmara (0 para a câmara padrão)
        :param width: int - largura de captura desejada em píxeis
        :param height: int - altura de captura desejada em píxeis
        :param calibration_path: caminho para o .npz de lente; None desativa
        :param perspective_path: caminho para o .npz de perspetiva; None desativa
        :param flip: True para rodar 180° (flip horizontal + vertical)
        """
        self._capture = self._open_capture(
            index=index,
            timeout_seconds=open_timeout_seconds,
            retry_interval_seconds=open_retry_interval_seconds,
        )
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
            self._capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2000)

        # Configurar resolução pedida — a câmara pode não suportar e ajusta automaticamente
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # Mapas pré-calculados para undistortion eficiente por frame (initUndistortRectifyMap)
        # Calculados uma vez no construtor; remap() aplica-os sem recalcular a cada frame
        self._undistort_maps: tuple[np.ndarray, np.ndarray] | None = None
        if calibration_path:
            path = Path(calibration_path)
            if path.exists():
                data = np.load(str(path))
                K, dist = data["K"], data["dist"]
                # newcameramtx guardado pelo calibrate_lens atual; fallback para K em ficheiros antigos
                newcameramtx = data["newcameramtx"] if "newcameramtx" in data else K
                self._undistort_maps = cv2.initUndistortRectifyMap(
                    K, dist, None, newcameramtx, (width, height), cv2.CV_32FC1
                )

        self._flip = flip

        # Matriz de perspetiva para correção de vista (bird's-eye view)
        self._perspective_M: np.ndarray | None = None
        self._perspective_size: tuple[int, int] | None = None
        if perspective_path:
            path = Path(perspective_path)
            if path.exists():
                data = np.load(str(path))
                self._perspective_M = data["M"]
                self._perspective_size = tuple(data["output_size"].tolist())

    @classmethod
    def from_config(cls, config: dict) -> "Camera":
        """Constrói uma Camera a partir do dicionário camera: do settings.yaml."""
        return cls(
            index=config["index"],
            width=config["width"],
            height=config["height"],
            calibration_path=config.get("calibration_path"),
            perspective_path=config.get("perspective_path"),
            flip=config.get("flip", False),
            open_timeout_seconds=config.get("open_timeout_seconds", 5.0),
            open_retry_interval_seconds=config.get("open_retry_interval_seconds", 0.2),
        )

    def _open_capture(
        self,
        *,
        index: int,
        timeout_seconds: float,
        retry_interval_seconds: float,
    ) -> cv2.VideoCapture:
        deadline = time.monotonic() + timeout_seconds
        last_capture = None

        while True:
            capture = cv2.VideoCapture(index, cv2.CAP_V4L2)
            if capture.isOpened():
                return capture

            capture.release()
            last_capture = capture
            if time.monotonic() >= deadline:
                return last_capture

            time.sleep(retry_interval_seconds)

    def read_frame(self) -> np.ndarray | None:
        """Lê o próximo frame, aplicando correções de lente e perspetiva se disponíveis.
        Devolve None se a câmara falhou ou terminou."""
        success, frame = self._capture.read()
        if not success:
            return None
        # Lente → flip → perspetiva (ordem importante para calibração consistente)
        if self._undistort_maps is not None:
            frame = cv2.remap(frame, *self._undistort_maps, cv2.INTER_LINEAR)
        if self._flip:
            frame = cv2.flip(frame, -1)
        if self._perspective_M is not None:
            frame = cv2.warpPerspective(frame, self._perspective_M, self._perspective_size)
        return frame

    def fps(self) -> float:
        """FPS reportado pela câmara — usado para cálculos temporais no pipeline."""
        return self._capture.get(cv2.CAP_PROP_FPS)

    def is_open(self) -> bool:
        """Verifica se a câmara está aberta e disponível para leitura."""
        return self._capture.isOpened()

    def release(self) -> None:
        """Liberta o recurso — deve ser chamado no finally de quem usa a câmara."""
        self._capture.release()
