"""
Routing agent (Pass 9 MVP).

Provides simple waypoint planning with a deterministic anti-jamming fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import math


@dataclass
class RoutePlan:
    drone_id: str
    mode: str
    waypoints: List[Tuple[float, float, float]]
    distance_m: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drone_id": self.drone_id,
            "mode": self.mode,
            "waypoints": [tuple(p) for p in self.waypoints],
            "distance_m": round(self.distance_m, 2),
        }


class RoutingAgent:
    def __init__(self, safety_altitude_m: float = 30.0):
        self.safety_altitude_m = float(safety_altitude_m)

    @staticmethod
    def _distance(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
        ax, ay, az = (list(a) + [0.0, 0.0, 0.0])[:3]
        bx, by, bz = (list(b) + [0.0, 0.0, 0.0])[:3]
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)

    def plan_route(
        self,
        drone_id: str,
        start: Tuple[float, float, float],
        target: Tuple[float, float, float],
        *,
        jam_detected: bool = False,
        return_base: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Dict[str, Any]:
        """
        Create a basic 3-point route:
        - climb to safety altitude
        - translate horizontally
        - descend to target
        If jamming is detected, route to return_base instead.
        """
        sx, sy, sz = (list(start) + [0.0, 0.0, 0.0])[:3]
        tx, ty, tz = (list(target) + [0.0, 0.0, 0.0])[:3]

        if jam_detected:
            bx, by, bz = (list(return_base) + [0.0, 0.0, 0.0])[:3]
            waypoints = [(sx, sy, self.safety_altitude_m), (bx, by, self.safety_altitude_m), (bx, by, bz)]
            mode = "jam_fallback_rtb"
            dist = (
                self._distance((sx, sy, sz), waypoints[0])
                + self._distance(waypoints[0], waypoints[1])
                + self._distance(waypoints[1], waypoints[2])
            )
            return RoutePlan(drone_id=drone_id, mode=mode, waypoints=waypoints, distance_m=dist).to_dict()

        waypoints = [(sx, sy, self.safety_altitude_m), (tx, ty, self.safety_altitude_m), (tx, ty, tz)]
        dist = (
            self._distance((sx, sy, sz), waypoints[0])
            + self._distance(waypoints[0], waypoints[1])
            + self._distance(waypoints[1], waypoints[2])
        )
        return RoutePlan(drone_id=drone_id, mode="direct_safe_altitude", waypoints=waypoints, distance_m=dist).to_dict()
