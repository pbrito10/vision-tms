# frame_queue → MediaPipe → detection_queue (frame + lista de HandDetection)
#
# Frame e deteções são emitidos juntos para garantir sincronismo: o consumidor
# (display ou monitor) precisa do frame exato em que as mãos foram detetadas,
# não de um frame mais recente com deteções de um frame mais antigo.
#
# O get() com timeout=0.1 s serve para que o loop verifique stop_event
# regularmente em vez de bloquear indefinidamente se a câmara parar.
#
# O detector é tipado como DetectorInterface para tornar explícita a
# dependência de abstração (DIP) — trocar o backend de deteção não toca no loop.


def run(frame_queue, detection_queue, stop_event, config):
    import queue

    from src.detection.detector_interface import DetectorInterface
    from src.detection.mediapipe_detector import MediapipeDetector

    detector: DetectorInterface = MediapipeDetector(
        model_path=config["detection"]["model_path"],
        max_num_hands=config["detection"]["max_num_hands"],
        min_detection_confidence=config["detection"]["min_detection_confidence"],
        min_tracking_confidence=config["detection"]["min_tracking_confidence"],
    )

    try:
        while not stop_event.is_set():
            try:
                frame = frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            maos = detector.detect(frame)

            try:
                detection_queue.put((frame, maos), timeout=0.1)
            except queue.Full:
                # O consumidor está lento (ou parou) — descartamos em vez de bloquear
                pass
    finally:
        detector.release()
