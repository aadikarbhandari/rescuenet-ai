# state/fleet_state.py

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
    current_mission: str | None     # Current task ID or None

class FleetState:
    drones: dict[str, DroneState]

    def can_perform_mission(self, drone_id: str, task_type: str, estimated_duration_min: float) -> tuple[bool, str]:
        """
        Returns (True, "") if drone can take the mission.
        Returns (False, reason) if it cannot.
        Used by all agents before assigning any task.
        """
        ...

    def get_best_drone_for(self, task_type: str, location: tuple) -> str | None:
        """
        Returns drone_id of the best available drone for a given task and location.
        Considers battery, proximity, payload, and current load.
        """
        ...