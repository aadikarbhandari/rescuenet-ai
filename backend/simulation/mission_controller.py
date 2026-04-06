"""_summary_
A scripted mission controller that triggers the disaster sequence and then activates the AI agents. 
It allows mode switching (Normal → Disaster) and coordinating the simulation with the AI system.
"""

import time

class MissionController:
    def __init__(self, airsim_client, state_agent, perception, coordinator, triage, voice):
        self.client = airsim_client
        self.state_agent = state_agent
        self.perception = perception
        self.coordinator = coordinator
        self.triage = triage
        self.voice = voice

        self.mode = "NORMAL"

    def start_normal_mode(self):
        print("Mission started in NORMAL mode")
        self.mode = "NORMAL"

        # drones idle monitoring
        drones = self.client.listVehicles()

        for drone in drones:
            self.client.enableApiControl(True, drone)

    def trigger_disaster(self):
        print("DISASTER TRIGGERED")
        self.mode = "DISASTER"

        # spawn smoke / debris in Unreal
        self.client.simRunConsoleCommand("ce trigger_disaster")

    def run_disaster_response(self):
        drones = self.client.listVehicles()

        print("Launching scout drones")

        for drone in drones:
            self.client.armDisarm(True, drone)
            self.client.takeoffAsync(vehicle_name=drone)

        # scanning phase
        detections = self.perception.scan_fleet(drones)

        # triage
        victims = self.triage.score_victims(detections)

        # assign drones
        assignments = self.coordinator.assign_drones(victims)

        # execute missions
        for mission in assignments:
            drone = mission["drone"]
            target = mission["victim"]

            self.client.moveToPositionAsync(
                target["x"],
                target["y"],
                -5,
                5,
                vehicle_name=drone
            )

            self.voice.speak(
                "Rescue drone here. Stay calm. Help is coming."
            )