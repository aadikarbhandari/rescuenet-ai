"""
Deterministic mock disaster environment.

Implements the Environment abstraction interface for demo mode.
"""
import random
from typing import Dict, List, Tuple, Any
from .environment import Environment

class MockDisasterEnv(Environment):
    # Mode configurations
    MODES = {
        "rescue": {
            "description": "Civilian rescue mode - victims need immediate assistance",
            "target_type": "victim",
            "max_targets": 4,
            "spawn_probability": 0.3,
        },
        "patrol": {
            "description": "Infrastructure patrol mode - checkpoints to inspect",
            "target_type": "checkpoint",
            "max_targets": 3,
            "spawn_probability": 0.2,
        }
    }

    def __init__(self, seed: int = 42, initial_mode: str = "rescue", num_drones: int = 3, num_victims: int = 4):
        self.rng = random.Random(seed)
        self._tick = 0
        self.num_drones = max(1, int(num_drones))
        self.num_victims = max(1, int(num_victims))
        self._current_mode = initial_mode if initial_mode in self.MODES else "rescue"
        self._init_drones()
        self._init_targets()  # Initializes victims or checkpoints based on mode
        self._init_weather()
        # Track active missions: mission_id -> {"start_tick": int, "duration_ticks": int, "drone_id": str, "victim_id": str}
        self.active_missions = {}
        # Track missions that completed in the last step
        self.recently_completed_missions = []
    
    @property
    def tick(self) -> int:
        """Current simulation tick counter."""
        return self._tick

    def _init_drones(self):
        """Create N drones with deterministic initial states."""
        self.drones = []
        for i in range(self.num_drones):
            sensor_quality = ["ok", "degraded", "ok"][i % 3]
            self.drones.append({
                "drone_id": f"drone_{i+1}",
                "battery_percent": max(45.0, 98.0 - i * 3.0),
                "mechanical_health": "degraded" if i % 7 == 3 else "ok",
                "sensor_status": {"rgb": "ok", "thermal": sensor_quality, "lidar": "ok" if i % 5 else "degraded"},
                "payload_kg": round((i % 4) * 0.6, 1),
                "winch_status": "fault" if i % 11 == 7 else "ready",
                "position": (10.0 + i * 8.0, 20.0 + ((i * 13) % 70), 5.0 + (i % 4)),
                "wind_speed_ms": 2.5 + (i % 4) * 0.4,
                "temperature_c": 22.0 + (i % 3) * 0.3,
                "visibility_m": 1200.0 - (i % 5) * 80.0,
                "current_mission": None,
                "operational_status": "idle"
            })

    def _init_targets(self):
        """Initialize targets (victims or checkpoints) based on current mode."""
        if self._current_mode == "rescue":
            self._init_victims()
        elif self._current_mode == "patrol":
            self._init_checkpoints()

    def _init_victims(self):
        """Create configurable victims with deterministic initial conditions."""
        severity_cycle = ["critical", "severe", "moderate", "minor"]
        bleeding_cycle = {"critical": "severe", "severe": "moderate", "moderate": "mild", "minor": "none"}
        self.victims = []
        for i in range(self.num_victims):
            severity = severity_cycle[i % len(severity_cycle)]
            self.victims.append({
                "victim_id": f"victim_{i+1}",
                "is_confirmed": False,
                "position": (15.0 + (i * 11) % 90, 8.0 + (i * 17) % 90, 0.0),
                "injury_severity": severity,
                "detected_by": "none",
                "first_detected_tick": 0,
                "detection_confidence": 0.0,
                "assigned_drone": None,
                "mission_id": None,
                "cooldown_until_tick": 0,
                "conscious": severity not in ("critical",),
                "bleeding": bleeding_cycle[severity],
                "body_temperature_c": 34.5 if severity == "critical" else (38.0 if severity == "severe" else 36.9),
                "accessibility": max(0.2, 0.95 - (i % 7) * 0.1)
            })
        # Alias for consistent access
        self.targets = self.victims

    def _init_checkpoints(self):
        """Create infrastructure checkpoints for patrol mode."""
        self.checkpoints = [
            {
                "checkpoint_id": "checkpoint_1",
                "position": (15.0, 25.0, 0.0),
                "status": "uninspected",
                "detected_by": "none",
                "first_detected_tick": 0,
                "detection_confidence": 0.0,
                "assigned_drone": None,
                "mission_id": None,
                "cooldown_until_tick": 0,
                "damage_level": "none",
                "accessibility": 0.9,
                "inspection_type": "visual",
                "priority": "high"
            },
            {
                "checkpoint_id": "checkpoint_2",
                "position": (35.0, 45.0, 0.0),
                "status": "uninspected",
                "detected_by": "none",
                "first_detected_tick": 0,
                "detection_confidence": 0.0,
                "assigned_drone": None,
                "mission_id": None,
                "cooldown_until_tick": 0,
                "damage_level": "minor",
                "accessibility": 0.8,
                "inspection_type": "thermal",
                "priority": "medium"
            },
            {
                "checkpoint_id": "checkpoint_3",
                "position": (55.0, 15.0, 0.0),
                "status": "uninspected",
                "detected_by": "none",
                "first_detected_tick": 0,
                "detection_confidence": 0.0,
                "assigned_drone": None,
                "mission_id": None,
                "cooldown_until_tick": 0,
                "damage_level": "moderate",
                "accessibility": 0.6,
                "inspection_type": "lidar",
                "priority": "high"
            }
        ]
        # Alias for consistent access
        self.targets = self.checkpoints

    def _init_weather(self):
        """Initialize weather parameters."""
        self.visibility = 1000.0
        self.wind_speed = 3.0
        self.temperature = 22.0

    def get_current_mode(self) -> str:
        """Return the current operational mode."""
        return self._current_mode

    def switch_mode(self, mode: str):
        """
        Switch the environment to a different operational mode.
        
        Args:
            mode: The mode to switch to ('rescue' or 'patrol')
        
        Raises:
            ValueError: If the mode is not recognized
        """
        if mode not in self.MODES:
            raise ValueError(f"Unknown mode: {mode}. Available modes: {list(self.MODES.keys())}")
        
        if mode == self._current_mode:
            return  # Already in this mode
        
        old_mode = self._current_mode
        self._current_mode = mode
        
        # Clear any active missions when switching modes
        self.active_missions.clear()
        self.recently_completed_missions.clear()
        
        # Reset drone missions
        for d in self.drones:
            d["current_mission"] = None
            if d["operational_status"] not in ["charging", "unavailable_fault", "idle"]:
                d["operational_status"] = "idle"
        
        # Reinitialize targets based on new mode
        self._init_targets()
        
        print(f"[MockEnv] Switched mode from '{old_mode}' to '{mode}'")
        print(f"[MockEnv] Mode description: {self.MODES[mode]['description']}")

    def get_drone_snapshots(self) -> List[Dict[str, Any]]:
        """Return current drone states as a list of dicts."""
        # Apply deterministic drift based on tick
        snapshots = []
        for d in self.drones:
            # copy to avoid mutating internal state
            snap = d.copy()
            # Remove the additional battery drain here since it's already handled in step()
            # snap["battery_percent"] = max(0.0, snap["battery_percent"] - self._tick * 0.05)
            # update environmental readings from current weather
            snap["wind_speed_ms"] = self.wind_speed + self.rng.uniform(-0.5, 0.5)
            snap["temperature_c"] = self.temperature + self.rng.uniform(-1.0, 1.0)
            snap["visibility_m"] = self.visibility + self.rng.uniform(-50.0, 50.0)
            # Add fields expected by security agent
            pos = snap.get("position", (0.0, 0.0, 0.0))
            snap["latitude"] = 47.641468 + pos[0] * 0.00001
            snap["longitude"] = -122.140165 + pos[1] * 0.00001
            snap["altitude"] = pos[2]
            snap["timestamp"] = self._tick
            snap["signal_strength"] = 85 if snap.get("operational_status") != "unavailable_fault" else 10
            snap["battery_level"] = snap.get("battery_percent", 0.0)
            # Add fields expected by fleet_state
            snap["id"] = snap.get("drone_id")
            snap["battery"] = snap.get("battery_percent", 0.0)
            snap["status"] = snap.get("operational_status", "idle")
            snapshots.append(snap)
        return snapshots

    def get_victim_snapshots(self) -> List[Dict[str, Any]]:
        """Return current target states as a list of dicts (victims or checkpoints based on mode)."""
        snapshots = []
        for target in self.targets:
            snap = target.copy()
            
            if self._current_mode == "rescue":
                # Victim-specific updates
                # deterministic condition changes over ticks
                # body temperature drifts slightly
                drift = self.rng.uniform(-0.1, 0.1)
                snap["body_temperature_c"] += drift
                # accessibility may improve if not already 1.0
                if snap["accessibility"] < 1.0:
                    snap["accessibility"] += self.rng.uniform(0.0, 0.02)
                # bleeding may worsen for severe cases
                if snap["bleeding"] == "severe" and self._tick % 10 == 0:
                    snap["bleeding"] = "severe"  # stays severe
                elif snap["bleeding"] == "moderate" and self._tick % 15 == 0:
                    snap["bleeding"] = "severe"
                # consciousness may change for critical victims
                if snap["injury_severity"] == "critical" and self._tick % 20 == 0:
                    snap["conscious"] = False
            elif self._current_mode == "patrol":
                # Checkpoint-specific updates
                # Damage level may worsen over time
                if snap["damage_level"] == "none" and self._tick % 50 == 0:
                    snap["damage_level"] = "minor"
                elif snap["damage_level"] == "minor" and self._tick % 40 == 0:
                    snap["damage_level"] = "moderate"
                elif snap["damage_level"] == "moderate" and self._tick % 30 == 0:
                    snap["damage_level"] = "severe"
                # Accessibility may change
                if snap["accessibility"] < 1.0:
                    snap["accessibility"] += self.rng.uniform(0.0, 0.01)
            
            snapshots.append(snap)
        return snapshots

    def step(self):
        """
        Advance simulation by one tick.
        Updates weather and internal state.
        """
        self._tick += 1

        # Weather changes deterministically
        # visibility follows a sine‑like pattern
        self.visibility = 800.0 + 200.0 * (1.0 + self.rng.uniform(-0.2, 0.2)) * (
            abs((self._tick % 60) - 30) / 30.0
        )
        # wind speed increases gradually then drops
        self.wind_speed = 2.0 + 0.1 * (self._tick % 40)
        # temperature has a daily cycle
        self.temperature = 20.0 + 5.0 * (1.0 + self.rng.uniform(-0.1, 0.1)) * (
            abs((self._tick % 120) - 60) / 60.0
        )

        # Realistic target discovery: drones must be close and have appropriate sensors
        # Simulates sensor-based detection with confidence levels
        for d in self.drones:
            for target in self.targets:
                # Calculate 2D distance (ignore altitude for simplicity)
                dx = d["position"][0] - target["position"][0]
                dy = d["position"][1] - target["position"][1]
                distance = (dx*dx + dy*dy) ** 0.5
                
                target_id = target.get("victim_id") or target.get("checkpoint_id")
                detected_by_key = "detected_by"
                
                if target[detected_by_key] == "none":
                    # Base detection probability based on distance
                    base_prob = max(0.0, 1.0 - (distance / 30.0))  # 100% at 0m, 0% at 30m+
                    
                    # Sensor bonuses
                    sensor_bonus = 0.0
                    if d["sensor_status"].get("thermal") == "ok":
                        sensor_bonus += 0.3  # Thermal helps detect body heat
                    if d["sensor_status"].get("rgb") == "ok":
                        sensor_bonus += 0.2  # RGB helps with visual identification
                    if d["sensor_status"].get("lidar") == "ok":
                        sensor_bonus += 0.1  # Lidar helps with shape detection
                    
                    # Environmental factors
                    visibility_factor = min(1.0, self.visibility / 500.0)  # Better visibility helps
                    detection_prob = base_prob * (1.0 + sensor_bonus) * visibility_factor
                    
                    # Random chance based on probability
                    if self.rng.random() < detection_prob:
                        target[detected_by_key] = d["drone_id"]
                        target["first_detected_tick"] = self._tick
                        # Initial confidence based on sensors and distance
                        target["detection_confidence"] = min(1.0, 0.3 + sensor_bonus * 0.5 + (1.0 - distance/30.0) * 0.3)
                        target["is_confirmed"] = target["detection_confidence"] >= 0.65
                        
                        if self._current_mode == "rescue":
                            print(f"[MockEnv] Victim {target_id} discovered by drone {d['drone_id']} "
                                  f"(distance: {distance:.1f}m, confidence: {target['detection_confidence']:.2f})")
                        else:
                            print(f"[MockEnv] Checkpoint {target_id} discovered by drone {d['drone_id']} "
                                  f"(distance: {distance:.1f}m, confidence: {target['detection_confidence']:.2f})")
                
                # Increase confidence for already detected targets if drone is closer
                elif target[detected_by_key] == d["drone_id"] and distance < 10.0:
                    # Re-observation increases confidence
                    confidence_boost = min(0.2, (10.0 - distance) / 50.0)
                    target["detection_confidence"] = min(1.0, target["detection_confidence"] + confidence_boost)
                    target["is_confirmed"] = target["detection_confidence"] >= 0.65

        # Track missions to complete (so we can update targets after drone loop)
        missions_to_complete = []
        
        # Base station position (where drones return to charge)
        base_station = (0.0, 0.0, 0.0)
        
        # Drone operational logic - realistic state machine
        for d in self.drones:
            current_status = d["operational_status"]
            
            # Check for low battery condition - triggers return-to-base from any state
            if d["battery_percent"] < 20.0 and current_status not in ["returning_to_base", "charging"]:
                d["operational_status"] = "returning_to_base"
                d["current_mission"] = None  # Abort any current mission
                print(f"[MockEnv] Drone {d['drone_id']} battery low ({d['battery_percent']:.1f}%), returning to base")
                current_status = "returning_to_base"  # Update for rest of logic
            
            # Check for hardware faults - triggers unavailable_fault
            if d["mechanical_health"] == "critical" and current_status != "unavailable_fault":
                d["operational_status"] = "unavailable_fault"
                d["current_mission"] = None  # Abort any current mission
                print(f"[MockEnv] Drone {d['drone_id']} mechanical health critical, marked as unavailable_fault")
                current_status = "unavailable_fault"
            
            # Handle different operational states
            if current_status == "idle":
                # Idle drone at base station
                d["position"] = base_station  # Ensure idle drones are at base
                
                # Check if battery is low (but not low enough to trigger auto-return)
                if d["battery_percent"] < 30.0:
                    # Battery getting low, should charge but not critical yet
                    # In real system, this would trigger charging, but for demo we keep idle
                    pass
                
                # Normal battery drain for idle drones (very low when at base)
                idle_drain = 0.1  # Increased from 0.02 for more realistic demo
                d["battery_percent"] = max(0.0, d["battery_percent"] - idle_drain)
            
            elif current_status == "assigned":
                # Drone has been assigned a mission but hasn't started moving yet
                # In this simplified model, transition to en_route immediately
                d["operational_status"] = "en_route"
                print(f"[MockEnv] Drone {d['drone_id']} starting mission {d['current_mission']}, en route")
                current_status = "en_route"  # Update for rest of logic
            
            elif current_status == "en_route":
                # Drone is traveling to target location
                # Find target position for this mission
                target_pos = None
                mission_id = d["current_mission"]
                for target in self.targets:
                    if target["mission_id"] == mission_id:
                        target_pos = target["position"]
                        break
                
                if target_pos:
                    # Move toward target (simplified movement)
                    dx = target_pos[0] - d["position"][0]
                    dy = target_pos[1] - d["position"][1]
                    distance = (dx*dx + dy*dy) ** 0.5
                    
                    if distance < 2.0:  # Close enough to target
                        d["operational_status"] = "on_scene"
                        d["position"] = target_pos  # Snap to exact position
                        print(f"[MockEnv] Drone {d['drone_id']} reached target, now on scene")
                    else:
                        # Move toward target
                        move_speed = 5.0
                        if distance > 0:
                            d["position"] = (
                                d["position"][0] + (dx / distance) * move_speed,
                                d["position"][1] + (dy / distance) * move_speed,
                                d["position"][2]
                            )
                
                # Battery drain while en route (higher due to movement)
                en_route_drain = 1.2  # Increased from 0.12 for more realistic demo
                d["battery_percent"] = max(0.0, d["battery_percent"] - en_route_drain)
            
            elif current_status == "on_scene":
                # Drone is at target location, performing task
                mission_id = d["current_mission"]
                
                # Track mission progress
                if mission_id not in self.active_missions:
                    # Start tracking this mission
                    target_id = None
                    for target in self.targets:
                        if target["mission_id"] == mission_id:
                            target_id = target.get("victim_id") or target.get("checkpoint_id")
                            break
                    
                    self.active_missions[mission_id] = {
                        "start_tick": self._tick,
                        "duration_ticks": 3,  # Missions complete after 3 ticks
                        "drone_id": d["drone_id"],
                        "target_id": target_id
                    }
                else:
                    # Check if mission is complete
                    mission = self.active_missions[mission_id]
                    elapsed = self._tick - mission["start_tick"]
                    if elapsed >= mission["duration_ticks"]:
                        # Mission complete - drone should return to base
                        d["current_mission"] = None
                        d["operational_status"] = "returning_to_base"
                        # Record for target update
                        missions_to_complete.append(mission_id)
                        print(f"[MockEnv] Mission {mission_id} completed by drone {d['drone_id']}, returning to base")
                
                # Battery drain while on scene (high due to payload operations)
                on_scene_drain = 1.5  # Increased from 0.15 for more realistic demo
                d["battery_percent"] = max(0.0, d["battery_percent"] - on_scene_drain)
            
            elif current_status == "returning_to_base":
                # Drone is returning to base station
                # Move toward base station (simplified movement)
                dx = base_station[0] - d["position"][0]
                dy = base_station[1] - d["position"][1]
                distance = (dx*dx + dy*dy) ** 0.5
                
                if distance < 5.0:  # Close enough to base
                    d["operational_status"] = "charging"
                    d["position"] = base_station
                    print(f"[MockEnv] Drone {d['drone_id']} reached base station, now charging")
                else:
                    # Move toward base (simplified)
                    move_speed = 5.0
                    if distance > 0:
                        d["position"] = (
                            d["position"][0] + (dx / distance) * move_speed,
                            d["position"][1] + (dy / distance) * move_speed,
                            d["position"][2]
                        )
                
                # Battery drain while returning (similar to en_route)
                return_drain = 1.0  # Increased from 0.1 for more realistic demo
                d["battery_percent"] = max(0.0, d["battery_percent"] - return_drain)
            
            elif current_status == "charging":
                # Charging at base station - battery increases
                charge_rate = 2.0  # 2% per tick when charging
                d["battery_percent"] = min(100.0, d["battery_percent"] + charge_rate)
                
                # When battery reaches sufficient level, become idle
                if d["battery_percent"] >= 80.0:
                    d["operational_status"] = "idle"
                    print(f"[MockEnv] Drone {d['drone_id']} fully charged ({d['battery_percent']:.1f}%), now idle")
            
            elif current_status == "unavailable_fault":
                # Recover after 3 ticks
                if "fault_since" not in d:
                    d["fault_since"] = self._tick
                elif d.get('fault_since') is not None and self._tick - d['fault_since'] >= 3:
                    d["operational_status"] = "idle"
                    d["fault_since"] = None
                    print(f"[MockEnv] Drone {d['drone_id']} recovered from fault, now idle")
            
            # Base battery drain (applies to all operational states except charging and unavailable_fault)
            if current_status not in ["charging", "unavailable_fault"]:
                base_drain = 0.1 + (0.05 * d["payload_kg"])  # Increased for more realistic demo
                d["battery_percent"] = max(0.0, d["battery_percent"] - base_drain)
            
            # Low battery logic - trigger return to base if battery is critically low
            if d["battery_percent"] < 20.0 and current_status not in ["returning_to_base", "charging", "unavailable_fault"]:
                if current_status in ["assigned", "en_route", "on_scene"]:
                    d["operational_status"] = "returning_to_base"
                    print(f"[MockEnv] Drone {d['drone_id']} battery critically low ({d['battery_percent']:.1f}%), returning to base")
                    # If drone was on a mission, mark it for completion
                    if d["current_mission"]:
                        missions_to_complete.append(d["current_mission"])
            
            # mechanical health may degrade after many ticks (independent of battery)
            if d["mechanical_health"] == "ok" and self._tick % 50 == 0:
                d["mechanical_health"] = "degraded"
                print(f"[MockEnv] Drone {d['drone_id']} mechanical health degraded")
            elif d["mechanical_health"] == "degraded" and self._tick % 30 == 0:
                d["mechanical_health"] = "critical"
                print(f"[MockEnv] Drone {d['drone_id']} mechanical health critical")
            
            # sensor status may fluctuate
            if self._tick % 25 == 0:
                for sensor in d["sensor_status"]:
                    if d["sensor_status"][sensor] == "ok":
                        d["sensor_status"][sensor] = "degraded"
                    elif d["sensor_status"][sensor] == "degraded":
                        d["sensor_status"][sensor] = "ok"
            
            # Random fault generation (1% chance per tick when not already in fault)
            if current_status != "unavailable_fault" and self.rng.random() < 0.01:
                d["operational_status"] = "unavailable_fault"
                print(f"[MockEnv] Drone {d['drone_id']} developed a system fault, status: unavailable_fault")
                # If drone was on a mission, mark it for completion/abortion
                if d["current_mission"]:
                    missions_to_complete.append(d["current_mission"])
        
        # Update targets for completed missions
        for mission_id in missions_to_complete:
            mission = self.active_missions.get(mission_id)
            if mission and mission.get("target_id"):
                # Find and update the target
                for target in self.targets:
                    target_id = target.get("victim_id") or target.get("checkpoint_id")
                    if target_id == mission["target_id"]:
                        target["assigned_drone"] = None
                        target["mission_id"] = None
                        # Set cooldown to prevent immediate reassignment (2 ticks cooldown)
                        target["cooldown_until_tick"] = self._tick + 2
                        
                        if self._current_mode == "rescue":
                            print(f"[MockEnv] Victim {target_id} freed from completed mission {mission_id}, cooldown until tick {target['cooldown_until_tick']}")
                        else:
                            print(f"[MockEnv] Checkpoint {target_id} freed from completed mission {mission_id}, cooldown until tick {target['cooldown_until_tick']}")
            # Remove from active missions tracking and add to recently completed
            if mission_id in self.active_missions:
                del self.active_missions[mission_id]
                self.recently_completed_missions.append(mission_id)

        # Target condition updates
        for target in self.targets:
            if self._current_mode == "rescue":
                # Victim condition updates
                # injury severity may worsen for critical/severe
                if target["injury_severity"] in ("critical", "severe") and self._tick % 40 == 0:
                    if target["injury_severity"] == "severe":
                        target["injury_severity"] = "critical"
                # body temperature drifts toward normal slowly
                diff = 37.0 - target["body_temperature_c"]
                target["body_temperature_c"] += diff * 0.01
                # accessibility slowly improves
                if target["accessibility"] < 1.0:
                    target["accessibility"] = min(1.0, target["accessibility"] + 0.005)
            elif self._current_mode == "patrol":
                # Checkpoint condition updates
                # Status may change to inspected after some time if not already
                if target["status"] == "uninspected" and self._tick % 30 == 0:
                    target["status"] = "inspected"
                # Accessibility may improve
                if target["accessibility"] < 1.0:
                    target["accessibility"] = min(1.0, target["accessibility"] + 0.003)

    def update_victim_assignment(self, victim_id: str, drone_id: str, mission_id: str):
        """Update victim assignment in the environment."""
        for target in self.targets:
            target_id = target.get("victim_id") or target.get("checkpoint_id")
            if target_id == victim_id:
                target["assigned_drone"] = drone_id
                target["mission_id"] = mission_id
                print(f"[MockEnv] Target {target_id} assigned to drone {drone_id} (mission {mission_id})")
                break
    
    def update_drone_mission(self, drone_id: str, mission_id: str):
        """Update drone mission assignment in the environment."""
        for d in self.drones:
            if d["drone_id"] == drone_id:
                d["current_mission"] = mission_id
                d["operational_status"] = "assigned"
                print(f"[MockEnv] Drone {drone_id} assigned to mission {mission_id}, status: assigned")
                break
    
    def get_completed_missions(self) -> List[str]:
        """Return list of mission IDs that completed in the last step and clear the list."""
        completed = self.recently_completed_missions.copy()
        self.recently_completed_missions.clear()
        return completed

    def get_simulation_state(self) -> Dict[str, Any]:
        """Return a summary of the current simulation state."""
        return {
            "tick": self._tick,
            "mode": self._current_mode,
            "weather": {
                "visibility_m": self.visibility,
                "wind_speed_ms": self.wind_speed,
                "temperature_c": self.temperature,
            },
            "num_drones": len(self.drones),
            "num_targets": len(self.targets),
        }

    def get_all_telemetry(self):
        """Return lightweight telemetry for all drones in demo mode."""
        telemetry = []
        for d in self.drones:
            telemetry.append({
                "drone_id": d.get("drone_id"),
                "position": d.get("position", [0, 0, 0]),
                "battery_percent": d.get("battery_percent", 100.0),
                "operational_status": d.get("operational_status", "unknown"),
                "mechanical_health": d.get("mechanical_health", "ok"),
                "wind_speed_ms": d.get("wind_speed_ms", 0.0),
                "temperature_c": d.get("temperature_c", 20.0),
                "visibility_m": d.get("visibility_m", 1000.0),
                "current_mission": d.get("current_mission"),
                # Fields expected by security agent
                "latitude": 47.641468 + d.get("position", (0,0,0))[0] * 0.00001,
                "longitude": -122.140165 + d.get("position", (0,0,0))[1] * 0.00001,
                "altitude": d.get("position", (0,0,0))[2],
                "timestamp": self._tick,
                "signal_strength": 85 if d.get("operational_status") != "unavailable_fault" else 10,
                "battery_level": d.get("battery_percent", 0.0),
            })
        return telemetry
