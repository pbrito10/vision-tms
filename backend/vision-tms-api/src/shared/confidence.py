from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Confidence:
    """Valor de confiança de uma deteção, sempre no intervalo [0.0, 1.0].

    Substituir float solto por este tipo torna a intenção explícita
    e valida o intervalo logo na criação.
    """

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Confidence deve estar entre 0.0 e 1.0, recebido: {self.value}")

    def is_above(self, threshold: Confidence) -> bool:
        """Verifica se a confiança supera o threshold — evita comparar floats pelo código."""
        return self.value >= threshold.value

    def as_percentage(self) -> float:
        """Devolve o valor em percentagem (ex: 0.87 → 87.0)."""
        return self.value * 100.0
