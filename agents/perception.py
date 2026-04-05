"""
Perception agent (Pass 9 MVP).

Provides deterministic victim detection scoring from drone/victim snapshots.
This is lightweight by design so it can run in demo mode without CV models.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import math


@dataclass
class DetectionResult:
    victim_id: str
    detected: bool
    confidence: float
    detected_by: str
    position: Tuple[float, float, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "victim_id": self.victim_id,
            "detected": self.detected,
            "confidence": round(self.confidence, 3),
            "detected_by": self.detected_by,
            "position": tuple(self.position),
            "is_confirmed": self.confidence >= 0.65,
        }


class PerceptionAgent:
    """
    Lightweight perception layer that estimates victim detection confidence
    based on drone-to-victim distance and sensor availability.
    """

    def __init__(self, detection_radius: float = 50.0, confirmation_confidence: float = 0.65):
        self.detection_radius = float(detection_radius)
        self.confirmation_confidence = float(confirmation_confidence)

    @staticmethod
    def _distance(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
        ax, ay, az = (list(a) + [0.0, 0.0, 0.0])[:3]
        bx, by, bz = (list(b) + [0.0, 0.0, 0.0])[:3]
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)

    @staticmethod
    def _sensor_bonus(drone: Dict[str, Any]) -> float:
        sensors = drone.get("sensors", {}) if isinstance(drone, dict) else {}
        bonus = 0.0
        if sensors.get("thermal", False):
            bonus += 0.20
        if sensors.get("camera", False):
            bonus += 0.15
        if sensors.get("lidar", False):
            bonus += 0.10
        return bonus

    def detect_victims(
        self,
        drones: List[Dict[str, Any]],
        victims: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Score each victim using nearest drone + sensor bonus.
        Returns normalized detection dictionaries used by upstream triage/state.
        """
        if not victims:
            return []

        outputs: List[Dict[str, Any]] = []
        for victim in victims:
            victim_id = str(victim.get("victim_id") or victim.get("id") or "unknown")
            vpos = tuple(victim.get("position", (0.0, 0.0, 0.0)))

            best_conf = 0.0
            best_drone = "none"
            for drone in drones or []:
                dpos = tuple(drone.get("position", (0.0, 0.0, 0.0)))
                dist = self._distance(dpos, vpos)
                if dist > self.detection_radius:
                    continue

                # Distance confidence: 1.0 when close, decreases to 0 near radius.
                distance_score = max(0.0, 1.0 - (dist / max(self.detection_radius, 1.0)))
                conf = min(1.0, 0.25 + (0.55 * distance_score) + self._sensor_bonus(drone))
                if conf > best_conf:
                    best_conf = conf
                    best_drone = str(drone.get("drone_id") or drone.get("id") or "unknown")

            result = DetectionResult(
                victim_id=victim_id,
                detected=best_conf >= 0.30,
                confidence=best_conf,
                detected_by=best_drone if best_conf >= self.confirmation_confidence else "none",
                position=vpos,
            ).to_dict()
            outputs.append(result)

        return outputs
