from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)


def run(detection_queue, stop_event, config, roi_path):
    import queue
    import time
    from pathlib import Path

    from src.roi.json_roi_repository import JsonRoiRepository
    from src.video.frame_annotator import ZoneColorScheme
    from src.video.live_frame import JpegFramePublisher, annotate_detection_frame

    rois = JsonRoiRepository(path=Path(roi_path)).load()
    cycle_order = config["tracking"]["cycle_zone_order"]
    color_scheme = ZoneColorScheme(
        start_zone=config["tracking"].get("start_zone") or (cycle_order[0] if cycle_order else None),
        output_zone=config["tracking"]["exit_zone"],
        assembly_zones=tuple(config["tracking"]["two_hands_zones"]),
    )
    publisher = JpegFramePublisher.from_config(config)
    previous_time = time.perf_counter()

    while not stop_event.is_set():
        try:
            frame_rgb, detections = detection_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        now = time.perf_counter()
        elapsed = now - previous_time
        fps = 1.0 / elapsed if elapsed > 0 else 0.0
        previous_time = now

        try:
            frame_bgr = annotate_detection_frame(
                frame_rgb,
                detections,
                rois=rois,
                color_scheme=color_scheme,
                fps=fps,
            )
            if not publisher.publish(frame_bgr):
                LOGGER.warning("Failed to encode preview frame as JPEG")
        except Exception:
            LOGGER.exception("Failed to publish preview frame")
