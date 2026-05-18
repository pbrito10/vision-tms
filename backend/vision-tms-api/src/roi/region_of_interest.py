from __future__ import annotations
from dataclasses import dataclass

from src.shared.point import Point

# Chaves do JSON — definidas aqui para que from_dict e to_dict usem a mesma fonte
_KEY_NAME = "name"
_KEY_X1   = "x1"
_KEY_Y1   = "y1"
_KEY_X2   = "x2"
_KEY_Y2   = "y2"


@dataclass(frozen=True)
class RegionOfInterest:
    """Zona retangular na bancada, identificada por nome.

    O nome vem da configuração de bancada validada pela API, o que garante
    consistência com cycle_zone_order e two_hands_zones.
    """

    name: str
    top_left: Point
    bottom_right: Point

    def contains(self, point: Point) -> bool:
        return (
            self.top_left.x <= point.x <= self.bottom_right.x
            and self.top_left.y <= point.y <= self.bottom_right.y
        )

    def to_dict(self) -> dict:
        return {
            _KEY_NAME: self.name,
            _KEY_X1:   self.top_left.x,
            _KEY_Y1:   self.top_left.y,
            _KEY_X2:   self.bottom_right.x,
            _KEY_Y2:   self.bottom_right.y,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RegionOfInterest:
        return cls(
            name=data[_KEY_NAME],
            top_left=Point(x=data[_KEY_X1], y=data[_KEY_Y1]),
            bottom_right=Point(x=data[_KEY_X2], y=data[_KEY_Y2]),
        )
