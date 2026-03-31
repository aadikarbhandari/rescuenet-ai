# state/fleet_state.py

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import math

@dataclass
class DroneState:
    drone_id: str
    battery_percent: float          # 0-100
    mechanical_health: str          # "ok" | "degraded" | "critical"
    sensor_status: dict             # {"rgb": "ok", "thermal": "ok", "lidar": "degraded"}
    payload_kg: float               # Current payload weight
    winch_status: str               # "ready" | "deployed" | "fault"
    position: tuple                 # (lat, lon, alt) or SLAM coords
    wind_speed_ms: float            # From onboard environmental sensor
    temperature_c: float
    visibility_m: float
    current_mission: Optional[str] = None     # Current task ID or None

@dataclass
class VictimState:
    victim_id: str
    position: tuple                 # (lat, lon, alt) or SLAM coords
    injury_severity: str            # "minor" | "moderate" | "severe" | "critical"
    detected_by: str                # drone_id that detected this victim
    assigned_drone: Optional[str] = None
    mission_id: Optional[str] = None

@dataclass
class MissionAssignment:
    mission_id: str
    drone_id: str
    victim_id: Optional[str] = None
    task_type: str = "scan"         # "scan", "deliver", "extract", "assist"
    estimated_duration_min: float = 0.0
    status: str = "pending"         # "pending", "active", "completed", "failed"

class FleetState:
    def __init__(self):
        self.drones: Dict[str, DroneState] = {}
        self.victims: Dict[str, VictimState] = {}
        self.assignments: Dict[str, MissionAssignment] = {}  # mission_id -> assignment
        self._mission_counter = 0

    def add_or_update_drone(self, drone_state: DroneState) -> None:
        """Insert or update a drone's state."""
        self.drones[drone_state.drone_id] = drone_state

    def add_or_update_victim(self, victim_state: VictimState) -> None:
        # If victim already exists, preserve assignment-related fields
        existing = self.victims.get(victim_state.id)
        if existing is not None:
            # Keep assignment state from existing victim
            victim_state.assigned_drone = existing.assigned_drone
            victim_state.mission_id = existing.mission_id
            victim_state.status = existing.status
        # Update the victim entry
        self.victims[victim_state.id] = victim_state
        """Insert or update a victim's state."""
        self.victims[victim_state.victim_id] = victim_state

    def can_perform_mission(self, drone_id: str, task_type: str, estimated_duration_min: float) -> Tuple[bool, str]:
        """
        Returns (True, "") if drone can take the mission.
        Returns (False, reason) if it cannot.
        Used by all agents before assigning any task.
        """
        if drone_id not in self.drones:
            return False, f"Drone {drone_id} not in fleet."

        drone = self.drones[drone_id]

        # Battery check
        required_battery = 0.0
        if task_type == "scan":
            required_battery = 5.0
        elif task_type == "deliver":
            required_battery = 15.0
        elif task_type == "extract":
            required_battery = 30.0
        elif task_type == "assist":
            required_battery = 10.0
        else:
            required_battery = 20.0

        # Adjust for duration (simple linear model)
        required_battery += estimated_duration_min * 0.5

        if drone.battery_percent < required_battery:
            return False, f"Insufficient battery ({drone.battery_percent:.1f}% < {required_battery:.1f}% required)."

        # Mechanical health
        if drone.mechanical_health == "critical":
            return False, "Mechanical health critical."
        if drone.mechanical_health == "degraded" and task_type in ["extract", "deliver"]:
            return False, "Mechanical health degraded for heavy-lift task."

        # Sensor check for perception tasks
        if task_type == "scan":
            if not all(status == "ok" for status in drone.sensor_status.values() if status in ["rgb", "thermal", "lidar"]):
                return False, "Essential sensors not fully operational for scanning."

        # Payload capacity for delivery/extraction
        if task_type in ["deliver", "extract"]:
            if drone.payload_kg > 2.0:  # arbitrary threshold
                return False, f"Payload capacity exceeded ({drone.payload_kg} kg)."

        # Winch status for extraction
        if task_type == "extract" and drone.winch_status != "ready":
            return False, f"Winch not ready (status: {drone.winch_status})."

        # Environmental limits
        if drone.wind_speed_ms > 15.0:
            return False, f"Wind speed too high ({drone.wind_speed_ms} m/s)."
        if drone.visibility_m < 50.0:
            return False, f"Visibility too low ({drone.visibility_m} m)."

        # Already on a mission?
        if drone.current_mission is not None:
            # Allow if the mission is nearly done? For simplicity, reject.
            return False, f"Drone already assigned to mission {drone.current_mission}."

        return True, ""

    def get_best_drone_for(self, task_type: str, location: tuple) -> Optional[str]:
        """
        Returns drone_id of the best available drone for a given task and location.
        Considers battery, proximity, payload, and current load.
        """
        if not self.drones:
            return None

        best_score = -float('inf')
        best_drone_id = None

        target_x, target_y, _ = location  # assume (x, y, z)

        for drone_id, drone in self.drones.items():
            # Skip if already on a mission
            if drone.current_mission is not None:
                continue

            # Quick eligibility
            can, reason = self.can_perform_mission(drone_id, task_type, estimated_duration_min=10.0)
            if not can:
                continue

            # Proximity score (closer is better)
            dx = drone.position[0] - target_x
            dy = drone.position[1] - target_y
            distance = math.sqrt(dx*dx + dy*dy)
            proximity_score = 100.0 / (1.0 + distance)  # max 100 when distance=0

            # Battery score (higher battery better)
            battery_score = drone.battery_percent

            # Health bonus
            health_bonus = 0.0
            if drone.mechanical_health == "ok":
                health_bonus = 20.0
            elif drone.mechanical_health == "degraded":
                health_bonus = 5.0

            # Payload suitability
            payload_score = 0.0
            if task_type in ["deliver", "extract"]:
                # lighter payload is better for these tasks
                payload_score = max(0.0, 10.0 - drone.payload_kg)

            total_score = proximity_score * 0.4 + battery_score * 0.3 + health_bonus + payload_score

            if total_score > best_score:
                best_score = total_score
                best_drone_id = drone_id

        return best_drone_id

    def available_drones(self) -> List[str]:
        """Return list of drone IDs that are not currently on a mission."""
        return [drone_id for drone_id, drone in self.drones.items() if drone.current_mission is None]

    def create_assignment(self, drone_id: str, victim_id: Optional[str], task_type: str, estimated_duration_min: float) -> Optional[str]:
        """Create a new mission assignment and update drone's current_mission."""
        if drone_id not in self.drones:
            return None

        drone = self.drones[drone_id]
        if drone.current_mission is not None:
            return None  # already assigned

        self._mission_counter += 1
        mission_id = f"mission_{self._mission_counter:04d}"

        assignment = MissionAssignment(
            mission_id=mission_id,
            drone_id=drone_id,
            victim_id=victim_id,
            task_type=task_type,
            estimated_duration_min=estimated_duration_min,
            status="pending"
        )
        self.assignments[mission_id] = assignment
        drone.current_mission = mission_id

        if victim_id and victim_id in self.victims:
            self.victims[victim_id].assigned_drone = drone_id
            self.victims[victim_id].mission_id = mission_id

        return mission_id

    def complete_assignment(self, mission_id: str) -> bool:
        """Mark an assignment as completed and free up the drone."""
        if mission_id not in self.assignments:
            return False

        assignment = self.assignments[mission_id]
        assignment.status = "completed"

        drone_id = assignment.drone_id
        if drone_id in self.drones:
            self.drones[drone_id].current_mission = None

        victim_id = assignment.victim_id
        if victim_id and victim_id in self.victims:
            self.victims[victim_id].assigned_drone = None
            self.victims[victim_id].mission_id = None

        return True
