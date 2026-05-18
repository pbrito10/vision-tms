from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Callable

from src.detection.hand_detection import HandDetection
from src.shared.hand_side import HandSide
from src.shared.task_state import TaskState
from src.tracking.activation_strategy import ActivationStrategy
from src.tracking.task_event import TaskEvent
from src.tracking.zone_classifier import ClassifiedHand


class StateMachineInterface(ABC):
    """Interface mínima que o orquestrador precisa de ambas as máquinas.

    state() existe porque a máquina pode regressar a IDLE sem emitir evento
    (ex: mão sai durante o dwell). O orquestrador precisa de detetar isso
    para limpar o ponteiro _active — caso contrário a próxima zona usaria
    a máquina errada.
    """

    @abstractmethod
    def update(
        self,
        classified_hands: list[ClassifiedHand],
        frame_time: datetime,
    ) -> TaskEvent | None: ...

    @abstractmethod
    def state(self) -> TaskState: ...


class _BaseStateMachine(StateMachineInterface):
    """Lógica partilhada pelas máquinas de estados de uma e duas mãos.

    Encapsula parâmetros de construção comuns, state() e _complete_task(),
    eliminando duplicação entre OneHandStateMachine e TwoHandsStateMachine.

    _reset_to_idle() é abstracto porque cada máquina tem campos de estado
    diferentes que precisam de ser limpos de forma específica.
    """

    def __init__(
        self,
        dwell_time:       timedelta,
        task_timeout:     timedelta,
        cycle_number_fn:  Callable[[], int],
        strategy:         ActivationStrategy,
    ) -> None:
        self._dwell_time      = dwell_time
        self._task_timeout    = task_timeout
        self._cycle_number_fn = cycle_number_fn
        self._strategy        = strategy
        self._task_state:   TaskState       = TaskState.IDLE
        self._tracked_zone: str | None      = None
        self._task_start:   datetime | None = None

    def state(self) -> TaskState:
        return self._task_state

    def _complete_task(self, end_time: datetime, was_forced: bool) -> TaskEvent:
        """Cria o TaskEvent, chama _reset_to_idle() e devolve o evento ao orquestrador."""
        event = TaskEvent.create(
            zone_name=self._tracked_zone,
            start_time=self._task_start,
            end_time=end_time,
            cycle_number=self._cycle_number_fn(),
            was_forced=was_forced,
        )
        self._reset_to_idle()
        return event

    @abstractmethod
    def _reset_to_idle(self) -> None:
        """Repõe todos os campos de estado a None/IDLE. Implementado por cada subclasse."""
        ...


class OneHandStateMachine(_BaseStateMachine):
    """Máquina de estados para zonas que exigem apenas uma mão.

    IDLE → DWELLING → TASK_IN_PROGRESS → IDLE

    O critério de "mão confirmada na zona" é delegado na ActivationStrategy
    (injeção por construtor) — trocar de stillness para tempo fixo não toca aqui.
    """

    def __init__(
        self,
        dwell_time:       timedelta,
        task_timeout:     timedelta,
        cycle_number_fn:  Callable[[], int],
        strategy:         ActivationStrategy,
    ) -> None:
        super().__init__(dwell_time, task_timeout, cycle_number_fn, strategy)
        self._prev_detection: HandDetection | None = None
        self._dwell_start:    datetime | None      = None

    def update(self, classified_hands: list[ClassifiedHand], frame_time: datetime) -> TaskEvent | None:
        if self._task_state == TaskState.IDLE:
            return self._handle_idle(classified_hands)
        if self._task_state == TaskState.DWELLING:
            return self._handle_dwelling(classified_hands, frame_time)
        if self._task_state == TaskState.TASK_IN_PROGRESS:
            return self._handle_in_progress(classified_hands, frame_time)
        return None

    def _handle_idle(self, classified_hands: list[ClassifiedHand]) -> None:
        # Fixa a primeira zona encontrada e avança — ignora as restantes
        # (o orquestrador garante que só chegamos aqui com _active a apontar para nós).
        for _, zone in classified_hands:
            if zone is None:
                continue
            self._tracked_zone   = zone.name
            self._prev_detection = None
            self._dwell_start    = None
            self._task_state     = TaskState.DWELLING
            return

    def _handle_dwelling(
        self,
        classified_hands: list[ClassifiedHand],
        frame_time: datetime,
    ) -> None:
        hand = self._hand_in_tracked_zone(classified_hands)

        if hand is None:
            # Saiu antes do dwell expirar — descarta sem emitir evento
            self._reset_to_idle()
            return

        if not self._strategy.is_active(hand, self._prev_detection):
            # Mão em movimento: reinicia o timer mas guarda a posição atual
            # para poder calcular velocidade no próximo frame.
            self._dwell_start    = None
            self._prev_detection = hand
            return

        if self._dwell_start is None:
            self._dwell_start = frame_time
        elif frame_time - self._dwell_start >= self._dwell_time:
            self._task_state = TaskState.TASK_IN_PROGRESS
            self._task_start = frame_time

        self._prev_detection = hand

    def _handle_in_progress(
        self,
        classified_hands: list[ClassifiedHand],
        frame_time: datetime,
    ) -> TaskEvent | None:
        if frame_time - self._task_start >= self._task_timeout:
            return self._complete_task(frame_time, was_forced=True)
        if self._hand_in_tracked_zone(classified_hands) is None:
            return self._complete_task(frame_time, was_forced=False)
        return None

    def _hand_in_tracked_zone(
        self,
        classified_hands: list[ClassifiedHand],
    ) -> HandDetection | None:
        for detection, zone in classified_hands:
            if zone is not None and zone.name == self._tracked_zone:
                return detection
        return None

    def _reset_to_idle(self) -> None:
        self._task_state     = TaskState.IDLE
        self._tracked_zone   = None
        self._prev_detection = None
        self._dwell_start    = None
        self._task_start     = None


class TwoHandsStateMachine(_BaseStateMachine):
    """Máquina de estados para zonas que exigem as duas mãos simultaneamente.

    IDLE → WAITING_SECOND_HAND → DWELLING_TWO_HANDS → TASK_IN_PROGRESS → IDLE

    O dwell só começa quando ambas as mãos estão paradas ao mesmo tempo.
    Se qualquer mão sair durante TASK_IN_PROGRESS, a tarefa fecha imediatamente
    — a lógica de montagem assume cooperação contínua de ambas as mãos.

    _prev_detections é um dict por HandSide para que cada mão tenha a sua
    referência de frame anterior independente no cálculo de velocidade.

    WAITING_SECOND_HAND tem timeout igual a dwell_time: se a segunda mão não
    chegar (ou uma mão ficar presa na zona sem a outra), a máquina regressa a
    IDLE e desbloqueia o sistema. Ajustável via tracking.dwell_time_seconds.
    """

    def __init__(
        self,
        dwell_time:       timedelta,
        task_timeout:     timedelta,
        cycle_number_fn:  Callable[[], int],
        strategy:         ActivationStrategy,
    ) -> None:
        super().__init__(dwell_time, task_timeout, cycle_number_fn, strategy)
        self._prev_detections: dict[HandSide, HandDetection] = {}
        self._waiting_start:   datetime | None               = None
        self._dwell_start:     datetime | None               = None

    def update(self, classified_hands: list[ClassifiedHand], frame_time: datetime) -> TaskEvent | None:
        if self._task_state == TaskState.IDLE:
            return self._handle_idle(classified_hands)
        if self._task_state == TaskState.WAITING_SECOND_HAND:
            return self._handle_waiting_second_hand(classified_hands, frame_time)
        if self._task_state == TaskState.DWELLING_TWO_HANDS:
            return self._handle_dwelling_two_hands(classified_hands, frame_time)
        if self._task_state == TaskState.TASK_IN_PROGRESS:
            return self._handle_in_progress(classified_hands, frame_time)
        return None

    def _handle_idle(self, classified_hands: list[ClassifiedHand]) -> None:
        for _, zone in classified_hands:
            if zone is None:
                continue
            self._tracked_zone    = zone.name
            self._prev_detections = {}
            self._waiting_start   = None
            self._dwell_start     = None
            self._task_state      = TaskState.WAITING_SECOND_HAND
            return

    def _handle_waiting_second_hand(
        self,
        classified_hands: list[ClassifiedHand],
        frame_time: datetime,
    ) -> None:
        hands = self._hands_in_tracked_zone(classified_hands)

        if len(hands) == 0:
            # A primeira mão saiu antes da segunda chegar — recomeça do zero
            self._reset_to_idle()
            return

        if self._waiting_start is None:
            self._waiting_start = frame_time

        if frame_time - self._waiting_start >= self._dwell_time:
            # Segunda mão não chegou dentro do tempo de dwell — desbloqueia
            self._reset_to_idle()
            return

        if len(hands) >= 2:
            self._dwell_start = None
            self._task_state  = TaskState.DWELLING_TWO_HANDS

    def _handle_dwelling_two_hands(
        self,
        classified_hands: list[ClassifiedHand],
        frame_time: datetime,
    ) -> None:
        hands = self._hands_in_tracked_zone(classified_hands)

        if len(hands) < 2:
            self._reset_to_idle()
            return

        both_still = all(
            self._strategy.is_active(hand, self._prev_detections.get(hand.hand_side))
            for hand in hands
        )

        if not both_still:
            self._dwell_start = None
        elif self._dwell_start is None:
            self._dwell_start = frame_time
        elif frame_time - self._dwell_start >= self._dwell_time:
            self._task_state = TaskState.TASK_IN_PROGRESS
            self._task_start = frame_time

        for hand in hands:
            self._prev_detections[hand.hand_side] = hand

    def _handle_in_progress(
        self,
        classified_hands: list[ClassifiedHand],
        frame_time: datetime,
    ) -> TaskEvent | None:
        if frame_time - self._task_start >= self._task_timeout:
            return self._complete_task(frame_time, was_forced=True)
        if len(self._hands_in_tracked_zone(classified_hands)) < 2:
            return self._complete_task(frame_time, was_forced=False)
        return None

    def _hands_in_tracked_zone(
        self,
        classified_hands: list[ClassifiedHand],
    ) -> list[HandDetection]:
        return [
            detection for detection, zone in classified_hands
            if zone is not None and zone.name == self._tracked_zone
        ]

    def _reset_to_idle(self) -> None:
        self._task_state      = TaskState.IDLE
        self._tracked_zone    = None
        self._prev_detections = {}
        self._waiting_start   = None
        self._dwell_start     = None
        self._task_start      = None


class TaskStateMachine:
    """Orquestrador: escolhe a máquina certa e impõe a regra de uma tarefa de cada vez.

    Enquanto _active não é None, entradas noutras zonas são ignoradas —
    o operador tem de terminar o que começou antes de o sistema reconhecer
    uma nova zona.

    _active é limpo quando a máquina interna regressa a IDLE, quer por
    conclusão de tarefa quer por saída antecipada. Sem este check, uma saída
    durante o dwell deixaria _active a apontar para a máquina errada e a
    próxima zona podia ser tratada com os requisitos errados (ex: Montagem
    exigia two-hands mas receberia one-hand, ou vice-versa).
    """

    def __init__(
        self,
        one_hand:        OneHandStateMachine,
        two_hands:       TwoHandsStateMachine,
        two_hands_zones: list[str],
    ) -> None:
        self._one_hand        = one_hand
        self._two_hands       = two_hands
        self._two_hands_zones = set(two_hands_zones)
        self._active:         StateMachineInterface | None = None

    def update(
        self,
        classified_hands: list[ClassifiedHand],
        frame_time: datetime,
    ) -> TaskEvent | None:
        if self._active is not None:
            event = self._active.update(classified_hands, frame_time)
            if self._active.state() == TaskState.IDLE:
                self._active = None
            return event

        return self._activate_best_zone(classified_hands, frame_time)

    def _activate_best_zone(
        self,
        classified_hands: list[ClassifiedHand],
        frame_time: datetime,
    ) -> TaskEvent | None:
        # Conta quantas mãos estão em cada zona neste frame
        hands_per_zone: dict[str, int] = {}
        for _, zone in classified_hands:
            if zone is not None:
                hands_per_zone[zone.name] = hands_per_zone.get(zone.name, 0) + 1

        # Tenta ativar zonas two-hands primeiro (requisito mais exigente)
        for zone_name, count in hands_per_zone.items():
            machine = self._machine_for_zone(zone_name, count)
            if machine is not None:
                self._active = machine
                return self._active.update(classified_hands, frame_time)

        # Zona de uma mão: filtra zonas two-hands para que _handle_idle não as possa
        # seleccionar acidentalmente como zona rastreada (ex: mão em repouso em Montagem
        # enquanto a outra mão trabalha em Porca — sem filtro, one_hand rastrearia Montagem)
        filtered = [
            (d, z) for d, z in classified_hands
            if z is None or z.name not in self._two_hands_zones
        ]
        for _, zone in filtered:
            if zone is not None:
                self._active = self._one_hand
                return self._active.update(filtered, frame_time)

        return None

    def _machine_for_zone(
        self, zone_name: str, hand_count: int
    ) -> StateMachineInterface | None:
        """Devolve a máquina adequada se o critério de ativação da zona está cumprido.

        Ponto de extensão OCP: para adicionar um novo tipo de zona, adiciona a lógica
        aqui sem modificar _activate_best_zone.
        """
        if zone_name in self._two_hands_zones and hand_count >= 2:
            return self._two_hands
        return None

    def current_state(self) -> TaskState:
        if self._active is None:
            return TaskState.IDLE
        return self._active.state()
