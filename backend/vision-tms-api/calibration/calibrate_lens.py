"""
Calibração intrínseca da câmara usando um tabuleiro de xadrez (checkerboard).

Como usar:
  1. Imprime um tabuleiro de xadrez com CHECKERBOARD_SIZE cantos internos.
  2. Executa: python calibration/calibrate_lens.py
  3. Mostra o tabuleiro à câmara em várias posições e ângulos.
  4. Pressiona SPACE quando o tabuleiro estiver bem visível (verde = detetado).
  5. Após MIN_CAPTURES capturas, a calibração corre automaticamente.
  6. Resultado guardado em calibration/data/lens_calibration.npz.

Uso posterior no pipeline:
  data = np.load("calibration/data/lens_calibration.npz")
  K, dist = data["K"], data["dist"]
  frame_corrigido = cv2.undistort(frame, K, dist)
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import cv2
import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.shared.logging_config import configure_logging

logger = logging.getLogger(__name__)

# Garante que o DISPLAY está definido quando o script é corrido fora de uma sessão gráfica
if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

# --- Configuração ---
CAMERA_INDEX: int = 0
# Número de cantos internos do checkerboard (colunas, linhas).
# Um tabuleiro 10x7 quadrados tem (9, 6) cantos internos.
CHECKERBOARD_SIZE: tuple[int, int] = (6, 4)
SQUARE_SIZE_MM: float = 35.0       # tamanho real de cada quadrado em milímetros
MIN_CAPTURES: int = 15             # capturas mínimas para correr a calibração
OUTPUT_PATH: Path = Path(__file__).parent / "data" / "lens_calibration.npz"

# Critério de paragem para refinamento sub-pixel dos cantos
_SUBPIX_CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)


class LensCalibrator:
    """Recolhe capturas de checkerboard e calcula os parâmetros intrínsecos da câmara.

    Separa a lógica de calibração da lógica de captura/UI.
    """

    def __init__(self, checkerboard_size: tuple[int, int], square_size_mm: float) -> None:
        self._checkerboard = checkerboard_size
        self._obj_pts_template = self._build_object_points(checkerboard_size, square_size_mm)
        self._obj_pts: list[np.ndarray] = []   # pontos 3D (um por captura)
        self._img_pts: list[np.ndarray] = []   # pontos 2D correspondentes

    @staticmethod
    def _build_object_points(size: tuple[int, int], square_mm: float) -> np.ndarray:
        """Cria o array de pontos 3D do checkerboard no referencial do mundo (z=0)."""
        cols, rows = size
        pts = np.zeros((rows * cols, 3), dtype=np.float32)
        pts[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
        pts *= square_mm
        return pts

    def detect(self, frame: np.ndarray) -> tuple[bool, np.ndarray | None, np.ndarray]:
        """Deteta os cantos do checkerboard num frame e devolve uma versão anotada.

        :return: (detetado, cantos_refinados_ou_None, frame_anotado)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, self._checkerboard, None)
        display = frame.copy()

        if found:
            # Refinamento sub-pixel para maior precisão
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), _SUBPIX_CRITERIA)
            cv2.drawChessboardCorners(display, self._checkerboard, corners, found)

        return found, (corners if found else None), display

    def capture(self, corners: np.ndarray) -> int:
        """Regista uma captura válida. Devolve o total de capturas acumuladas."""
        self._obj_pts.append(self._obj_pts_template)
        self._img_pts.append(corners)
        return len(self._obj_pts)

    @property
    def capture_count(self) -> int:
        return len(self._obj_pts)

    def calibrate(self, image_size: tuple[int, int]) -> CalibrationResult:
        """Executa cv2.calibrateCamera com todas as capturas recolhidas.

        :param image_size: (width, height) do frame em píxeis
        :raises ValueError: se o número de capturas for insuficiente
        """
        if self.capture_count < MIN_CAPTURES:
            raise ValueError(f"São necessárias pelo menos {MIN_CAPTURES} capturas.")

        rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(
            self._obj_pts,
            self._img_pts,
            image_size,
            None,
            None,
        )

        # Refina a matriz intrínseca com alpha=1 (retém todos os píxeis; sem crop)
        w, h = image_size
        newcameramtx, roi = cv2.getOptimalNewCameraMatrix(K, dist, (w, h), 1, (w, h))

        # Erro de reprojeção por imagem — quanto mais próximo de 0, melhor
        per_image_errors = []
        for i in range(len(self._obj_pts)):
            imgpoints2, _ = cv2.projectPoints(self._obj_pts[i], rvecs[i], tvecs[i], K, dist)
            error = cv2.norm(self._img_pts[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
            per_image_errors.append(error)

        return CalibrationResult(
            camera_matrix=K,
            dist_coeffs=dist,
            rms=rms,
            new_camera_matrix=newcameramtx,
            roi=roi,
            per_image_errors=per_image_errors,
        )


class CalibrationResult:
    """Encapsula os parâmetros intrínsecos, distorção, matriz refinada e erros de reprojeção."""

    def __init__(
        self,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        rms: float,
        new_camera_matrix: np.ndarray,
        roi: tuple[int, int, int, int],
        per_image_errors: list[float],
    ) -> None:
        self.camera_matrix = camera_matrix      # K original: focal lengths + ponto principal
        self.dist_coeffs = dist_coeffs          # [k1, k2, p1, p2, k3]
        self.rms = rms                           # erro de reprojeção médio em píxeis
        self.new_camera_matrix = new_camera_matrix  # K refinado por getOptimalNewCameraMatrix
        self.roi = roi                           # (x, y, w, h) — região válida após undistortion
        self.per_image_errors = per_image_errors

    def save(self, path: Path) -> None:
        """Grava os parâmetros em .npz. Cria as pastas intermédias se necessário."""
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            str(path),
            K=self.camera_matrix,
            dist=self.dist_coeffs,
            newcameramtx=self.new_camera_matrix,
            roi=np.array(self.roi),
        )
        logger.info("Calibracao guardada em: %s", path)
        logger.info("Erro de reprojecao (RMS total): %.4f px", self.rms)
        logger.info("Erro por imagem:")
        for i, err in enumerate(self.per_image_errors):
            logger.info("Imagem %2d: %.4f px", i + 1, err)
        # Valores > 1 px indicam que as imagens capturadas podem ter má qualidade
        if self.rms > 1.0:
            logger.warning("RMS > 1 px; considera capturar mais imagens ou verificar o checkerboard.")


def _draw_hud(frame: np.ndarray, count: int, detected: bool) -> None:
    """Sobrepõe informação de estado no frame: status de deteção e contagem."""
    h = frame.shape[0]
    color = (0, 200, 0) if detected else (0, 0, 200)
    status = "DETETADO — SPACE para capturar" if detected else "A procurar checkerboard..."

    cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(frame, f"Capturas: {count}/{MIN_CAPTURES}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, "SPACE: capturar  ESC: sair", (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)


def main() -> None:
    configure_logging()

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        logger.error("Nao foi possivel abrir a camara %s.", CAMERA_INDEX)
        sys.exit(1)

    calibrator = LensCalibrator(CHECKERBOARD_SIZE, SQUARE_SIZE_MM)
    image_size: tuple[int, int] | None = None
    calibrated = False
    #Cria a janela explicitamente
    cv2.namedWindow("Calibração de Lente", cv2.WINDOW_NORMAL)
    logger.info("=== Calibracao de Lente ===")
    logger.info("Checkerboard: %sx%s cantos internos", CHECKERBOARD_SIZE[0], CHECKERBOARD_SIZE[1])
    logger.info("Quadrado: %s mm | Capturas necessarias: %s", SQUARE_SIZE_MM, MIN_CAPTURES)
    logger.info("Mostra o tabuleiro a camara em posicoes e angulos variados.")
    logger.info("Pressiona SPACE quando o padrao estiver detetado (cantos verdes).")

    while True:
        ok, frame = cap.read()
        if not ok:
            logger.error("Erro a ler frame da camara.")
            break

        if image_size is None:
            h, w = frame.shape[:2]
            image_size = (w, h)

        found, corners, display = calibrator.detect(frame)
        _draw_hud(display, calibrator.capture_count, found)
        cv2.imshow("Calibração de Lente", display)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC — sair
            logger.info("Saiu sem guardar.")
            break

        if key == ord(' ') and found and corners is not None and not calibrated:
            count = calibrator.capture(corners)
            logger.info("Captura %s/%s registada.", count, MIN_CAPTURES)

            # Calibração automática ao atingir o mínimo
            if count >= MIN_CAPTURES:
                logger.info("A calcular calibracao.")
                result = calibrator.calibrate(image_size)
                result.save(OUTPUT_PATH)
                calibrated = True
                logger.info("Pressiona ESC para sair.")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
