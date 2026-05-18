from enum import Enum


class TaskState(Enum):
    """Estados da máquina de estados de tarefas.

    Zonas normais (one_hand):
        IDLE → DWELLING → TASK_IN_PROGRESS → IDLE

    Zonas two_hands (ex: Zona de Montagem):
        IDLE → WAITING_SECOND_HAND → DWELLING_TWO_HANDS → TASK_IN_PROGRESS → IDLE

    Não existe estado TIMED_OUT — o timeout é uma transição forçada de
    TASK_IN_PROGRESS para IDLE, distinguida pelo was_forced no TaskEvent.
    """

    IDLE                = "IDLE"
    DWELLING            = "DWELLING"
    WAITING_SECOND_HAND = "WAITING_SECOND_HAND"
    DWELLING_TWO_HANDS  = "DWELLING_TWO_HANDS"
    TASK_IN_PROGRESS    = "TASK_IN_PROGRESS"
