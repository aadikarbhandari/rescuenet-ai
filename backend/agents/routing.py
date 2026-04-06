"""
Navigation + jamming fallback

This agent moves drones to targets.
"""

class RoutingAgent:
    def __init__(self, client):
        self.client = client
        

    def plan_route(self, drone_pos, target):
        return [drone_pos, target]
    
    def assign_task(self, drone_id, target):
        print(f"Assigning drone {drone_id} to target {target}")

    def fallback_route(self, drone_id, target):
        print(f"Jamming detected for drone {drone_id}. Assigning fallback route to target {target}")
        self.client.moveToPositionAsync(target[0], target[1], target[2], velocity=5, vehicle_name=drone_id)