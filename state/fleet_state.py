import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("rescuenet.fleet_state")


class DroneStatus(Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class MissionStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DroneState:
    id: str
    status: DroneStatus = DroneStatus.AVAILABLE
    battery: float = 100.0
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    current_mission_id: Optional[str] = None
    last_update: float = 0.0


@dataclass
class VictimState:
    id: str
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    severity: int = 50
    triage_score: float = 50.0
    status: str = "discovered"
    assigned_drone_id: Optional[str] = None
    assigned_mission_id: Optional[str] = None


@dataclass
class MissionAssignment:
    id: str
    drone_id: str
    victim_id: str
    waypoints: List[Tuple[float, float, float]] = field(default_factory=list)
    status: MissionStatus = MissionStatus.PENDING
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class FleetState:
    def __init__(self, drone_names: List[str] = None):
        self.logger = logging.getLogger("rescuenet.fleet_state")
        self.drones: Dict[str, DroneState] = {}
        self.victims: Dict[str, VictimState] = {}
        self.missions: Dict[str, MissionAssignment] = {}
        
        if drone_names:
            for name in drone_names:
                self.drones[name] = DroneState(id=name)
        
        self.logger.info(f"FleetState initialized with {len(self.drones)} drones")

    def get_available_drones(self) -> List[DroneState]:
        """Return list of drones that are available for assignment."""
        available = []
        for drone in self.drones.values():
            if drone.status == DroneStatus.AVAILABLE and drone.battery > 20.0:
                available.append(drone)
        return available

    def update_from_telemetry(self, telemetry: Dict[str, Any]) -> None:
        """Update drone state from AirSim telemetry."""
        if not isinstance(telemetry, dict):
            self.logger.debug("No valid telemetry data to update")
            return
        
        current_time = telemetry.get('timestamp', 0)
        
        for drone_id, data in telemetry.items():
            if drone_id == 'timestamp':
                continue
                
            if drone_id not in self.drones:
                self.drones[drone_id] = DroneState(id=drone_id)
            
            drone = self.drones[drone_id]
            
            # Update position
            if 'position' in data:
                drone.position = tuple(data['position'])
            
            # Update velocity
            if 'velocity' in data:
                drone.velocity = tuple(data['velocity'])
            
            # Update battery
            if 'battery' in data:
                drone.battery = float(data['battery'])
            
            # Update status
            if 'status' in data:
                try:
                    drone.status = DroneStatus(data['status'])
                except ValueError:
                    self.logger.warning(f"Invalid status {data['status']} for {drone_id}, keeping current")
            
            drone.last_update = current_time

    def add_mission(self, mission: MissionAssignment) -> None:
        """Add a new mission assignment."""
        self.missions[mission.id] = mission
        
        # Update drone status
        if mission.drone_id in self.drones:
            self.drones[mission.drone_id].status = DroneStatus.BUSY
            self.drones[mission.drone_id].current_mission_id = mission.id

    def update_mission_status(self, mission_id: str, status: MissionStatus) -> None:
        """Update mission status and free drone on completion."""
        if mission_id in self.missions:
            mission = self.missions[mission_id]
            mission.status = status
            
            if status in [MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED]:
                # Free the drone
                if mission.drone_id in self.drones:
                    self.drones[mission.drone_id].status = DroneStatus.AVAILABLE
                    self.drones[mission.drone_id].current_mission_id = None

    def update_victim(self, victim_state) -> None:
        """Update victim state from simulation or detection."""
        # Handle both dict and VictimState inputs
        if isinstance(victim_state, dict):
            victim_id = victim_state.get('id') or victim_state.get('victim_id')
            if not victim_id:
                self.logger.warning("Victim dict missing 'id' field, skipping")
                return
            # Convert dict to VictimState
            vs = VictimState(
                id=victim_id,
                position=tuple(victim_state.get('position', (0.0, 0.0, 0.0))),
                severity=victim_state.get('severity', 50),
                triage_score=victim_state.get('triage_score', 50.0),
                status=victim_state.get('status', 'discovered'),
                assigned_drone_id=victim_state.get('assigned_drone_id'),
                assigned_mission_id=victim_state.get('assigned_mission_id')
            )
        else:
            # Assume it's a VictimState object
            victim_id = victim_state.id
            vs = victim_state
        
        self.victims[victim_id] = vs

    def get_victims(self) -> List[VictimState]:
        """Return all victims."""
        return list(self.victims.values())

    def get_unassigned_victims(self) -> List[VictimState]:
        """Return victims not currently assigned to a drone."""
        unassigned = []
        for victim in self.victims.values():
            if not victim.assigned_drone_id:
                unassigned.append(victim)
        return unassigned

    def to_dict(self) -> Dict[str, Any]:
        """Serialize fleet state for API responses."""
        return {
            "drones": {
                did: {
                    "id": d.id,
                    "status": d.status.value,
                    "battery": d.battery,
                    "position": list(d.position),
                    "velocity": list(d.velocity),
                    "current_mission_id": d.current_mission_id,
                    "last_update": d.last_update
                }
                for did, d in self.drones.items()
            },
            "victims": {
                vid: {
                    "id": v.id,
                    "position": list(v.position),
                    "severity": v.severity,
                    "triage_score": v.triage_score,
                    "status": v.status,
                    "assigned_drone_id": v.assigned_drone_id,
                    "assigned_mission_id": v.assigned_mission_id
                }
                for vid, v in self.victims.items()
            },
            "missions": {
                mid: {
                    "id": m.id,
                    "drone_id": m.drone_id,
                    "victim_id": m.victim_id,
                    "status": m.status.value,
                    "created_at": m.created_at,
                    "started_at": m.started_at,
                    "completed_at": m.completed_at
                }
                for mid, m in self.missions.items()
            }
        }
