from dataclasses import dataclass
from typing import Tuple, Optional

DRONE_SPAWN = {
    "Drone1": (0, 5000, -100),
    "Drone2": (-200, 5000, -100),
    "Drone3": (200, 5000, -100),
    "Drone4": (0, 5200, -100),
    "Drone5": (0, 4800, -100)
}

@dataclass
class DroneState:
    drone_id: str
    battery_percent: float          # 0-100
    mechanical_health: str          # "ok" | "degraded" | "critical"
    sensor_status: dict             # {"rgb": "ok", "thermal": "ok", "lidar": "degraded"}
    payload_kg: float               # Current payload weight
    winch_status: str               # "ready" | "deployed" | "fault"
    position: Tuple[float, float, float]                 # (lat, lon, alt) or SLAM coords
    wind_speed_ms: float            # From onboard environmental sensor
    temperature_c: float
    visibility_m: float
    current_mission: Optional[str]  # Current task ID or None