"""
Supervisor agent - oversees full graph
"""
from typing import List, Optional, Dict, Any
import json
import logging

# Try to import LLM libraries, but make them optional
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from state.fleet_state import FleetState, VictimState, MissionAssignment

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoordinatorAgent:
    def __init__(self, fleet_state: FleetState, use_llm_replanning: bool = False, llm_api_key: str = None):
        self.fleet = fleet_state
        self.assigned_drones = set()  # drone IDs already assigned in this planning cycle
        self.use_llm_replanning = use_llm_replanning
        if use_llm_replanning and not OPENAI_AVAILABLE:
            logger.warning("LLM replanning requested but openai not available, falling back to default logic")
            self.use_llm_replanning = False
        if use_llm_replanning and llm_api_key:
            openai.api_key = llm_api_key

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

    def replan_missions(self, fleet_state: dict, victims: list) -> list:
        """
        Use LLM to decide which drone should go to which victim.
        Returns list of assignments [{drone_id, victim_id, priority}].
        Falls back to existing logic if LLM fails.
        """
        if not self.use_llm_replanning:
            return self._fallback_replan(fleet_state, victims)
        
        try:
            # Format fleet state and victims for LLM
            prompt = self._build_replan_prompt(fleet_state, victims)
            
            # Call LLM
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a rescue coordination AI. Assign drones to victims based on severity, distance, and drone capabilities. Respond only with valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # Parse response
            assignments = self._parse_llm_response(response.choices[0].message.content)
            logger.info(f"[Coordinator] LLM replanning returned {len(assignments)} assignments")
            return assignments
            
        except Exception as e:
            logger.error(f"LLM replanning failed: {e}, falling back to default logic")
            return self._fallback_replan(fleet_state, victims)
    
    def _build_replan_prompt(self, fleet_state: dict, victims: list) -> str:
        """Build a detailed prompt for the LLM with current state information."""
        # Format drone information
        drones_info = []
        for drone_id, drone in fleet_state.get('drones', {}).items():
            drones_info.append({
                'id': drone_id,
                'position': list(drone.position) if hasattr(drone, 'position') else list(drone.get('position', [0, 0, 0])),
                'battery_percent': drone.battery_percent if hasattr(drone, 'battery_percent') else drone.get('battery_percent', 0),
                'status': 'busy' if drone.current_mission is not None else 'available',
                'winch_status': getattr(drone, 'winch_status', 'unknown'),
                'payload_kg': getattr(drone, 'payload_kg', 0),
                'sensor_status': getattr(drone, 'sensor_status', {}),
                'mechanical_health': getattr(drone, 'mechanical_health', 'unknown'),
                'wind_speed_ms': getattr(drone, 'wind_speed_ms', 0),
                'visibility_m': getattr(drone, 'visibility_m', 1000)
            })
        
        # Format victim information
        victims_info = []
        for victim in victims:
            victims_info.append({
                'id': victim.victim_id if hasattr(victim, 'victim_id') else victim.get('victim_id'),
                'position': list(victim.position) if hasattr(victim, 'position') else list(victim.get('position', [0, 0, 0])),
                'severity': victim.injury_severity if hasattr(victim, 'injury_severity') else victim.get('injury_severity', 'moderate'),
                'is_confirmed': victim.is_confirmed if hasattr(victim, 'is_confirmed') else victim.get('is_confirmed', False)
            })
        
        prompt = f"""Current fleet state (drones):
{json.dumps(drones_info, indent=2)}

Victims to assign:
{json.dumps(victims_info, indent=2)}

Based on the above information, assign each victim to the most appropriate available drone.
Consider:
1. Victim severity (critical > severe > moderate > minor)
2. Drone proximity to victim
3. Drone battery level (higher is better)
4. Drone capabilities matching victim needs (winch for extract, payload for deliver, sensors for scan, mechanical health for assist)
5. Environmental conditions (wind speed, visibility)

Return ONLY a JSON array of assignments with this exact format:
[{{"drone_id": "drone_1", "victim_id": "victim_1", "priority": 1}}, ...]

Rules:
- Only assign drones that are available (status: 'available')
- Do not assign the same drone to multiple victims
- Prioritize critical and severe victims
- Consider drone capabilities: extract needs winch, deliver needs payload capacity, scan needs sensors, assist needs mechanical health
"""
        return prompt
    
    def _parse_llm_response(self, response: str) -> list:
        """Parse the LLM response into assignments list."""
        try:
            # Extract JSON from response
            start = response.find('[')
            end = response.rfind(']') + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON array found in response")
            
            json_str = response[start:end]
            assignments = json.loads(json_str)
            
            # Validate assignments
            valid_assignments = []
            for assignment in assignments:
                if all(k in assignment for k in ['drone_id', 'victim_id', 'priority']):
                    valid_assignments.append(assignment)
            
            return valid_assignments
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise
    
    def _fallback_replan(self, fleet_state: dict, victims: list) -> list:
        """
        Fallback to existing heuristic-based assignment logic.
        Returns list of assignments in the same format as LLM would produce.
        """
        # Convert dict victims back to VictimState objects if needed
        victim_states = []
        for v in victims:
            if isinstance(v, dict):
                # Create a simple object with required attributes
                class DictVictim:
                    def __init__(self, d):
                        self.victim_id = d.get('victim_id')
                        self.position = tuple(d.get('position', [0, 0, 0]))
                        self.injury_severity = d.get('injury_severity', 'moderate')
                        self.is_confirmed = d.get('is_confirmed', False)
                        self.assigned_drone = None
                        self.mission_id = None
                        self.detection_confidence = d.get('detection_confidence', 1.0)
                        self.cooldown_until_tick = d.get('cooldown_until_tick', 0)
                        self.is_detected = d.get('is_detected', True)
                victim_states.append(DictVictim(v))
            else:
                victim_states.append(v)
        
        # Use existing prioritization logic
        prioritized = self.prioritize_victims(victim_states)
        
        # Build assignments list similar to LLM format
        assignments = []
        for idx, victim in enumerate(prioritized):
            # Find best drone using existing logic
            task_type = self._task_for_severity(victim.injury_severity)
            best_drone_id = self.fleet.get_best_drone_for(task_type, victim.position, victim.injury_severity)
            
            if best_drone_id and best_drone_id not in self.assigned_drones:
                assignments.append({
                    'drone_id': best_drone_id,
                    'victim_id': victim.victim_id,
                    'priority': idx + 1
                })
                self.assigned_drones.add(best_drone_id)
        
        return assignments

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
            if v.detection_confidence < 0.65:
                print(f"[Coordinator] Victim {v.victim_id} not confirmed (confidence: {v.detection_confidence:.2f}) - skipping")
                continue
            
            assignable.append(v)
        
        print(f"[Coordinator] {len(assignable)} assignable victims out of {len(victims)} total "
              f"(detected: {sum(1 for v in victims if v.is_detected)}, "
              f"confirmed: {sum(1 for v in victims if v.is_confirmed)}).")

        # Try LLM-powered replanning if enabled
        llm_assignments = []
        if self.use_llm_replanning:
            try:
                # Convert fleet to dict format for LLM
                fleet_dict = {
                    'drones': self.fleet.drones,
                    'assignments': self.fleet.assignments
                }
                llm_assignments = self.replan_missions(fleet_dict, assignable)
                print(f"[Coordinator] LLM replanning produced {len(llm_assignments)} candidate assignments")
            except Exception as e:
                print(f"[Coordinator] LLM replanning failed: {e}, using fallback")

        # Prioritize
        prioritized = self.prioritize_victims(assignable)
        print(f"[Coordinator] Priority order: {[v.victim_id for v in prioritized]}")

        # Collect drones that are already busy with active missions (from fleet.assignments)
        busy_drones = set()
        for mission_id, assign in self.fleet.assignments.items():
            if getattr(assign, 'status', 'pending') != 'completed':
                busy_drones.add(assign.drone_id)

        # Process LLM assignments first if available
        if llm_assignments:
            for llm_assign in llm_assignments:
                drone_id = llm_assign.get('drone_id')
                victim_id = llm_assign.get('victim_id')
                
                # Find the victim object
                victim = None
                for v in assignable:
                    if v.victim_id == victim_id:
                        victim = v
                        break
                
                if victim is None:
                    print(f"[Coordinator] LLM assigned victim {victim_id} not found in assignable list")
                    continue
                
                # Check drone validity
                if drone_id not in self.fleet.drones:
                    print(f"[Coordinator] LLM assigned drone {drone_id} not found in fleet")
                    continue
                
                if drone_id in busy_drones or drone_id in self.assigned_drones:
                    print(f"[Coordinator] LLM assigned drone {drone_id} is busy or already assigned")
                    continue
                
                # Verify capability
                task_type = self._task_for_severity(victim.injury_severity)
                can, reason = self.fleet.can_perform_mission(
                    drone_id, task_type, estimated_duration_min=15.0, victim_location=victim.position
                )
                if not can:
                    print(f"[Coordinator] LLM assigned drone {drone_id} cannot perform {task_type}: {reason}")
                    continue
                
                # Create mission assignment
                mission_id = self.fleet.create_assignment(
                    drone_id=drone_id,
                    victim_id=victim.victim_id,
                    task_type=task_type,
                    estimated_duration_min=15.0,
                    current_tick=current_tick
                )
                if mission_id is None:
                    print(f"[Coordinator] Failed to create assignment for {victim.victim_id} from LLM.")
                    continue

                self.assigned_drones.add(drone_id)
                busy_drones.add(drone_id)
                assignment = self.fleet.assignments[mission_id]
                assignments.append(assignment)
                print(f"[Coordinator] LLM-assigned drone {drone_id} to victim {victim.victim_id} (mission {mission_id})")

        # Process remaining victims using existing heuristic logic
        for victim in prioritized:
            # Skip if already assigned by LLM
            if victim.victim_id in [la.get('victim_id') for la in llm_assignments]:
                continue
            
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