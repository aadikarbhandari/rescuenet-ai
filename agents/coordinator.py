"""
Supervisor agent - oversees full graph
"""
from typing import List, Optional
from state.fleet_state import FleetState, VictimState, MissionAssignment

class CoordinatorAgent:
    def __init__(self, fleet_state: FleetState):
        self.fleet = fleet_state
        self.assigned_drones = set()  # drone IDs already assigned in this planning cycle

    def prioritize_victims(self, victims: List[VictimState]) -> List[VictimState]:
        """
        Sort victims by injury severity (critical > severe > moderate > minor).
        Within same severity, closer to any available drone gets higher priority.
        """
        severity_order = {"critical": 4, "severe": 3, "moderate": 2, "minor": 1}

        def victim_score(victim: VictimState) -> tuple:
            base = severity_order.get(victim.injury_severity, 0)
            # compute minimal distance to any available drone
            min_dist = float('inf')
            for drone_id, drone in self.fleet.drones.items():
                if drone.current_mission is not None:
                    continue
                dx = drone.position[0] - victim.position[0]
                dy = drone.position[1] - victim.position[1]
                dist = (dx*dx + dy*dy) ** 0.5
                if dist < min_dist:
                    min_dist = dist
            # lower distance is better, so we use negative for sorting
            return (-base, min_dist)  # higher severity first, then closer

        # Filter out victims that already have an active assignment
        unassigned = []
        for v in victims:
            if v.assigned_drone is None and v.mission_id is None:
                unassigned.append(v)
            else:
                print(f"[Coordinator] Victim {v.victim_id} already assigned (drone={v.assigned_drone}, mission={v.mission_id}) - skipping")
        sorted_victims = sorted(unassigned, key=victim_score)
        return sorted_victims

    def assign_missions(self, victims: List[VictimState], current_tick: int = 0) -> List[MissionAssignment]:
        """
        Main assignment loop.
        Returns a list of newly created MissionAssignment objects.
        """
        assignments = []
        self.assigned_drones.clear()

        # Filter out victims already assigned (assigned_drone or mission_id not None)
        # Also filter out victims in cooldown period after mission completion
        unassigned = []
        for v in victims:
            if v.assigned_drone is None and v.mission_id is None:
                # Check if victim is in cooldown period
                if current_tick < v.cooldown_until_tick:
                    print(f"[Coordinator] Victim {v.victim_id} in cooldown until tick {v.cooldown_until_tick} (current: {current_tick}) - skipping")
                    continue
                unassigned.append(v)
        print(f"[Coordinator] {len(unassigned)} unassigned victims out of {len(victims)} total.")

        # Prioritize
        prioritized = self.prioritize_victims(unassigned)
        print(f"[Coordinator] Priority order: {[v.victim_id for v in prioritized]}")

        # Collect drones that are already busy with active missions (from fleet.assignments)
        busy_drones = set()
        for mission_id, assign in self.fleet.assignments.items():
            if getattr(assign, 'status', 'pending') != 'completed':
                busy_drones.add(assign.drone_id)

        for victim in prioritized:
            # Determine task type based on injury severity
            task_type = self._task_for_severity(victim.injury_severity)
            print(f"[Coordinator] Victim {victim.victim_id} severity {victim.injury_severity} -> task {task_type}")

            # Find best available drone (not already assigned in this cycle AND not busy with active mission)
            best_drone_id = self.fleet.get_best_drone_for(task_type, victim.position)
            if best_drone_id is None:
                print(f"[Coordinator] No suitable drone for victim {victim.victim_id}. Skipping.")
                continue
            # Check if drone is already busy with an active mission
            if best_drone_id in busy_drones:
                print(f"[Coordinator] Drone {best_drone_id} is already busy with an active mission. Looking for alternative...")
                alt_drone = self._find_alternative_drone(task_type, victim.position)
                if alt_drone is None:
                    print(f"[Coordinator] No alternative drone for {victim.victim_id}. Skipping.")
                    continue
                best_drone_id = alt_drone
            # Also ensure drone not already assigned in this planning cycle
            if best_drone_id in self.assigned_drones:
                print(f"[Coordinator] Drone {best_drone_id} already assigned this cycle. Looking for alternative...")
                alt_drone = self._find_alternative_drone(task_type, victim.position)
                if alt_drone is None:
                    print(f"[Coordinator] No alternative drone for {victim.victim_id}. Skipping.")
                    continue
                best_drone_id = alt_drone
            # Double-check the drone is not busy (should be caught above)
            if best_drone_id in busy_drones:
                print(f"[Coordinator] Drone {best_drone_id} is busy (final check). Skipping victim {victim.victim_id}.")
                continue

            # Check capability via fleet's can_perform_mission
            can, reason = self.fleet.can_perform_mission(
                best_drone_id, task_type, estimated_duration_min=15.0
            )
            if not can:
                print(f"[Coordinator] Drone {best_drone_id} cannot perform {task_type}: {reason}")
                continue

            # Create mission assignment
            mission_id = self.fleet.create_assignment(
                drone_id=best_drone_id,
                victim_id=victim.victim_id,
                task_type=task_type,
                estimated_duration_min=15.0
            )
            if mission_id is None:
                print(f"[Coordinator] Failed to create assignment for {victim.victim_id}.")
                continue

            self.assigned_drones.add(best_drone_id)
            busy_drones.add(best_drone_id)   # also mark as busy for subsequent victims in this same loop
            assignment = self.fleet.assignments[mission_id]
            assignments.append(assignment)
            print(f"[Coordinator] Assigned drone {best_drone_id} to victim {victim.victim_id} (mission {mission_id})")

        print(f"[Coordinator] Total new assignments created: {len(assignments)}")
        return assignments

    def _task_for_severity(self, severity: str) -> str:
        """Map injury severity to a task type."""
        mapping = {
            "critical": "extract",
            "severe": "deliver",
            "moderate": "assist",
            "minor": "scan"
        }
        return mapping.get(severity, "scan")

    def _find_alternative_drone(self, task_type: str, location: tuple) -> Optional[str]:
        """
        Find an available drone (not in self.assigned_drones) that can perform the task.
        Also exclude drones that are already busy with an active mission (from fleet.assignments).
        Uses same scoring as get_best_drone_for for consistency.
        """
        best_score = -float('inf')
        best_id = None
        target_x, target_y, _ = location

        # Collect drones that are already busy with active missions
        busy_drones = set()
        for mission_id, assign in self.fleet.assignments.items():
            if getattr(assign, 'status', 'pending') != 'completed':
                busy_drones.add(assign.drone_id)

        for drone_id, drone in self.fleet.drones.items():
            # Skip if drone has a current_mission (drone-level busy flag)
            if drone.current_mission is not None:
                continue
            # Skip if drone is already assigned in this planning cycle
            if drone_id in self.assigned_drones:
                continue
            # Skip if drone is busy with an active mission (from fleet.assignments)
            if drone_id in busy_drones:
                continue
            can, _ = self.fleet.can_perform_mission(drone_id, task_type, estimated_duration_min=15.0)
            if not can:
                continue
            
            # Use same scoring as get_best_drone_for for consistency
            # Proximity score (closer is better)
            dx = drone.position[0] - target_x
            dy = drone.position[1] - target_y
            distance = (dx*dx + dy*dy) ** 0.5
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
                best_id = drone_id
        return best_id
