"""_summary_
This class store and update information for each drone in the fleet.
It acts as a centralized knowledge base used by agents (Coordinator, Triage, Routing) to make informed decisions about task feasibility and drone assignment.


Returns:
    _type_: _description_
"""

from http import client

from state.drone_state import DroneState, DRONE_SPAWN
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

class FleetState:
    def __init__(self):
        self.drones: Dict[str, DroneState] = {}

    # Registers a drone in the fleet:
    def add_drone(self, drone: DroneState):
        self.drones[drone.drone_id] = drone


    def remove_drone(self, drone_id: str):
        if drone_id in self.drones:
            del self.drones[drone_id]

    # Updates the state of a drone based on new telemetry data:
    def update_drone_state(self, drone_id: str, **kwargs):
        if drone_id not in self.drones:
            return

        drone = self.drones[drone_id]

        for key, value in kwargs.items():
            if hasattr(drone, key):
                setattr(drone, key, value)


    def get_drone(self, drone_id: str) -> Optional[DroneState]:
        return self.drones.get(drone_id)


    def get_all_drones(self):
        return list(self.drones.values())
    
    def get_all_drones_dict(self, client):
        drones = []

        for drone in self.get_all_drones():
            spawn_x, spawn_y, spawn_z = DRONE_SPAWN.get(drone.drone_id, (0,0,0))
            state = client.getMultirotorState(vehicle_name=drone.drone_id)
            position = [
                spawn_x + state.kinematics_estimated.position.x_val,
                spawn_y + state.kinematics_estimated.position.y_val,
                spawn_z + state.kinematics_estimated.position.z_val
            ] 
            drones.append({
                "drone_id": drone.drone_id,
                "battery_percent": drone.battery_percent,
                "mechanical_health": drone.mechanical_health,
                "position": position,
                "payload_kg": drone.payload_kg,
                "wind_speed_ms": drone.wind_speed_ms,
                "temperature_c": drone.temperature_c,
                "visibility_m": drone.visibility_m,
                "current_mission": drone.current_mission
            })
        
        return drones


    # Helper function to check if a drone can perform a specific task based on its current state:
    def can_perform_mission(self, drone_id: str, task_type: str, estimated_duration_min: float) -> Tuple[bool, str]:
        drone = self.drones.get(drone_id)

        if drone is None:
            return False, "Drone not found"

        if drone.battery_percent < 20:
            return False, "Battery too low"

        if drone.mechanical_health == "critical":
            return False, "Mechanical health critical"

        if drone.mechanical_health == "degraded":
            return False, "Mechanical health degraded"

        if drone.sensor_status:
            for sensor, status in drone.sensor_status.items():
                if status == "fault":
                    return False, f"{sensor} sensor fault"

        if drone.current_mission is not None:
            return False, "Drone already assigned to a mission"

        return True, ""


    # Helper function to select the best drone for a given task based on proximity, battery level, and health status:
    def get_best_drone_for(self, task_type: str, location: Tuple[float, float, float]) -> Optional[str]:
        best_drone_id = None
        best_score = float("inf")

        for drone in self.drones.values():
            if drone.current_mission is not None:
                continue

            if drone.battery_percent < 25:
                continue

            if drone.mechanical_health != "ok":
                continue

            dx = drone.position[0] - location[0]
            dy = drone.position[1] - location[1]
            dz = drone.position[2] - location[2]
            distance = (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5

            battery_penalty = (100 - drone.battery_percent) * 0.5

            score = distance + battery_penalty

            if score < best_score:
                best_score = score
                best_drone_id = drone.drone_id

        return best_drone_id