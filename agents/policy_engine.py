"""
RescueNet Policy Engine

Centralized safety/operations policy checks applied before mission execution.
Keeps LLM decisions autonomous but bounded by hard safety guardrails.
"""
from dataclasses import dataclass
from typing import Dict, List, Any, Tuple

from state.fleet_state import FleetState, DroneStatus


@dataclass
class PolicyConfig:
    min_battery_for_new_mission: float = 25.0
    min_reserve_available_drones: int = 1
    critical_override_score: float = 90.0
    low_battery_return_threshold: float = 20.0
    min_supply_drone_reserve: int = 0


class PolicyEngine:
    def __init__(self, config: PolicyConfig | None = None):
        self.config = config or PolicyConfig()

    def _distance(self, p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
        x1, y1, z1 = (list(p1) + [0, 0, 0])[:3]
        x2, y2, z2 = (list(p2) + [0, 0, 0])[:3]
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5

    def filter_assignments(self, assignments: List[Dict[str, str]], fleet: FleetState) -> List[Dict[str, str]]:
        """
        Enforce hard safety policies on top of coordinator assignments.
        """
        if not assignments:
            return []

        approved: List[Dict[str, str]] = []
        available_drones = [d for d in fleet.drones.values() if d.status == DroneStatus.AVAILABLE]
        supply_available = [d for d in available_drones if self._drone_role(d.id) == "supply"]

        for item in assignments:
            drone = fleet.drones.get(item.get("drone_id"))
            victim = fleet.victims.get(item.get("victim_id"))
            if not drone or not victim:
                continue

            # Policy 1: battery floor
            if float(getattr(drone, "battery", 0.0) or 0.0) < self.config.min_battery_for_new_mission:
                continue

            # Policy 2: keep standby reserve unless victim is high urgency
            triage = float(getattr(victim, "triage_score", 0.0) or 0.0)
            projected_available = max(0, len(available_drones) - len(approved) - 1)
            if projected_available < self.config.min_reserve_available_drones and triage < self.config.critical_override_score:
                continue

            # Policy 2b: keep minimal supply drone reserve for logistics continuity
            if self._drone_role(drone.id) == "supply":
                projected_supply = max(0, len(supply_available) - len([a for a in approved if self._drone_role(a["drone_id"]) == "supply"]) - 1)
                if projected_supply < self.config.min_supply_drone_reserve and triage < self.config.critical_override_score:
                    continue

            # Policy 3: simple distance sanity check (avoid absurd assignments)
            if self._distance(drone.position, victim.position) > 5000:
                continue

            approved.append(item)

        return approved

    def _drone_role(self, drone_id: str) -> str:
        did = (drone_id or "").lower()
        if "supply" in did or "cargo" in did:
            return "supply"
        return "rescue"

    def apply_recharge_policy(self, env: Any, fleet: FleetState) -> List[str]:
        """
        Route low-battery available drones to return/charge posture.
        Returns list of drone ids transitioned to return mode.
        """
        moved: List[str] = []
        low_ids = {
            d.id for d in fleet.drones.values()
            if float(getattr(d, "battery", 0.0) or 0.0) <= self.config.low_battery_return_threshold
            and d.status == DroneStatus.AVAILABLE
        }
        if not low_ids:
            return moved

        # Update env-side status if running against mock env shape
        for d in getattr(env, "drones", []):
            did = d.get("drone_id")
            if did in low_ids:
                d["operational_status"] = "returning_to_base"
                moved.append(did)
        return moved
