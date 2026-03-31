"""
CRITICAL - live fleet state + decision helpers
"""
from typing import Dict, List, Tuple, Any, Optional
from state.fleet_state import FleetState, DroneState

class StateAwarenessAgent:
    def __init__(self, fleet_state: FleetState):
        self.fleet = fleet_state

    def ingest_raw_drone_data(self, raw_data: List[Dict[str, Any]]) -> None:
        """
        Accept raw simulated drone data and update FleetState.
        Expected raw_data format:
        [
            {
                "drone_id": "drone_1",
                "battery_percent": 85.0,
                "mechanical_health": "ok",
                "sensor_status": {"rgb": "ok", "thermal": "ok", "lidar": "degraded"},
                "payload_kg": 1.2,
                "winch_status": "ready",
                "position": (10.5, 20.3, 5.0),
                "wind_speed_ms": 3.2,
                "temperature_c": 22.0,
                "visibility_m": 1000.0,
                "current_mission": None
            },
            ...
        ]
        """
        for entry in raw_data:
            drone_id = entry["drone_id"]
            # Create or update DroneState
            drone_state = DroneState(
                drone_id=drone_id,
                battery_percent=entry["battery_percent"],
                mechanical_health=entry["mechanical_health"],
                sensor_status=entry["sensor_status"],
                payload_kg=entry["payload_kg"],
                winch_status=entry["winch_status"],
                position=entry["position"],
                wind_speed_ms=entry["wind_speed_ms"],
                temperature_c=entry["temperature_c"],
                visibility_m=entry["visibility_m"],
                current_mission=entry.get("current_mission")
            )
            self.fleet.add_or_update_drone(drone_state)

    def mark_availability(self) -> Dict[str, bool]:
        """
        Mark drones as available (True) or unavailable (False) for missions.
        Returns dict mapping drone_id -> availability.
        """
        availability = {}
        for drone_id, drone in self.fleet.drones.items():
            # A drone is unavailable if:
            # 1. Already on a mission
            # 2. Battery too low (<10%)
            # 3. Mechanical health critical
            # 4. Essential sensors not ok for basic flight
            unavailable = (
                drone.current_mission is not None or
                drone.battery_percent < 10.0 or
                drone.mechanical_health == "critical" or
                not self._essential_sensors_ok(drone.sensor_status)
            )
            availability[drone_id] = not unavailable
        return availability

    def _essential_sensors_ok(self, sensor_status: Dict[str, str]) -> bool:
        """Check if essential sensors for basic flight are operational."""
        essential = {"rgb", "lidar"}  # minimal set for navigation
        for sensor in essential:
            if sensor_status.get(sensor) != "ok":
                return False
        return True

    def compute_fleet_readiness_summary(self) -> Dict[str, Any]:
        """
        Compute a simple fleet readiness summary.
        """
        total = len(self.fleet.drones)
        if total == 0:
            return {
                "total_drones": 0,
                "available_drones": 0,
                "avg_battery": 0.0,
                "operational_percent": 0.0,
                "unavailable_reasons": {}
            }

        availability = self.mark_availability()
        available_count = sum(1 for avail in availability.values() if avail)
        avg_battery = sum(d.battery_percent for d in self.fleet.drones.values()) / total

        # Collect reasons for unavailable drones
        unavailable_reasons = {}
        for drone_id, drone in self.fleet.drones.items():
            if not availability.get(drone_id, True):
                reasons = []
                if drone.current_mission is not None:
                    reasons.append("on_mission")
                if drone.battery_percent < 10.0:
                    reasons.append("low_battery")
                if drone.mechanical_health == "critical":
                    reasons.append("critical_health")
                if not self._essential_sensors_ok(drone.sensor_status):
                    reasons.append("sensor_fault")
                unavailable_reasons[drone_id] = reasons

        return {
            "total_drones": total,
            "available_drones": available_count,
            "avg_battery": round(avg_battery, 1),
            "operational_percent": round((available_count / total) * 100, 1),
            "unavailable_reasons": unavailable_reasons
        }

    def get_observations_for_coordinator(self) -> Dict[str, Any]:
        """
        Return structured observations for the coordinator.
        """
        readiness = self.compute_fleet_readiness_summary()
        availability = self.mark_availability()

        # List of available drone IDs with their positions and battery
        available_drones = []
        for drone_id, avail in availability.items():
            if avail:
                drone = self.fleet.drones[drone_id]
                available_drones.append({
                    "drone_id": drone_id,
                    "position": drone.position,
                    "battery_percent": drone.battery_percent,
                    "payload_kg": drone.payload_kg,
                    "winch_status": drone.winch_status
                })

        # List of drones currently on missions
        on_mission = []
        for drone_id, drone in self.fleet.drones.items():
            if drone.current_mission is not None:
                on_mission.append({
                    "drone_id": drone_id,
                    "mission_id": drone.current_mission,
                    "position": drone.position,
                    "battery_percent": drone.battery_percent
                })

        return {
            "fleet_readiness": readiness,
            "available_drones": available_drones,
            "drones_on_mission": on_mission,
            "timestamp": "sim_cycle"  # placeholder
        }
