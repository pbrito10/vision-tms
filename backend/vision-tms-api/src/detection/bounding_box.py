from __future__ import annotations
from dataclasses import dataclass

from src.shared.point import Point


@dataclass(frozen=True)
class BoundingBox:
    """Retângulo envolvente de uma mão detetada.

    Definido por dois pontos em vez de quatro ints soltos,
    tornando explícito que formam um retângulo.
    """

    top_left: Point
    bottom_right: Point

    def center(self) -> Point:
        """Ponto central do retângulo, calculado como média dos dois cantos.

        Não é usado pelo ZoneClassifier (que usa finger_mcp_centroid).
        Disponível para consumidores externos que precisem do centro geométrico da bbox.
        """
        return Point(
            x=(self.top_left.x + self.bottom_right.x) // 2,
            y=(self.top_left.y + self.bottom_right.y) // 2,
        )

    def area(self) -> int:
        """Área do retângulo em píxeis quadrados (largura × altura).

        Atualmente não usado pelo pipeline — disponível para análises externas
        ou para filtrar deteções por tamanho mínimo da mão.
        """
        width = self.bottom_right.x - self.top_left.x
        height = self.bottom_right.y - self.top_left.y
        return width * height

    def contains(self, point: Point) -> bool:
        """Verifica se um ponto está dentro do retângulo."""
        return (
            self.top_left.x <= point.x <= self.bottom_right.x
            and self.top_left.y <= point.y <= self.bottom_right.y
        )
