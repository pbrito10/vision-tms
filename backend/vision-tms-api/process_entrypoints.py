from __future__ import annotations


def run_camera(frame_queue, stop_event, config):
    """Child-process entrypoint for camera capture."""
    import capture_process

    capture_process.run(frame_queue, stop_event, config)


def run_detector(frame_queue, detection_queue, stop_event, config):
    """Child-process entrypoint for hand detection."""
    import detection_process

    detection_process.run(frame_queue, detection_queue, stop_event, config)


def run_pipeline(detection_queue, stop_event, config, roi_path):
    """Child-process entrypoint for tracking, metrics and outputs."""
    import monitor_process

    monitor_process.run(detection_queue, stop_event, config, roi_path)
