"""
This agent chooses the best drone for the task.
It uses the FleetState

Supervisor agent - oversees full graph
The coordinator agent integrates the perception, triage, and routing agents to manage the overall rescue operation. 
It processes incoming data from the perception agent, prioritizes victims using the triage agent, and assigns drones to rescue tasks based on the fleet state and routing logic.

"""

class Coordinator:
    def __init__(self, perception, triage, routing):
        self.perception = perception
        self.triage = triage
        self.routing = routing


    def process_frame(self, image):
        victims = self.perception.detect_victims(image)
        return victims
    

    def get_best_victim(self, victims):
        best_victim = None
        best_score = -float("inf")

        for victim in victims:
            score = self.triage.score(victim)
            if score > best_score:
                best_score = score
                best_victim = victim
        return best_victim
    

    def assign_drone(self, victim, fleet_state):
        best_drone = fleet_state.get_best_drone_for(task_type="rescue", location=victim["location"])
        if best_drone is not None:
            fleet_state.update_fleet_state()
            self.routing.assign_task(best_drone, victim["location"])


    def get_best_drone_for_victim(self, victim, fleet_state):
        best_drone = fleet_state.get_best_drone_for(task_type="rescue", location=victim["location"])
        return best_drone
    
    