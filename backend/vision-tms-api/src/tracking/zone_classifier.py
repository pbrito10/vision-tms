from __future__ import annotations

from src.detection.hand_detection import HandDetection
from src.roi.region_of_interest import RegionOfInterest
from src.roi.roi_collection import RoiCollection

# None indica que a mão está em trânsito — fora de qualquer zona definida
ClassifiedHand = tuple[HandDetection, RegionOfInterest | None]


class ZoneClassifier:
    """Mapeia deteções para zonas frame a frame. Sem estado, sem interpretação.

    Apenas reporta o que vê — se uma mão está em trânsito devolve None.
    Acumular e interpretar esse None é responsabilidade da TaskStateMachine.
    """

    def __init__(self, rois: RoiCollection) -> None:
        self._rois = rois

    def classify(self, detections: list[HandDetection]) -> list[ClassifiedHand]:
        return [self._classify_one(detection) for detection in detections]

    def _classify_one(self, detection: HandDetection) -> ClassifiedHand:
        # O ponto de referência é o centróide dos MCP e não o pulso nem as fingertips —
        # ver KeypointCollection.finger_mcp_centroid() para a justificação.
        point = detection.keypoints.finger_mcp_centroid()
        zone  = self._rois.find_zone_for_point(point)
        return detection, zone
