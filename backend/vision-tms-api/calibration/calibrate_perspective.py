"""
Calibração de perspetiva por seleção interativa de 4 pontos de referência.

Como usar:
  1. Coloca um retângulo de referência bem visível na bancada (ex: folha A4).
  2. Executa: python calibration/calibrate_perspective.py
  3. Clica nos 4 cantos do retângulo na ordem indicada (SE → SD → ID → IE).
  4. Verifica a vista corrigida na janela de preview.
  5. ENTER para guardar, R para repetir, ESC para sair sem guardar.
  6. Resultado guardado em calibration/data/perspective_calibration.npz.

Uso posterior no pipeline:
  data = np.load("calibration/data/perspective_calibration.npz")
  M = data["M"]
  output_size = tuple(data["output_size"])
  frame_corrigido = cv2.warpPerspective(frame, M, output_size)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

# Quando em SSH, força o display físico da máquina remota
if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY") or not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

# --- Configuração ---
CAMERA_INDEX: int = 0
# Dimensões reais do retângulo de referência na bancada (em milímetros).
# Exemplos: A4 → (297, 210) | A3 → (420, 297) | quadrado 300mm → (300, 300)
REFERENCE_WIDTH_MM: float = 297.0
REFERENCE_HEIGHT_MM: float = 210.0
# Largura da imagem de saída corrigida em píxeis (altura calculada automaticamente).
OUTPUT_WIDTH_PX: int = 800
OUTPUT_PATH: Path = Path(__file__).parent / "data" / "perspective_calibration.npz"

# Ordem de clique: Superior-Esquerdo → Superior-Direito → Inferior-Direito → Inferior-Esquerdo
_LABELS = ["Sup-Esq", "Sup-Dir", "Inf-Dir", "Inf-Esq"]
_COLORS = [(0, 255, 0), (255, 128, 0), (0, 0, 255), (255, 0, 255)]

# Lista global de pontos clicados — evita passar objetos Python como param ao Qt
_src_points: list[tuple[int, int]] = []


def _compute_output_height() -> int:
    """Calcula a altura de saída mantendo a proporção real do retângulo de referência."""
    return int(OUTPUT_WIDTH_PX * REFERENCE_HEIGHT_MM / REFERENCE_WIDTH_MM)


class PerspectiveCalibrator:
    """Recolhe 4 pontos clicados pelo utilizador e calcula a homografia de perspetiva.

    Os 4 pontos correspondem aos cantos de um retângulo conhecido na bancada.
    A transformação mapeia esses pontos para os cantos da imagem de saída,
    resultando numa vista ortogonal (bird's-eye view).
    """

    def __init__(self, output_size: tuple[int, int]) -> None:
        self._output_w, self._output_h = output_size
        self._src_pts: list[tuple[int, int]] = []

    @property
    def point_count(self) -> int:
        return len(self._src_pts)

    @property
    def points(self) -> list[tuple[int, int]]:
        return list(self._src_pts)

    @property
    def is_complete(self) -> bool:
        return len(self._src_pts) == 4

    def add_point(self, x: int, y: int) -> None:
        """Regista um ponto clicado. Ignora cliques depois dos 4 pontos estarem definidos."""
        if not self.is_complete:
            self._src_pts.append((x, y))

    def reset(self) -> None:
        """Remove todos os pontos para recomeçar a seleção."""
        self._src_pts.clear()

    def compute(self) -> PerspectiveResult:
        """Calcula a matriz de perspetiva 3×3 a partir dos 4 pontos selecionados.

        :raises ValueError: se ainda não houver 4 pontos registados
        """
        if not self.is_complete:
            raise ValueError("São necessários exatamente 4 pontos.")

        src = np.float32(self._src_pts)
        # Destino: os 4 cantos da imagem de saída (retângulo perfeito)
        dst = np.float32([
            [0,                   0],
            [self._output_w - 1,  0],
            [self._output_w - 1,  self._output_h - 1],
            [0,                   self._output_h - 1],
        ])
        M = cv2.getPerspectiveTransform(src, dst)
        return PerspectiveResult(matrix=M, output_size=(self._output_w, self._output_h))


class PerspectiveResult:
    """Encapsula a matriz de perspetiva e o tamanho da imagem de saída."""

    def __init__(self, matrix: np.ndarray, output_size: tuple[int, int]) -> None:
        self.matrix = matrix
        self.output_size = output_size

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Aplica a transformação de perspetiva a um frame."""
        return cv2.warpPerspective(frame, self.matrix, self.output_size)

    def save(self, path: Path) -> None:
        """Grava a matriz e o tamanho de saída em .npz. Cria pastas se necessário."""
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(str(path), M=self.matrix, output_size=np.array(self.output_size))
        print(f"\nPerspetiva guardada em: {path}")
        print(f"Tamanho de saída: {self.output_size[0]}x{self.output_size[1]} px")


def _draw_hud(frame: np.ndarray, calibrator: PerspectiveCalibrator) -> None:
    """Desenha os pontos já clicados e as instruções para o próximo ponto."""
    h = frame.shape[0]

    # Pontos já selecionados: círculo preenchido + linha de ligação + label
    for i, (x, y) in enumerate(calibrator.points):
        color = _COLORS[i]
        cv2.circle(frame, (x, y), 8, color, -1)
        cv2.circle(frame, (x, y), 10, (255, 255, 255), 1)
        cv2.putText(frame, _LABELS[i], (x + 12, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    # Linha de contorno entre pontos consecutivos (ajuda a visualizar o retângulo)
    pts = calibrator.points
    for i in range(len(pts)):
        cv2.line(frame, pts[i], pts[(i + 1) % len(pts)], (200, 200, 200), 1)

    # Instrução para o próximo ponto ou confirmação
    if not calibrator.is_complete:
        idx = calibrator.point_count
        cv2.putText(frame, f"Clica: {_LABELS[idx]}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, _COLORS[idx], 2)
    else:
        cv2.putText(frame, "4 pontos OK  |  ENTER: guardar   R: repetir", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 0), 2)

    cv2.putText(frame, "R: repetir  |  ESC: sair sem guardar", (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)


def _on_mouse_click(event: int, x: int, y: int, _flags: int, _param) -> None:
    """Callback de rato: regista cliques esquerdos na lista global _src_points."""
    if event == cv2.EVENT_LBUTTONDOWN and len(_src_points) < 4:
        _src_points.append((x, y))


def main() -> None:
    global _src_points

    with open(_SETTINGS_PATH) as f:
        _settings = yaml.safe_load(f)
    _flip: bool = _settings["camera"].get("flip", False)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"Erro: não foi possível abrir a câmara {CAMERA_INDEX}.")
        sys.exit(1)

    output_size = (OUTPUT_WIDTH_PX, _compute_output_height())
    calibrator = PerspectiveCalibrator(output_size)
    current_result: PerspectiveResult | None = None
    callback_registered = False

    window_main    = "Calibracao de Perspetiva"
    window_preview = "Preview Corrigido"

    cv2.namedWindow(window_main, cv2.WINDOW_NORMAL)

    print("=== Calibração de Perspetiva ===")
    print(f"Retângulo de referência: {REFERENCE_WIDTH_MM} mm × {REFERENCE_HEIGHT_MM} mm")
    print(f"Imagem de saída: {output_size[0]}×{output_size[1]} px\n")
    print("Clica nos 4 cantos do retângulo de referência na bancada:")
    print("  1. Superior-Esquerdo  →  2. Superior-Direito")
    print("  4. Inferior-Esquerdo  ←  3. Inferior-Direito")
    print("\nENTER: confirmar e guardar | R: repetir seleção | ESC: sair\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Erro a ler frame da câmara.")
            break

        # Aplica o mesmo flip do pipeline (lido de settings.yaml) para consistência
        if _flip:
            frame = cv2.flip(frame, -1)

        # Sincroniza pontos clicados (lista global) com o calibrador
        while len(_src_points) > calibrator.point_count:
            x, y = _src_points[calibrator.point_count]
            calibrator.add_point(x, y)

        display = frame.copy()
        _draw_hud(display, calibrator)
        cv2.imshow(window_main, display)

        # Regista o callback só após o primeiro imshow — garante que a janela existe no Qt
        if not callback_registered:
            cv2.setMouseCallback(window_main, _on_mouse_click)
            callback_registered = True

        if calibrator.is_complete:
            current_result = calibrator.compute()
            warped = current_result.apply(frame)
            cv2.imshow(window_preview, warped)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC — sair sem guardar
            print("Saiu sem guardar.")
            break

        if key in (ord('r'), ord('R')):
            calibrator.reset()
            _src_points.clear()
            current_result = None
            cv2.destroyWindow(window_preview)
            print("Pontos limpos. Seleciona novamente.")

        if key == 13 and current_result is not None:  # ENTER — confirmar e guardar
            current_result.save(OUTPUT_PATH)
            print("Calibração de perspetiva concluída! Pressiona ESC para sair.")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
