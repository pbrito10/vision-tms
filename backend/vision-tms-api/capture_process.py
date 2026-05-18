# Câmara → frame_queue (RGB, espelho horizontal)
#
# OpenCV captura em BGR; convertemos para RGB aqui, uma vez, para não forçar
# o detector a fazer esse trabalho em cada frame.
#
# Quando a queue está cheia, descartamos o frame mais antigo em vez de bloquear.
# A alternativa (bloquear) acumularia frames velhos: o utilizador veria sempre
# o passado em vez do presente. Latência baixa > completude do histórico.


def run(frame_queue, stop_event, config):
    import os
    import queue
    import cv2

    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY") or not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":0"

    from src.video.camera import Camera

    camera = Camera.from_config(config["camera"])

    try:
        while not stop_event.is_set():
            frame = camera.read_frame()

            if frame is None:
                stop_event.set()
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass

            frame_queue.put(frame_rgb)
    finally:
        camera.release()
