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

        # Drone battery naturally depletes (more if payload > 0)
        for d in self.drones:
            drain = 0.05 + (0.02 * d["payload_kg"])
            d["battery_percent"] = max(0.0, d["battery_percent"] - drain)
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
