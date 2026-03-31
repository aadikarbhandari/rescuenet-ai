"""
Deterministic mock disaster environment.
"""
import random
from typing import Dict, List, Tuple, Any

class MockDisasterEnv:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.tick = 0
        self._init_drones()
        self._init_victims()
        self._init_weather()
        # Track active missions: mission_id -> {"start_tick": int, "duration_ticks": int, "drone_id": str, "victim_id": str}
        self.active_missions = {}
        # Track missions that completed in the last step
        self.recently_completed_missions = []

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
                "current_mission": None
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
                "current_mission": None
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
                "current_mission": None
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
            # small deterministic battery drain
            snap["battery_percent"] = max(0.0, snap["battery_percent"] - self.tick * 0.05)
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
            if snap["bleeding"] == "severe" and self.tick % 10 == 0:
                snap["bleeding"] = "severe"  # stays severe
            elif snap["bleeding"] == "moderate" and self.tick % 15 == 0:
                snap["bleeding"] = "severe"
            # consciousness may change for critical victims
            if snap["injury_severity"] == "critical" and self.tick % 20 == 0:
                snap["conscious"] = False
            snapshots.append(snap)
        return snapshots

    def step(self):
        """
        Advance simulation by one tick.
        Updates weather and internal state.
        """
        self.tick += 1

        # Weather changes deterministically
        # visibility follows a sine‑like pattern
        self.visibility = 800.0 + 200.0 * (1.0 + self.rng.uniform(-0.2, 0.2)) * (
            abs((self.tick % 60) - 30) / 30.0
        )
        # wind speed increases gradually then drops
        self.wind_speed = 2.0 + 0.1 * (self.tick % 40)
        # temperature has a daily cycle
        self.temperature = 20.0 + 5.0 * (1.0 + self.rng.uniform(-0.1, 0.1)) * (
            abs((self.tick % 120) - 60) / 60.0
        )

        # Track missions to complete (so we can update victims after drone loop)
        missions_to_complete = []
        
        # Drone battery naturally depletes (more if payload > 0)
        for d in self.drones:
            # Base battery drain
            base_drain = 0.05 + (0.02 * d["payload_kg"])
            
            # Additional drain if on a mission (varies by mission type)
            mission_drain = 0.0
            if d["current_mission"] is not None:
                # Extra battery consumption during active missions
                # Different mission types have different energy requirements
                mission_drain = 0.15  # Base additional drain for being on mission
                
                # Track mission progress
                mission_id = d["current_mission"]
                if mission_id not in self.active_missions:
                    # Start tracking this mission
                    # Try to find which victim is assigned to this mission
                    victim_id = None
                    for v in self.victims:
                        if v["mission_id"] == mission_id:
                            victim_id = v["victim_id"]
                            break
                    
                    self.active_missions[mission_id] = {
                        "start_tick": self.tick,
                        "duration_ticks": 3,  # Missions complete after 3 ticks
                        "drone_id": d["drone_id"],
                        "victim_id": victim_id
                    }
                else:
                    # Check if mission is complete
                    mission = self.active_missions[mission_id]
                    elapsed = self.tick - mission["start_tick"]
                    if elapsed >= mission["duration_ticks"]:
                        # Mission complete - free the drone
                        d["current_mission"] = None
                        # Record for victim update
                        missions_to_complete.append(mission_id)
                        print(f"[MockEnv] Mission {mission_id} completed by drone {d['drone_id']}")
            
            # Apply total battery drain
            total_drain = base_drain + mission_drain
            d["battery_percent"] = max(0.0, d["battery_percent"] - total_drain)
            
            # mechanical health may degrade after many ticks
            if d["mechanical_health"] == "ok" and self.tick % 50 == 0:
                d["mechanical_health"] = "degraded"
            elif d["mechanical_health"] == "degraded" and self.tick % 30 == 0:
                d["mechanical_health"] = "critical"
            # sensor status may fluctuate
            if self.tick % 25 == 0:
                for sensor in d["sensor_status"]:
                    if d["sensor_status"][sensor] == "ok":
                        d["sensor_status"][sensor] = "degraded"
                    elif d["sensor_status"][sensor] == "degraded":
                        d["sensor_status"][sensor] = "ok"
        
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
                        v["cooldown_until_tick"] = self.tick + 2
                        print(f"[MockEnv] Victim {v['victim_id']} freed from completed mission {mission_id}, cooldown until tick {v['cooldown_until_tick']}")
            # Remove from active missions tracking and add to recently completed
            if mission_id in self.active_missions:
                del self.active_missions[mission_id]
                self.recently_completed_missions.append(mission_id)

        # Victim condition updates
        for v in self.victims:
            # injury severity may worsen for critical/severe
            if v["injury_severity"] in ("critical", "severe") and self.tick % 40 == 0:
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
                print(f"[MockEnv] Drone {drone_id} assigned to mission {mission_id}")
                break
    
    def get_completed_missions(self) -> List[str]:
        """Return list of mission IDs that completed in the last step and clear the list."""
        completed = self.recently_completed_missions.copy()
        self.recently_completed_missions.clear()
        return completed

    def get_simulation_state(self) -> Dict[str, Any]:
        """Return a summary of the current simulation state."""
        return {
            "tick": self.tick,
            "weather": {
                "visibility_m": self.visibility,
                "wind_speed_ms": self.wind_speed,
                "temperature_c": self.temperature,
            },
            "num_drones": len(self.drones),
            "num_victims": len(self.victims),
        }
