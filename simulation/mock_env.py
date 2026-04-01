"""
Deterministic mock disaster environment.

Implements the Environment abstraction interface for demo mode.
"""
import random
from typing import Dict, List, Tuple, Any
from .environment import Environment

class MockDisasterEnv(Environment):
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self._tick = 0
        self._init_drones()
        self._init_victims()
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
        """Create 3 drones with deterministic initial states."""
        self.drones = [
            {
                "drone_id": "drone_1",
                "battery_percent": 95.0,
                "mechanical_health": "ok",
                "sensor_status": {"rgb": "ok", "thermal": "ok", "lidar": "ok"},
                "payload_kg": 0.0,
                "winch_status": "ready",
                "position": (10.0, 20.0, 5.0),
                "wind_speed_ms": 2.5,
                "temperature_c": 22.0,
                "visibility_m": 1000.0,
                "current_mission": None,
                "operational_status": "idle"
            },
            {
                "drone_id": "drone_2",
                "battery_percent": 80.0,
                "mechanical_health": "degraded",
                "sensor_status": {"rgb": "ok", "thermal": "degraded", "lidar": "ok"},
                "payload_kg": 1.5,
                "winch_status": "ready",
                "position": (30.0, 40.0, 10.0),
                "wind_speed_ms": 3.0,
                "temperature_c": 21.5,
                "visibility_m": 800.0,
                "current_mission": None,
                "operational_status": "idle"
            },
            {
                "drone_id": "drone_3",
                "battery_percent": 60.0,
                "mechanical_health": "ok",
                "sensor_status": {"rgb": "ok", "thermal": "ok", "lidar": "degraded"},
                "payload_kg": 0.8,
                "winch_status": "fault",
                "position": (50.0, 10.0, 8.0),
                "wind_speed_ms": 4.2,
                "temperature_c": 23.0,
                "visibility_m": 1200.0,
                "current_mission": None,
                "operational_status": "idle"
            }
        ]

    def _init_victims(self):
        """Create 2‑4 victims with deterministic initial conditions."""
        self.victims = [
            {
                "victim_id": "victim_1",
                "position": (15.0, 25.0, 0.0),
                "injury_severity": "critical",
                "detected_by": "none",
                "first_detected_tick": 0,
                "detection_confidence": 0.0,
                "assigned_drone": None,
                "mission_id": None,
                "cooldown_until_tick": 0,
                "conscious": False,
                "bleeding": "severe",
                "body_temperature_c": 34.5,
                "accessibility": 0.3
            },
            {
                "victim_id": "victim_2",
                "position": (35.0, 45.0, 0.0),
                "injury_severity": "moderate",
                "detected_by": "none",
                "first_detected_tick": 0,
                "detection_confidence": 0.0,
                "assigned_drone": None,
                "mission_id": None,
                "cooldown_until_tick": 0,
                "conscious": True,
                "bleeding": "mild",
                "body_temperature_c": 36.8,
                "accessibility": 0.8
            },
            {
                "victim_id": "victim_3",
                "position": (55.0, 15.0, 0.0),
                "injury_severity": "severe",
                "detected_by": "none",
                "first_detected_tick": 0,
                "detection_confidence": 0.0,
                "assigned_drone": None,
                "mission_id": None,
                "cooldown_until_tick": 0,
                "conscious": True,
                "bleeding": "moderate",
                "body_temperature_c": 38.2,
                "accessibility": 0.5
            },
            {
                "victim_id": "victim_4",
                "position": (25.0, 5.0, 0.0),
                "injury_severity": "minor",
                "detected_by": "none",
                "first_detected_tick": 0,
                "detection_confidence": 0.0,
                "assigned_drone": None,
                "mission_id": None,
                "cooldown_until_tick": 0,
                "conscious": True,
                "bleeding": "none",
                "body_temperature_c": 37.0,
                "accessibility": 0.9
            }
        ]

    def _init_weather(self):
        """Initialize weather parameters."""
        self.visibility = 1000.0
        self.wind_speed = 3.0
        self.temperature = 22.0

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
            snapshots.append(snap)
        return snapshots

    def get_victim_snapshots(self) -> List[Dict[str, Any]]:
        """Return current victim states as a list of dicts."""
        snapshots = []
        for v in self.victims:
            snap = v.copy()
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

        # Realistic victim discovery: drones must be close and have appropriate sensors
        # Simulates sensor-based detection with confidence levels
        for d in self.drones:
            for v in self.victims:
                # Calculate 2D distance (ignore altitude for simplicity)
                dx = d["position"][0] - v["position"][0]
                dy = d["position"][1] - v["position"][1]
                distance = (dx*dx + dy*dy) ** 0.5
                
                if v["detected_by"] == "none":
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
                        v["detected_by"] = d["drone_id"]
                        v["first_detected_tick"] = self._tick
                        # Initial confidence based on sensors and distance
                        v["detection_confidence"] = min(1.0, 0.3 + sensor_bonus * 0.5 + (1.0 - distance/30.0) * 0.3)
                        print(f"[MockEnv] Victim {v['victim_id']} discovered by drone {d['drone_id']} "
                              f"(distance: {distance:.1f}m, confidence: {v['detection_confidence']:.2f})")
                
                # Increase confidence for already detected victims if drone is closer
                elif v["detected_by"] == d["drone_id"] and distance < 10.0:
                    # Re-observation increases confidence
                    confidence_boost = min(0.2, (10.0 - distance) / 50.0)
                    v["detection_confidence"] = min(1.0, v["detection_confidence"] + confidence_boost)

        # Track missions to complete (so we can update victims after drone loop)
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
                # Drone is traveling to victim location
                # Find victim position for this mission
                target_pos = None
                mission_id = d["current_mission"]
                for v in self.victims:
                    if v["mission_id"] == mission_id:
                        target_pos = v["position"]
                        break
                
                if target_pos:
                    # Move toward target (simplified movement)
                    dx = target_pos[0] - d["position"][0]
                    dy = target_pos[1] - d["position"][1]
                    distance = (dx*dx + dy*dy) ** 0.5
                    
                    if distance < 2.0:  # Close enough to victim
                        d["operational_status"] = "on_scene"
                        d["position"] = target_pos  # Snap to exact position
                        print(f"[MockEnv] Drone {d['drone_id']} reached victim, now on scene")
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
                # Drone is at victim location, performing task
                mission_id = d["current_mission"]
                
                # Track mission progress
                if mission_id not in self.active_missions:
                    # Start tracking this mission
                    victim_id = None
                    for v in self.victims:
                        if v["mission_id"] == mission_id:
                            victim_id = v["victim_id"]
                            break
                    
                    self.active_missions[mission_id] = {
                        "start_tick": self._tick,
                        "duration_ticks": 3,  # Missions complete after 3 ticks
                        "drone_id": d["drone_id"],
                        "victim_id": victim_id
                    }
                else:
                    # Check if mission is complete
                    mission = self.active_missions[mission_id]
                    elapsed = self._tick - mission["start_tick"]
                    if elapsed >= mission["duration_ticks"]:
                        # Mission complete - drone should return to base
                        d["current_mission"] = None
                        d["operational_status"] = "returning_to_base"
                        # Record for victim update
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
                # Drone has hardware/system fault and cannot operate
                # No movement or battery drain (powered off or in maintenance)
                # Position stays where it was when fault occurred
                pass
            
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
        
        # Update victims for completed missions
        for mission_id in missions_to_complete:
            mission = self.active_missions.get(mission_id)
            if mission and mission["victim_id"]:
                # Find and update the victim
                for v in self.victims:
                    if v["victim_id"] == mission["victim_id"]:
                        v["assigned_drone"] = None
                        v["mission_id"] = None
                        # Set cooldown to prevent immediate reassignment (2 ticks cooldown)
                        v["cooldown_until_tick"] = self._tick + 2
                        print(f"[MockEnv] Victim {v['victim_id']} freed from completed mission {mission_id}, cooldown until tick {v['cooldown_until_tick']}")
            # Remove from active missions tracking and add to recently completed
            if mission_id in self.active_missions:
                del self.active_missions[mission_id]
                self.recently_completed_missions.append(mission_id)

        # Victim condition updates
        for v in self.victims:
            # injury severity may worsen for critical/severe
            if v["injury_severity"] in ("critical", "severe") and self._tick % 40 == 0:
                if v["injury_severity"] == "severe":
                    v["injury_severity"] = "critical"
            # body temperature drifts toward normal slowly
            diff = 37.0 - v["body_temperature_c"]
            v["body_temperature_c"] += diff * 0.01
            # accessibility slowly improves
            if v["accessibility"] < 1.0:
                v["accessibility"] = min(1.0, v["accessibility"] + 0.005)

    def update_victim_assignment(self, victim_id: str, drone_id: str, mission_id: str):
        """Update victim assignment in the environment."""
        for v in self.victims:
            if v["victim_id"] == victim_id:
                v["assigned_drone"] = drone_id
                v["mission_id"] = mission_id
                print(f"[MockEnv] Victim {victim_id} assigned to drone {drone_id} (mission {mission_id})")
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
            "weather": {
                "visibility_m": self.visibility,
                "wind_speed_ms": self.wind_speed,
                "temperature_c": self.temperature,
            },
            "num_drones": len(self.drones),
            "num_victims": len(self.victims),
        }
