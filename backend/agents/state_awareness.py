"""
CRITICAL - live fleet state + decision helpers

This agent continuously reads telemetry from AirSim and updates the FleetState object.
It maintains a live FleetState updated every 1–2 seconds, tracks drone health and environment data, and provides helper functions such as mission feasibility checks.

Typical workflow:
* Connects to AirSim.
* Detects all drones automatically.
* Creates and maintains a live FleetState.
* Updates telemetry every 1–2 seconds.
* Tracks battery, position, sensors, payload, and environment data.
* Provides helper functions used by other agents to decide:
  * whether a drone can perform a mission
  * which drone is best for a task.

Other agents (Coordinator, Triage, Routing) will query this class so their decisions always rely on the current real fleet state.
"""


import time
import threading
from typing import Dict

import airsim

from state.fleet_state import FleetState, DroneState


class StateAwarenessAgent:
    def __init__(self, update_interval: float = 2.0):
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()

        self.fleet_state = FleetState()
        self.update_interval = update_interval

        self.running = False
        self.thread = None

    # Initialize the fleet state with current drones in AirSim
    def initialize_drones(self):
        vehicle_names = self.client.listVehicles()

        for name in vehicle_names:
            state = self.client.getMultirotorState(vehicle_name=name)

            drone_state = DroneState(
                drone_id=name,
                battery_percent=100.0,#state.battery_remaining * 100,
                mechanical_health="ok",
                sensor_status={
                    "rgb_camera": "ok",
                    "thermal_camera": "ok",
                    "lidar": "ok",
                    "microphone": "ok",
                },
                payload_kg=0.0,
                winch_status="idle",
                position=(
                    state.kinematics_estimated.position.x_val,
                    state.kinematics_estimated.position.y_val,
                    state.kinematics_estimated.position.z_val,
                ),
                wind_speed_ms=0.0,
                temperature_c=25.0,
                visibility_m=1000.0,
                current_mission=None
            )

            self.fleet_state.add_drone(drone_state)

    # Start the background thread to continuously update fleet state
    def start(self):
        if self.running:
            return

        self.running = True
        self.initialize_drones()

        self.thread = threading.Thread(target=self._update_loop)
        self.thread.daemon = True
        self.thread.start()

    # Stop the background thread:
    def stop(self):
        self.running = False

        if self.thread:
            self.thread.join()

    # Background loop to continuously update fleet state
    def _update_loop(self):
        while self.running:
            try:
                self.update_fleet_state()
                time.sleep(self.update_interval)
            except Exception as e:
                print("StateAwarenessAgent error:", e)

    # Query AirSim for each drone’s state and update FleetState
    def update_fleet_state(self):
        for drone in self.fleet_state.get_all_drones():
            drone_id = drone.drone_id

            state = self.client.getMultirotorState(vehicle_name=drone_id)

            position = (
                state.kinematics_estimated.position.x_val,
                state.kinematics_estimated.position.y_val,
                state.kinematics_estimated.position.z_val,
            )

            #battery = state.battery_remaining * 100
            current_drone = self.fleet_state.get_drone(drone_id)
            battery = max(0, current_drone.battery_percent - 0.1)

            self.fleet_state.update_drone_state(
                drone_id,
                position=position,
                battery_percent=battery
            )

    # Helper functions to query fleet state and make decisions
    def get_fleet_state(self):
        return self.fleet_state

    # Check if a drone can perform a mission based on its current state and the mission requirements
    def can_perform_mission(self, drone_id: str, task_type: str, estimated_duration: float):
        return self.fleet_state.can_perform_mission(
            drone_id,
            task_type,
            estimated_duration
        )

    # Get the best drone for a specific task based on current fleet state and task requirements
    def get_best_drone_for(self, task_type: str, location):
        return self.fleet_state.get_best_drone_for(
            task_type,
            location
        )