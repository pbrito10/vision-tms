from __future__ import annotations

import logging

# Pipeline principal: classifica zonas, atualiza a state machine,
# calcula métricas e escreve outputs em tempo real.
#
# Este módulo é carregado num processo filho (spawn) — todos os imports
# ficam dentro das funções/métodos para evitar carregar dependências pesadas
# (OpenCV, MediaPipe) no processo pai sem necessidade.

LOGGER = logging.getLogger(__name__)


def _session_start_from_config(config, datetime_cls):
    raw_value = config.get("_runtime", {}).get("session_started_at")
    if isinstance(raw_value, str):
        try:
            return datetime_cls.fromisoformat(raw_value)
        except ValueError:
            LOGGER.warning("Invalid runtime session_started_at: %s", raw_value)
    return datetime_cls.now()


def run(detection_queue, stop_event, config, roi_path):
    try:
        _MonitorSession(config, roi_path).execute(detection_queue, stop_event)
    except Exception:
        LOGGER.exception("Monitor process stopped unexpectedly")
        raise


class _ZoneTransitionTracker:
    """Deteta transições de zona frame a frame e delega o registo no DebugLogger.

    Isola o estado de zona anterior e a última deteção por zona — antes
    espalhados em _MonitorSession — separando esta responsabilidade do orquestrador.
    """

    def __init__(self, session_start) -> None:  # session_start: datetime
        self._session_start                     = session_start
        self._prev_zones: dict[str, str | None] = {}
        self._last_detection_per_zone: dict     = {}

    def track(self, classified_hands, now, frame_idx: int, debug_logger) -> None:
        """Atualiza deteções e regista transições de entrada/saída de zonas."""
        self._update_last_detections(classified_hands)
        self._log_transitions(classified_hands, now, frame_idx, debug_logger)

    def _update_last_detections(self, classified_hands) -> None:
        for detection, zone in classified_hands:
            if zone is not None:
                self._last_detection_per_zone[zone.name] = detection

    def _log_transitions(self, classified_hands, now, frame_idx, debug_logger) -> None:
        current = {}
        for detection, zone in classified_hands:
            zone_name = zone.name if zone is not None else None
            current[detection.hand_side.value] = (zone_name, detection)

        relative = now - self._session_start

        # A união dos dois conjuntos de chaves apanha entradas E saídas:
        # chaves só em prev → mão saiu; chaves só em current → mão entrou.
        for key in set(self._prev_zones) | set(current):
            self._check_transition(key, current, now, relative, frame_idx, debug_logger)

        self._prev_zones = {k: v[0] for k, v in current.items()}

    def _check_transition(self, key, current, now, relative, frame_idx, debug_logger) -> None:
        prev_zone            = self._prev_zones.get(key)
        curr_zone, detection = current.get(key, (None, None))

        if prev_zone == curr_zone:
            return

        if prev_zone is not None:
            last_det = self._last_detection_per_zone.get(prev_zone)
            if last_det is not None:
                debug_logger.log_zone_exit(now, relative, prev_zone, last_det, frame_idx)

        if curr_zone is not None and detection is not None:
            debug_logger.log_zone_enter(now, relative, curr_zone, detection, frame_idx)


class _DetectionGapTracker:
    """Deteta periodos sem detecao por mao e guarda evidencias."""

    def __init__(
        self,
        threshold_s: float,
        session_start,
        output_dir,
        cycle_number_fn,
        rois,
        color_scheme,
    ) -> None:
        from datetime import timedelta

        self._threshold = timedelta(seconds=threshold_s)
        self._session_start = session_start
        self._output_dir = output_dir
        self._cycle_number_fn = cycle_number_fn
        self._rois = rois
        self._color_scheme = color_scheme
        self._seen_hands: set[str] = set()
        self._gap_start_by_hand: dict[str, object] = {}
        self._gap_frame_by_hand: dict[str, object] = {}
        self._gaps_per_cycle: dict[tuple[int, str], int] = {}

    def update(self, detections, now, frame_rgb, debug_logger) -> None:
        current_hands = {detection.hand_side.value for detection in detections}

        for hand_side in current_hands:
            if hand_side in self._gap_start_by_hand:
                self._flush(hand_side, now, debug_logger)

        tracked_hands = self._seen_hands | current_hands
        for hand_side in tracked_hands - current_hands:
            if hand_side not in self._gap_start_by_hand:
                self._gap_start_by_hand[hand_side] = now
                self._gap_frame_by_hand[hand_side] = frame_rgb

        self._seen_hands |= current_hands

    def flush(self, now, debug_logger) -> None:
        for hand_side in list(self._gap_start_by_hand):
            self._flush(hand_side, now, debug_logger)

    def _flush(self, hand_side: str, now, debug_logger) -> None:
        gap_start = self._gap_start_by_hand[hand_side]
        duration = now - gap_start
        if duration >= self._threshold:
            relative = gap_start - self._session_start
            debug_logger.log_detection_gap(gap_start, relative, duration, hand_side)
            self._save_frame(hand_side)
        self._gap_start_by_hand.pop(hand_side, None)
        self._gap_frame_by_hand.pop(hand_side, None)

    def _save_frame(self, hand_side: str) -> None:
        import cv2
        import numpy as np
        from src.video import frame_annotator

        gap_frame = self._gap_frame_by_hand.get(hand_side)
        if gap_frame is None:
            return

        cycle = self._cycle_number_fn()
        key = (cycle, hand_side)
        count = self._gaps_per_cycle.get(key, 0) + 1
        self._gaps_per_cycle[key] = count

        suffix = f"_{count}" if count > 1 else ""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename = self._output_dir / f"gap_{hand_side}_ciclo_{cycle:03d}{suffix}.jpg"

        frame_bgr = cv2.cvtColor(np.asarray(gap_frame), cv2.COLOR_RGB2BGR)
        frame_annotator.draw_rois(frame_bgr, self._rois, color_scheme=self._color_scheme)
        cv2.imwrite(str(filename), frame_bgr)


class _MonitorSession:
    """Orquestrador da sessão de monitorização.

    Coordena os componentes do pipeline — cada componente com estado próprio
    está isolado na sua classe, e cada método trata de uma responsabilidade.
    """

    def __init__(self, config: dict, roi_path: str) -> None:
        from datetime import datetime, timedelta
        from pathlib import Path

        from src.metrics.metrics_calculator import MetricsCalculator
        from src.output.excel_exporter import ExcelExporter
        from src.output.influx_writer import InfluxWriter
        from src.output.session_output import create_session_output_layout
        from src.output.video_recorder import VideoRecorder
        from src.roi.json_roi_repository import JsonRoiRepository
        from src.tracking.activation_strategy import StillnessDwellStrategy
        from src.tracking.cycle_tracker import CycleTracker
        from src.tracking.task_event_merger import ConsecutiveTaskMerger
        from src.tracking.task_labeler import TaskLabeler
        from src.tracking.zone_classifier import ZoneClassifier
        from src.video.frame_annotator import ZoneColorScheme
        from src.video.live_frame import JpegFramePublisher

        self._config        = config
        self._session_start = _session_start_from_config(config, datetime)
        self._frame_idx     = 0
        self._last_metrics_write = datetime.min
        self._refresh_interval   = timedelta(seconds=config["dashboard"]["refresh_seconds"])
        self._frame_publisher = JpegFramePublisher.from_config(config)
        self._frame_output_path    = self._frame_publisher.path
        self._state_output_path    = Path(config["dashboard"].get("state_path", "dashboard/data/program_state.json"))
        self._state_output_path.parent.mkdir(parents=True, exist_ok=True)

        rois                     = JsonRoiRepository(path=Path(roi_path)).load()
        self._rois               = rois
        cycle_order              = config["tracking"]["cycle_zone_order"]
        self._color_scheme       = ZoneColorScheme(
            start_zone=config["tracking"].get("start_zone") or (cycle_order[0] if cycle_order else None),
            output_zone=config["tracking"]["exit_zone"],
            assembly_zones=tuple(config["tracking"]["two_hands_zones"]),
        )
        self._session_output     = create_session_output_layout(config, self._session_start)
        self._zone_classifier    = ZoneClassifier(rois)
        self._transition_tracker = _ZoneTransitionTracker(self._session_start)
        self._task_merger       = ConsecutiveTaskMerger()

        dwell_time   = timedelta(seconds=config["tracking"]["dwell_time_seconds"])
        task_timeout = timedelta(seconds=config["tracking"]["task_timeout_seconds"])
        two_hands_missing_tolerance = timedelta(
            seconds=config["tracking"].get("two_hands_missing_tolerance_seconds", 0.0)
        )
        strategy     = StillnessDwellStrategy(config["tracking"]["stillness_threshold_px"])

        self._cycle_tracker    = CycleTracker(
            exit_zone=config["tracking"]["exit_zone"],
            expected_order=config["tracking"]["cycle_zone_order"],
            repeat_rules=config["tracking"].get("cycle_repeat_rules", []),
        )
        self._gap_tracker = _DetectionGapTracker(
            threshold_s=config["tracking"].get("detection_gap_threshold_s", 1.0),
            session_start=self._session_start,
            output_dir=self._session_output.gap_frames_dir,
            cycle_number_fn=self._cycle_tracker.current_cycle_number,
            rois=rois,
            color_scheme=self._color_scheme,
        )
        self._metrics = MetricsCalculator(self._session_start, config["tracking"]["zones"])
        self._task_labeler = TaskLabeler(
            assembly_zone=config["tracking"].get("assembly_zone", "Montagem"),
            labels_by_previous_zone=config["tracking"].get("assembly_task_labels", {}),
        )
        self._excel_exporter = ExcelExporter(self._session_output.session_dir, self._session_start)
        self._video_recorder = VideoRecorder(
            self._session_output.video_path,
            fps=config["output"].get("video_fps", 10.0),
            enabled=config["output"].get("record_video", False),
        )
        self._influx_writer = InfluxWriter.from_config(config, self._session_start)
        self._state_machine = self._build_state_machine(
            dwell_time,
            task_timeout,
            two_hands_missing_tolerance,
            strategy,
        )

    def _build_state_machine(self, dwell_time, task_timeout, two_hands_missing_tolerance, strategy):
        """Monta as duas máquinas de estado e o orquestrador TaskStateMachine.

        Separado do __init__ para isolar a lógica de construção — os imports
        são locais porque os de __init__ não estão em scope neste método.
        """
        from src.tracking.task_state_machine import (
            OneHandStateMachine, TaskStateMachine, TwoHandsStateMachine,
        )
        one_hand  = OneHandStateMachine(dwell_time, task_timeout, self._cycle_tracker.current_cycle_number, strategy)
        two_hands = TwoHandsStateMachine(
            dwell_time,
            task_timeout,
            self._cycle_tracker.current_cycle_number,
            strategy,
            missing_tolerance=two_hands_missing_tolerance,
        )
        return TaskStateMachine(one_hand, two_hands, self._config["tracking"]["two_hands_zones"])

    def execute(self, detection_queue, stop_event) -> None:
        from src.events.debug_logger import DebugLogger
        from src.output.session_config_snapshot import write_session_config_snapshot

        LOGGER.info("Session outputs: %s", self._session_output.session_dir)
        with DebugLogger(self._session_output.session_dir, self._session_start) as debug_logger:
            write_session_config_snapshot(debug_logger.path, self._config, self._rois)
            self._loop(detection_queue, stop_event, debug_logger)

    def _loop(self, detection_queue, stop_event, debug_logger) -> None:
        import queue

        try:
            while not stop_event.is_set():
                try:
                    frame_rgb, maos = detection_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                try:
                    self._process_frame(frame_rgb, maos, debug_logger)
                except Exception:
                    LOGGER.exception("Failed to process monitor frame %s", self._frame_idx + 1)
        finally:
            self._finalise(debug_logger)

    def _process_frame(self, frame_rgb, maos, debug_logger) -> None:
        from datetime import datetime

        self._frame_idx += 1
        now = datetime.now()

        self._gap_tracker.update(maos, now, frame_rgb, debug_logger)

        classified_hands = self._zone_classifier.classify(maos)
        self._transition_tracker.track(classified_hands, now, self._frame_idx, debug_logger)

        task_event = self._state_machine.update(classified_hands, now)
        self._log_task_diagnostics(debug_logger)
        if task_event is not None:
            self._handle_task_event_candidate(task_event, debug_logger)

        self._maybe_write_live_metrics(now)
        self._publish_program_state(classified_hands, now)
        annotated_frame = self._annotate_frame(frame_rgb, maos)
        self._record_frame(annotated_frame)
        self._publish_frame(annotated_frame)

    def _annotate_frame(self, frame_rgb, maos):
        from src.video.live_frame import annotate_detection_frame

        return annotate_detection_frame(
            frame_rgb,
            maos,
            rois=self._rois,
            color_scheme=self._color_scheme,
        )

    def _record_frame(self, frame_bgr) -> None:
        self._safe_output("write annotated video frame", self._video_recorder.write, frame_bgr)

    def _publish_program_state(self, classified_hands, now) -> None:
        import json

        detected_zones = []
        for _, zone in classified_hands:
            if zone is not None and zone.name not in detected_zones:
                detected_zones.append(zone.name)

        completed_steps   = self._cycle_tracker.current_sequence()
        expected_sequence = list(self._config["tracking"]["cycle_zone_order"])
        current_zone      = self._current_zone(detected_zones, expected_sequence, completed_steps)

        payload = {
            "captured_at": now.isoformat(timespec="seconds"),
            "current_zone": current_zone,
            "current_step_index": self._current_step_index(current_zone, expected_sequence, completed_steps),
            "completed_steps": completed_steps,
            "expected_sequence": expected_sequence,
            "cycle_number": self._cycle_tracker.current_cycle_number(),
        }

        try:
            temp_path = self._state_output_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            temp_path.replace(self._state_output_path)
        except OSError:
            LOGGER.exception("Failed to publish program state to %s", self._state_output_path)

    def _current_zone(self, detected_zones, expected_sequence, completed_steps):
        if not detected_zones:
            return None

        next_index = len(completed_steps)
        if next_index < len(expected_sequence) and expected_sequence[next_index] in detected_zones:
            return expected_sequence[next_index]

        for zone_name in detected_zones:
            if zone_name in expected_sequence:
                return zone_name

        return detected_zones[0]

    def _current_step_index(self, current_zone, expected_sequence, completed_steps):
        if current_zone is None:
            return None

        start_index = min(len(completed_steps), max(len(expected_sequence) - 1, 0))
        for index in range(start_index, len(expected_sequence)):
            if expected_sequence[index] == current_zone:
                return index

        for index, zone_name in enumerate(expected_sequence):
            if zone_name == current_zone:
                return index

        return None

    def _publish_frame(self, frame_bgr) -> None:
        try:
            if not self._frame_publisher.publish(frame_bgr):
                LOGGER.warning("Failed to encode program frame as JPEG")
        except Exception:
            LOGGER.exception("Failed to publish program frame to %s", self._frame_output_path)

    def _handle_task_event_candidate(self, task_event, debug_logger) -> None:
        completed_event = self._task_merger.push(task_event)
        if completed_event is not None:
            self._handle_task_event(completed_event, debug_logger)
        if self._should_flush_task_event_candidate(task_event):
            self._flush_pending_task_event(debug_logger)

    def _should_flush_task_event_candidate(self, task_event) -> bool:
        return (
            task_event.zone_name == self._config["tracking"]["exit_zone"]
            and not task_event.was_forced
        )

    def _flush_pending_task_event(self, debug_logger) -> None:
        completed_event = self._task_merger.flush()
        if completed_event is not None:
            self._handle_task_event(completed_event, debug_logger)

    def _handle_task_event(self, task_event, debug_logger) -> None:
        task_event = self._event_in_current_cycle(task_event)
        cycle_result = self._cycle_tracker.record(task_event)
        if self._cycle_tracker.last_event_started_new_cycle():
            self._record_cycle_result(cycle_result, debug_logger)
            cycle_result = None
            task_event = self._event_in_current_cycle(task_event)

        self._log_task(task_event, debug_logger)
        analysis_event = self._task_labeler.label(task_event)
        if analysis_event.counts_as_interruption:
            self._metrics.record_interruption(analysis_event.event.duration)
        else:
            self._metrics.record(analysis_event.event)

        self._safe_output(
            "append task event to Excel output",
            self._excel_exporter.add_event,
            analysis_event.event,
            analysis_event.counts_as_interruption,
        )
        self._safe_output(
            "write task event to InfluxDB",
            self._influx_writer.write_task_event,
            analysis_event.event,
            analysis_event.counts_as_interruption,
        )

        if cycle_result is not None:
            self._record_cycle_result(cycle_result, debug_logger)

    def _event_in_current_cycle(self, task_event):
        from dataclasses import replace

        return replace(task_event, cycle_number=self._cycle_tracker.current_cycle_number())

    def _record_cycle_result(self, cycle_result, debug_logger) -> None:
        if cycle_result is None:
            return

        self._metrics.record_cycle(cycle_result)
        self._safe_output("append cycle result to Excel output", self._excel_exporter.add_cycle_result, cycle_result)
        self._safe_output("write cycle result to InfluxDB", self._influx_writer.write_cycle_result, cycle_result)
        debug_logger.log_cycle_complete(cycle_result)
        self._safe_output("write live metrics to InfluxDB", self._influx_writer.write, self._metrics.snapshot())

    def _log_task(self, task_event, debug_logger) -> None:
        if task_event.was_forced:
            debug_logger.log_task_timeout(task_event)
            return
        debug_logger.log_task_complete(task_event)

    def _log_task_diagnostics(self, debug_logger) -> None:
        for diagnostic in self._state_machine.pop_diagnostics():
            debug_logger.log_task_rejected(diagnostic)

    def _maybe_write_live_metrics(self, now) -> None:
        if now - self._last_metrics_write >= self._refresh_interval:
            snapshot = self._metrics.snapshot()
            self._safe_output("write live metrics to InfluxDB", self._influx_writer.write, snapshot)
            self._last_metrics_write = now

    def _finalise(self, debug_logger) -> None:
        from datetime import datetime

        self._safe_output("flush detection gaps", self._gap_tracker.flush, datetime.now(), debug_logger)
        self._safe_output("flush pending task event", self._flush_pending_task_event, debug_logger)
        snapshot = self._metrics.snapshot()
        self._safe_output("write final metrics to InfluxDB", self._influx_writer.write, snapshot)
        self._safe_output("write final Excel output", self._excel_exporter.write, snapshot)
        self._safe_output("close annotated video", self._video_recorder.close)
        self._safe_output("close InfluxDB writer", self._influx_writer.close)

    def _safe_output(self, action: str, callback, *args) -> bool:
        try:
            callback(*args)
        except Exception:
            LOGGER.exception("Failed to %s", action)
            return False
        return True
