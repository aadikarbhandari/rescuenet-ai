# state/fleet_state.py

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import math

@dataclass
class DroneState:
    drone_id: str
    battery_percent: float          # 0-100
    mechanical_health: str          # "ok" | "degraded" | "critical"
    sensor_status: dict             # {"rgb": "ok", "thermal": "ok", "lidar": "degraded"}
    payload_kg: float               # Current payload weight
    winch_status: str               # "ready" | "deployed" | "fault"
    position: tuple                 # (lat, lon, alt) or SLAM coords
    wind_speed_ms: float            # From onboard environmental sensor
    temperature_c: float
    visibility_m: float
    current_mission: Optional[str] = None     # Current task ID or None
    operational_status: str = "idle"          # "idle", "assigned", "en_route", "on_scene", "returning_to_base", "charging", "unavailable_fault"
    target_position: Optional[tuple] = None   # Target location when en_route or on_scene

@dataclass
class VictimState:
    victim_id: str
    position: tuple                 # (lat, lon, alt) or SLAM coords
    injury_severity: str            # "minor" | "moderate" | "severe" | "critical"
    detected_by: str = "none"       # drone_id that first detected this victim, or "none"
    first_detected_tick: int = 0    # Tick when victim was first detected
    detection_confidence: float = 0.0  # 0.0-1.0 confidence in detection
    assigned_drone: Optional[str] = None
    mission_id: Optional[str] = None
    cooldown_until_tick: int = 0    # Tick until which victim is in cooldown after mission completion
    # Additional medical details (for triage)
    conscious: bool = True
    bleeding: str = "none"          # "none", "mild", "moderate", "severe"
    body_temperature_c: float = 37.0
    accessibility: float = 0.5      # 0.0-1.0 accessibility score
    
    @property
    def is_detected(self) -> bool:
        """Return True if victim has been detected by any drone."""
        return self.detected_by != "none"
    
    @property
    def is_confirmed(self) -> bool:
        """Return True if victim detection has high confidence."""
        return self.is_detected and self.detection_confidence >= 0.7
    
    @property
    def is_triaged(self) -> bool:
        """Return True if victim has been assigned a priority score."""
        # For now, assume detected victims are triaged
        # In future, this could track if triage agent has processed this victim
        return self.is_detected
    
    @property
    def is_assigned(self) -> bool:
        """Return True if victim has been assigned to a drone/mission."""
        return self.assigned_drone is not None or self.mission_id is not None
    
    @property
    def is_resolved(self) -> bool:
        """Return True if victim mission is completed/resolved."""
        # Currently tracks cooldown period after mission completion
        return self.cooldown_until_tick > 0

@dataclass
class MissionAssignment:
    mission_id: str
    drone_id: str
    victim_id: Optional[str] = None
    task_type: str = "scan"         # "scan", "deliver", "extract", "assist"
    estimated_duration_min: float = 0.0
    status: str = "detected"        # "detected", "triaged", "queued", "assigned", "en_route", "on_scene", "action_in_progress", "completed", "aborted", "returning"
    current_phase: str = "detected"  # Tracks current phase in mission lifecycle
    phase_start_tick: int = 0       # Tick when current phase started
    progress_percent: float = 0.0   # 0-100% progress in current phase

class FleetState:
    def __init__(self):
        self.drones: Dict[str, DroneState] = {}
        self.victims: Dict[str, VictimState] = {}
        self.assignments: Dict[str, MissionAssignment] = {}  # mission_id -> assignment
        self._mission_counter = 0

    def add_or_update_drone(self, drone_state: DroneState) -> None:
        """Insert or update a drone's state."""
        self.drones[drone_state.drone_id] = drone_state

    def add_or_update_victim(self, victim_state: VictimState) -> None:
        """
        Insert or update a victim's state with discovery-aware logic.
        
        For detected victims: preserve detection info (first detection is important)
        For undetected victims: environment provides ground truth
        For assignment state: environment is authoritative
        """
        existing = self.victims.get(victim_state.victim_id)
        
        if existing is not None:
            # Preserve detection information (first detection is important)
            if victim_state.detected_by == "none" and existing.detected_by != "none":
                # New data says not detected, but we previously detected it
                # Keep our detection info
                victim_state.detected_by = existing.detected_by
                victim_state.first_detected_tick = existing.first_detected_tick
                victim_state.detection_confidence = existing.detection_confidence
            
            # Preserve cooldown if new data has cooldown_until_tick = 0 (not set)
            if victim_state.cooldown_until_tick == 0 and existing.cooldown_until_tick > 0:
                victim_state.cooldown_until_tick = existing.cooldown_until_tick
            
            # Preserve medical details if new data has default values
            if victim_state.conscious == True and existing.conscious == False:
                victim_state.conscious = False
            if victim_state.bleeding == "none" and existing.bleeding != "none":
                victim_state.bleeding = existing.bleeding
            if victim_state.body_temperature_c == 37.0 and existing.body_temperature_c != 37.0:
                victim_state.body_temperature_c = existing.body_temperature_c
            if victim_state.accessibility == 0.5 and existing.accessibility != 0.5:
                victim_state.accessibility = existing.accessibility
            
            # Assignment state comes from new data (env ground truth)
            # Don't preserve assignment from existing - env is authoritative
        
        self.victims[victim_state.victim_id] = victim_state

    def can_perform_mission(self, drone_id: str, task_type: str, estimated_duration_min: float, victim_location: Optional[tuple] = None) -> Tuple[bool, str]:
        """
        Returns (True, "") if drone can take the mission.
        Returns (False, reason) if it cannot.
        Used by all agents before assigning any task.
        """
        if drone_id not in self.drones:
            return False, f"Drone {drone_id} not in fleet."

        drone = self.drones[drone_id]

        # Battery check - use more accurate calculation if victim location is provided
        if victim_location:
            # Calculate distance to victim
            dx = drone.position[0] - victim_location[0]
            dy = drone.position[1] - victim_location[1]
            distance = math.sqrt(dx*dx + dy*dy)
            required_battery = self._calculate_required_battery(task_type, estimated_duration_min, distance)
        else:
            # Fallback to simple calculation
            required_battery = 0.0
            if task_type == "scan":
                required_battery = 5.0
            elif task_type == "deliver":
                required_battery = 15.0
            elif task_type == "extract":
                required_battery = 30.0
            elif task_type == "assist":
                required_battery = 10.0
            else:
                required_battery = 20.0
            required_battery += estimated_duration_min * 0.5
            required_battery *= 1.1  # Add safety margin

        if drone.battery_percent < required_battery:
            return False, f"Insufficient battery ({drone.battery_percent:.1f}% < {required_battery:.1f}% required)."

        # Mechanical health
        if drone.mechanical_health == "critical":
            return False, "Mechanical health critical."
        if drone.mechanical_health == "degraded" and task_type in ["extract", "deliver"]:
            return False, "Mechanical health degraded for heavy-lift task."

        # Sensor check for perception tasks
        if task_type == "scan":
            if not all(status == "ok" for status in drone.sensor_status.values() if status in ["rgb", "thermal", "lidar"]):
                return False, "Essential sensors not fully operational for scanning."

        # Payload capacity for delivery/extraction
        if task_type in ["deliver", "extract"]:
            if drone.payload_kg > 2.0:  # arbitrary threshold
                return False, f"Payload capacity exceeded ({drone.payload_kg} kg)."

        # Winch status for extraction
        if task_type == "extract" and drone.winch_status != "ready":
            return False, f"Winch not ready (status: {drone.winch_status})."

        # Environmental limits
        if drone.wind_speed_ms > 15.0:
            return False, f"Wind speed too high ({drone.wind_speed_ms} m/s)."
        if drone.visibility_m < 50.0:
            return False, f"Visibility too low ({drone.visibility_m} m)."

        # Already on a mission or not operationally available?
        if drone.current_mission is not None:
            # Allow if the mission is nearly done? For simplicity, reject.
            return False, f"Drone already assigned to mission {drone.current_mission}."
        
        # Check operational status - only idle drones can be assigned new missions
        if drone.operational_status != "idle":
            return False, f"Drone not idle (status: {drone.operational_status})."
        
        # Low battery check - don't assign missions to drones with low battery
        if drone.battery_percent < 25.0:  # Safety margin above critical threshold
            return False, f"Battery too low for new mission ({drone.battery_percent:.1f}% < 25%)."

        return True, ""
    
    def is_drone_available(self, drone_id: str) -> bool:
        """
        Check if drone is available for display/readiness purposes.
        Different from can_perform_mission - this is for status reporting.
        """
        if drone_id not in self.drones:
            return False
        
        drone = self.drones[drone_id]
        
        # Drones are considered "available" if they're idle and not critically low on battery
        return (drone.operational_status == "idle" and 
                drone.battery_percent >= 10.0 and  # Not critically low
                drone.mechanical_health != "critical")

    def get_best_drone_for(self, task_type: str, location: tuple, victim_severity: str = "moderate") -> Optional[str]:
        """
        Returns drone_id of the best available drone for a given task and location.
        Considers victim severity, distance, battery, drone capability, and operational state.
        """
        if not self.drones:
            return None

        best_score = -float('inf')
        best_drone_id = None
        best_score_details = {}

        target_x, target_y, _ = location  # assume (x, y, z)

        for drone_id, drone in self.drones.items():
            # Skip if already on a mission or not idle (idle is the available state)
            if drone.current_mission is not None or drone.operational_status != "idle":
                continue

            # Quick eligibility - use same duration as coordinator (15.0 minutes) for consistency
            can, reason = self.can_perform_mission(drone_id, task_type, estimated_duration_min=15.0, victim_location=location)
            if not can:
                continue

            # Calculate distance and travel effort
            dx = drone.position[0] - target_x
            dy = drone.position[1] - target_y
            distance = math.sqrt(dx*dx + dy*dy)
            
            # 1. VICTIM PRIORITY FACTOR (higher for critical victims)
            severity_weights = {"critical": 2.0, "severe": 1.5, "moderate": 1.2, "minor": 1.0}
            priority_factor = severity_weights.get(victim_severity, 1.0)
            
            # 2. DISTANCE/TRAVEL EFFORT (closer is better, but critical victims can justify longer travel)
            # Normalize distance: 0-100m = 100-0 score, >100m = diminishing returns
            if distance <= 100.0:
                distance_score = 100.0 - distance  # 100 at 0m, 0 at 100m
            else:
                distance_score = max(0.0, 100.0 - (distance - 100.0) * 0.5)  # slower decay beyond 100m
            
            # 3. BATTERY SUFFICIENCY (consider margin above required)
            # Calculate required battery for this specific mission
            required_battery = self._calculate_required_battery(task_type, 15.0, distance)
            battery_margin = drone.battery_percent - required_battery
            if battery_margin > 30.0:
                battery_score = 100.0  # Plenty of margin
            elif battery_margin > 15.0:
                battery_score = 80.0   # Good margin
            elif battery_margin > 5.0:
                battery_score = 60.0   # Adequate margin
            elif battery_margin > 0.0:
                battery_score = 40.0   # Minimal margin
            else:
                battery_score = 0.0    # Should have been rejected by can_perform_mission
            
            # 4. DRONE CAPABILITY/SPECIALIZATION
            capability_score = 0.0
            if task_type == "extract":
                # Winch capability is critical for extraction
                if drone.winch_status == "ready":
                    capability_score += 40.0
                elif drone.winch_status == "degraded":
                    capability_score += 20.0
                # Payload capacity matters for extraction
                payload_capacity = max(0.0, 5.0 - drone.payload_kg)  # 5kg max capacity
                capability_score += payload_capacity * 4.0  # 0-20 points
                    
            elif task_type == "deliver":
                # Payload capacity matters for delivery
                payload_capacity = max(0.0, 5.0 - drone.payload_kg)
                capability_score += payload_capacity * 4.0  # 0-20 points
                
            elif task_type == "scan":
                # Sensor quality matters for scanning
                sensor_score = 0.0
                for sensor, status in drone.sensor_status.items():
                    if status == "ok":
                        sensor_score += 10.0
                    elif status == "degraded":
                        sensor_score += 5.0
                capability_score += sensor_score / 3.0  # Normalize to ~0-10
                
            elif task_type == "assist":
                # General purpose - health and battery matter more
                if drone.mechanical_health == "ok":
                    capability_score += 30.0
                elif drone.mechanical_health == "degraded":
                    capability_score += 10.0
            
            # 5. OPERATIONAL RELIABILITY
            reliability_score = 0.0
            if drone.mechanical_health == "ok":
                reliability_score = 30.0
            elif drone.mechanical_health == "degraded":
                reliability_score = 10.0
            # Critical health would have been rejected by can_perform_mission
            
            # 6. ENVIRONMENTAL ADAPTABILITY
            env_score = 0.0
            # Wind tolerance
            if drone.wind_speed_ms < 5.0:
                env_score += 15.0
            elif drone.wind_speed_ms < 10.0:
                env_score += 10.0
            elif drone.wind_speed_ms < 15.0:
                env_score += 5.0
            # Visibility tolerance
            if drone.visibility_m > 500.0:
                env_score += 10.0
            elif drone.visibility_m > 100.0:
                env_score += 5.0
            
            # 7. LOAD BALANCING (simple version - prefer drones that haven't been used recently)
            # This would require tracking mission history, but for now we'll use battery as proxy
            # Drones with higher battery have done less work recently
            
            # COMBINE SCORES WITH WEIGHTS
            # Weights adjust based on victim priority
            if victim_severity == "critical":
                # For critical victims: capability and reliability matter most
                weights = {
                    "distance": 0.2 * priority_factor,
                    "battery": 0.3 * priority_factor,
                    "capability": 0.3 * priority_factor,
                    "reliability": 0.2 * priority_factor,
                    "environment": 0.1 * priority_factor
                }
            else:
                # For non-critical: distance and battery efficiency matter more
                weights = {
                    "distance": 0.4 * priority_factor,
                    "battery": 0.3 * priority_factor,
                    "capability": 0.2 * priority_factor,
                    "reliability": 0.1 * priority_factor,
                    "environment": 0.1 * priority_factor
                }
            
            total_score = (
                distance_score * weights["distance"] +
                battery_score * weights["battery"] +
                capability_score * weights["capability"] +
                reliability_score * weights["reliability"] +
                env_score * weights["environment"]
            )
            
            # Store score details for debugging/explanation
            score_details = {
                "distance": distance_score,
                "battery": battery_score,
                "capability": capability_score,
                "reliability": reliability_score,
                "environment": env_score,
                "weights": weights,
                "total": total_score
            }

            if total_score > best_score:
                best_score = total_score
                best_drone_id = drone_id
                best_score_details = score_details

        # Debug logging
        if best_drone_id:
            print(f"[FleetState] Best drone for {task_type} (severity: {victim_severity}): {best_drone_id} "
                  f"score={best_score:.1f} "
                  f"(dist={best_score_details.get('distance', 0):.1f}, "
                  f"batt={best_score_details.get('battery', 0):.1f}, "
                  f"cap={best_score_details.get('capability', 0):.1f}, "
                  f"rel={best_score_details.get('reliability', 0):.1f}, "
                  f"env={best_score_details.get('environment', 0):.1f})")
        
        return best_drone_id
    
    def _calculate_required_battery(self, task_type: str, duration_min: float, distance_m: float) -> float:
        """
        Calculate required battery percentage for a mission.
        Considers task type, duration, and travel distance.
        """
        # Base battery requirements by task type
        if task_type == "scan":
            base_required = 5.0
        elif task_type == "deliver":
            base_required = 15.0
        elif task_type == "extract":
            base_required = 30.0
        elif task_type == "assist":
            base_required = 10.0
        else:
            base_required = 20.0
        
        # Add duration cost (0.5% per minute)
        duration_cost = duration_min * 0.5
        
        # Add travel cost (0.1% per meter round trip)
        travel_cost = distance_m * 0.1 * 2  # Round trip
        
        # Add safety margin (10%)
        total_required = (base_required + duration_cost + travel_cost) * 1.1
        
        return total_required

    def available_drones(self) -> List[str]:
        """Return list of drone IDs that are not currently on a mission."""
        return [drone_id for drone_id, drone in self.drones.items() if drone.current_mission is None]

    def create_assignment(self, drone_id: str, victim_id: Optional[str], task_type: str, estimated_duration_min: float, current_tick: int = 0) -> Optional[str]:
        """Create a new mission assignment and update drone's current_mission."""
        if drone_id not in self.drones:
            return None

        drone = self.drones[drone_id]
        if drone.current_mission is not None:
            return None  # already assigned

        self._mission_counter += 1
        mission_id = f"mission_{self._mission_counter:04d}"

        assignment = MissionAssignment(
            mission_id=mission_id,
            drone_id=drone_id,
            victim_id=victim_id,
            task_type=task_type,
            estimated_duration_min=estimated_duration_min,
            status="assigned",  # Mission starts in assigned phase
            current_phase="assigned",
            phase_start_tick=current_tick,
            progress_percent=0.0
        )
        self.assignments[mission_id] = assignment
        drone.current_mission = mission_id
        drone.operational_status = "assigned"  # Drone is now assigned to a mission

        if victim_id and victim_id in self.victims:
            self.victims[victim_id].assigned_drone = drone_id
            self.victims[victim_id].mission_id = mission_id

        return mission_id

    def complete_assignment(self, mission_id: str, current_tick: int = 0) -> bool:
        """Mark an assignment as completed and free up the drone."""
        if mission_id not in self.assignments:
            return False

        assignment = self.assignments[mission_id]
        assignment.status = "completed"
        assignment.current_phase = "completed"
        assignment.phase_start_tick = current_tick
        assignment.progress_percent = 100.0

        drone_id = assignment.drone_id
        if drone_id in self.drones:
            self.drones[drone_id].current_mission = None

        victim_id = assignment.victim_id
        if victim_id and victim_id in self.victims:
            self.victims[victim_id].assigned_drone = None
            self.victims[victim_id].mission_id = None

        return True
    
    def update_mission_phase(self, mission_id: str, new_phase: str, progress_percent: float = 0.0, current_tick: int = 0) -> bool:
        """Update a mission's current phase and progress."""
        if mission_id not in self.assignments:
            return False
        
        assignment = self.assignments[mission_id]
        assignment.status = new_phase  # For backward compatibility, status tracks current phase
        assignment.current_phase = new_phase
        assignment.phase_start_tick = current_tick
        assignment.progress_percent = progress_percent
        
        return True
    
    def abort_assignment(self, mission_id: str, current_tick: int = 0) -> bool:
        """Mark an assignment as aborted and free up the drone."""
        if mission_id not in self.assignments:
            return False

        assignment = self.assignments[mission_id]
        assignment.status = "aborted"
        assignment.current_phase = "aborted"
        assignment.phase_start_tick = current_tick
        assignment.progress_percent = 0.0

        drone_id = assignment.drone_id
        if drone_id in self.drones:
            self.drones[drone_id].current_mission = None

        victim_id = assignment.victim_id
        if victim_id and victim_id in self.victims:
            self.victims[victim_id].assigned_drone = None
            self.victims[victim_id].mission_id = None

        return True
    
    def sync_mission_phases_from_drones(self, current_tick: int = 0) -> None:
        """
        Update mission phases based on drone operational status.
        This should be called after drone states are updated from the environment.
        """
        for drone_id, drone in self.drones.items():
            if drone.current_mission is None:
                continue
                
            mission_id = drone.current_mission
            if mission_id not in self.assignments:
                continue
                
            assignment = self.assignments[mission_id]
            current_phase = assignment.current_phase
            new_phase = None
            
            # Map drone operational status to mission phase
            if drone.operational_status == "assigned" and current_phase != "assigned":
                new_phase = "assigned"
            elif drone.operational_status == "en_route" and current_phase != "en_route":
                new_phase = "en_route"
            elif drone.operational_status == "on_scene" and current_phase != "on_scene":
                new_phase = "on_scene"
            elif drone.operational_status == "returning_to_base" and current_phase != "returning":
                new_phase = "returning"
            elif drone.operational_status == "charging" and current_phase != "completed":
                # When drone starts charging, mission is completed
                new_phase = "completed"
            elif drone.operational_status == "idle" and current_phase == "completed":
                # Drone is idle after mission completion - no phase change needed
                pass
            elif drone.operational_status == "unavailable_fault" and current_phase != "aborted":
                new_phase = "aborted"
            
            if new_phase is not None:
                self.update_mission_phase(mission_id, new_phase, current_tick=current_tick)
                print(f"[FleetState] Mission {mission_id} phase updated from '{current_phase}' to '{new_phase}' based on drone {drone_id} status '{drone.operational_status}'")
