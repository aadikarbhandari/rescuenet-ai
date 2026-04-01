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

        # Filter victims for assignment
        # Only assign missions to confirmed victims (high confidence detection)
        # Also filter out victims already assigned or in cooldown period
        assignable = []
        for v in victims:
            # Skip if already assigned
            if v.assigned_drone is not None or v.mission_id is not None:
                continue
            
            # Skip if in cooldown period
            if current_tick < v.cooldown_until_tick:
                print(f"[Coordinator] Victim {v.victim_id} in cooldown until tick {v.cooldown_until_tick} (current: {current_tick}) - skipping")
                continue
            
            # Only assign missions to confirmed victims (high confidence)
            if not v.is_confirmed:
                print(f"[Coordinator] Victim {v.victim_id} not confirmed (confidence: {v.detection_confidence:.2f}) - skipping")
                continue
            
            assignable.append(v)
        
        print(f"[Coordinator] {len(assignable)} assignable victims out of {len(victims)} total "
              f"(detected: {sum(1 for v in victims if v.is_detected)}, "
              f"confirmed: {sum(1 for v in victims if v.is_confirmed)}).")

        # Prioritize
        prioritized = self.prioritize_victims(assignable)
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
            best_drone_id = self.fleet.get_best_drone_for(task_type, victim.position, victim.injury_severity)
            if best_drone_id is None:
                print(f"[Coordinator] No suitable drone for victim {victim.victim_id}. Skipping.")
                continue
            # Check if drone is already busy with an active mission
            if best_drone_id in busy_drones:
                print(f"[Coordinator] Drone {best_drone_id} is already busy with an active mission. Looking for alternative...")
                alt_drone = self._find_alternative_drone(task_type, victim.position, victim.injury_severity)
                if alt_drone is None:
                    print(f"[Coordinator] No alternative drone for {victim.victim_id}. Skipping.")
                    continue
                best_drone_id = alt_drone
            # Also ensure drone not already assigned in this planning cycle
            if best_drone_id in self.assigned_drones:
                print(f"[Coordinator] Drone {best_drone_id} already assigned this cycle. Looking for alternative...")
                alt_drone = self._find_alternative_drone(task_type, victim.position, victim.injury_severity)
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
                best_drone_id, task_type, estimated_duration_min=15.0, victim_location=victim.position
            )
            if not can:
                print(f"[Coordinator] Drone {best_drone_id} cannot perform {task_type}: {reason}")
                continue

            # Create mission assignment
            mission_id = self.fleet.create_assignment(
                drone_id=best_drone_id,
                victim_id=victim.victim_id,
                task_type=task_type,
                estimated_duration_min=15.0,
                current_tick=current_tick
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

    def _find_alternative_drone(self, task_type: str, location: tuple, victim_severity: str = "moderate") -> Optional[str]:
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
            can, _ = self.fleet.can_perform_mission(drone_id, task_type, estimated_duration_min=15.0, victim_location=location)
            if not can:
                continue
            
            # Use same scoring as get_best_drone_for for consistency
            # Calculate distance
            dx = drone.position[0] - target_x
            dy = drone.position[1] - target_y
            distance = (dx*dx + dy*dy) ** 0.5
            
            # VICTIM PRIORITY FACTOR
            severity_weights = {"critical": 2.0, "severe": 1.5, "moderate": 1.2, "minor": 1.0}
            priority_factor = severity_weights.get(victim_severity, 1.0)
            
            # DISTANCE/TRAVEL EFFORT
            if distance <= 100.0:
                distance_score = 100.0 - distance
            else:
                distance_score = max(0.0, 100.0 - (distance - 100.0) * 0.5)
            
            # BATTERY SUFFICIENCY (simplified version)
            battery_margin = drone.battery_percent - 25.0  # Simplified margin check
            if battery_margin > 30.0:
                battery_score = 100.0
            elif battery_margin > 15.0:
                battery_score = 80.0
            elif battery_margin > 5.0:
                battery_score = 60.0
            elif battery_margin > 0.0:
                battery_score = 40.0
            else:
                battery_score = 0.0
            
            # DRONE CAPABILITY/SPECIALIZATION (simplified)
            capability_score = 0.0
            if task_type == "extract":
                if drone.winch_status == "ready":
                    capability_score += 40.0
                elif drone.winch_status == "degraded":
                    capability_score += 20.0
                payload_capacity = max(0.0, 5.0 - drone.payload_kg)
                capability_score += payload_capacity * 4.0
            elif task_type == "deliver":
                payload_capacity = max(0.0, 5.0 - drone.payload_kg)
                capability_score += payload_capacity * 4.0
            elif task_type == "scan":
                sensor_score = 0.0
                for sensor, status in drone.sensor_status.items():
                    if status == "ok":
                        sensor_score += 10.0
                    elif status == "degraded":
                        sensor_score += 5.0
                capability_score += sensor_score / 3.0
            elif task_type == "assist":
                if drone.mechanical_health == "ok":
                    capability_score += 30.0
                elif drone.mechanical_health == "degraded":
                    capability_score += 10.0
            
            # OPERATIONAL RELIABILITY
            reliability_score = 0.0
            if drone.mechanical_health == "ok":
                reliability_score = 30.0
            elif drone.mechanical_health == "degraded":
                reliability_score = 10.0
            
            # ENVIRONMENTAL ADAPTABILITY
            env_score = 0.0
            if drone.wind_speed_ms < 5.0:
                env_score += 15.0
            elif drone.wind_speed_ms < 10.0:
                env_score += 10.0
            elif drone.wind_speed_ms < 15.0:
                env_score += 5.0
            if drone.visibility_m > 500.0:
                env_score += 10.0
            elif drone.visibility_m > 100.0:
                env_score += 5.0
            
            # WEIGHTS (simplified version)
            if victim_severity == "critical":
                weights = {"distance": 0.2, "battery": 0.3, "capability": 0.3, "reliability": 0.2, "environment": 0.1}
            else:
                weights = {"distance": 0.4, "battery": 0.3, "capability": 0.2, "reliability": 0.1, "environment": 0.1}
            
            # Apply priority factor to weights
            for key in weights:
                weights[key] *= priority_factor
            
            total_score = (
                distance_score * weights["distance"] +
                battery_score * weights["battery"] +
                capability_score * weights["capability"] +
                reliability_score * weights["reliability"] +
                env_score * weights["environment"]
            )
            
            if total_score > best_score:
                best_score = total_score
                best_id = drone_id
        return best_id
