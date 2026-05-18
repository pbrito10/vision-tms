from __future__ import annotations


def run_camera(frame_queue, stop_event, config):
    """Child-process entrypoint for camera capture."""
    from src.shared.logging_config import configure_logging
    import capture_process

    configure_logging()
    capture_process.run(frame_queue, stop_event, config)


def run_detector(frame_queue, detection_queue, stop_event, config):
    """Child-process entrypoint for hand detection."""
    from src.shared.logging_config import configure_logging
    import detection_process

    configure_logging()
    detection_process.run(frame_queue, detection_queue, stop_event, config)


def run_pipeline(detection_queue, stop_event, config, roi_path):
    """Child-process entrypoint for tracking, metrics and outputs."""
    from src.shared.logging_config import configure_logging
    import monitor_process

    configure_logging()
    monitor_process.run(detection_queue, stop_event, config, roi_path)
