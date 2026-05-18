from enum import Enum


class HandSide(Enum):
    """Qual das mãos foi detetada.

    Enum em vez de string para que um typo seja apanhado pelo Python
    em vez de originar um bug silencioso mais tarde.
    """

    LEFT = "left"
    RIGHT = "right"
