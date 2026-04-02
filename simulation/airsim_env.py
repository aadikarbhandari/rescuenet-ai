import logging
import time
import random
import math
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import airsim
    import msgpackrpc
except ImportError as e:
    logger.error(f"Failed to import AirSim: {e}")
    raise ImportError(
        "AirSim package not installed. Please install it with: pip install airsim\n"
        "Also ensure Unreal Engine is running with AirSim plugin installed."
    ) from e


class AirSimEnv:
    """
    AirSim environment adapter for RescueNet AI.
    
    Connects to real AirSim running in Unreal Engine to provide
    realistic drone simulation for rescue operations.
    """
    
    def __init__(self, settings: Any):
        """
        Initialize AirSim environment.
        
        Args:
            settings: Configuration object with attributes:
                - airsim_ip: str - AirSim server IP (default: "localhost")
                - airsim_port: int - AirSim server port (default: 41451)
                - drone_names: List[str] - List of drone names to control
                - battery_drain_rate: float - Battery drain per second while flying
                - battery_idle_drain: float - Battery drain per second while idle
                - battery_critical: float - Critical battery threshold (0-100)
                - charging_rate: float - Battery percent per second while charging
                - rescue_stations: List[Dict] - Station configurations
                
        Raises:
            ImportError: If AirSim is not available
            ConnectionError: If cannot connect to AirSim
        """
        self.settings = settings
        self.client = None
        self._connected = False
        self._tick = 0
        
        # Get configuration with defaults
        self.airsim_ip = getattr(settings, 'airsim_ip', 'localhost')
        self.airsim_port = getattr(settings, 'airsim_port', 41451)
        self.drone_names = getattr(settings, 'drone_names', ['Drone1'])
        self.battery_drain_rate = getattr(settings, 'battery_drain_rate', 2.0)
        self.battery_idle_drain = getattr(settings, 'battery_idle_drain', 0.5)
        self.battery_critical = getattr(settings, 'battery_critical', 15.0)
        self.charging_rate = getattr(settings, 'charging_rate', 10.0)
        
        # Initialize state tracking
        self.drone_states: Dict[str, Dict[str, Any]] = {}
        self.victims: List[Dict[str, Any]] = []
        self.rescue_stations: List[Dict[str, Any]] = []
        
        # Flight time tracking for battery estimation
        self.flight_times: Dict[str, float] = {name: 0.0 for name in self.drone_names}
        self.idle_times: Dict[str, float] = {name: 0.0 for name in self.drone_names}
        
        # Initialize rescue stations
        self._initialize_stations()
        
        # Attempt connection
        self.connect()
        
        logger.info(f"AirSim environment initialized with {len(self.drone_names)} drones")
    
    def _initialize_stations(self) -> None:
        """Initialize rescue stations from settings."""
        stations_config = getattr(self.settings, 'rescue_stations', [
            {"name": "Station_1", "x": 0, "y": 0, "z": 0, "supplies": {"first_aid_kit": 10, "water": 20, "food": 15}},
            {"name": "Station_2", "x": 50, "y": 50, "z": 0, "supplies": {"first_aid_kit": 10, "water": 20, "food": 15}},
        ])
        
        for station in stations_config:
            self.rescue_stations.append({
                "name": station.get("name", f"Station_{len(self.rescue_stations)}"),
                "x": station.get("x", 0),
                "y": station.get("y", 0),
                "z": station.get("z", 0),
                "supplies": station.get("supplies", {"first_aid_kit": 10, "water": 20, "food": 15}),
                "charging_slots": getattr(self.settings, 'charging_slots', 4),
                "drones_present": []
            })
        
        logger.info(f"Initialized {len(self.rescue_stations)} rescue stations")
    
    def connect(self) -> None:
        """
        Connect to AirSim and initialize all drones.
        
        Raises:
            ConnectionError: If cannot connect to AirSim server
        """
        try:
            logger.info(f"Connecting to AirSim at {self.airsim_ip}:{self.airsim_port}")
            
            # Create client connection
            self.client = airsim.MultirotorClient(
                ip=self.airsim_ip, 
                port=self.airsim_port
            )
            
            # Verify connection
            self.client.confirmConnection()
            logger.info("AirSim connection confirmed")
            
            # Initialize each drone
            for drone_name in self.drone_names:
                try:
                    # Enable API control
                    self.client.enableApiControl(True, vehicle_name=drone_name)
                    self.client.armDisarm(True, vehicle_name=drone_name)
                    
                    # Initialize drone state
                    self.drone_states[drone_name] = {
                        "drone_id": drone_name,
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                        "battery_percent": 100.0,
                        "status": "idle",
                        "velocity": {"x": 0, "y": 0, "z": 0},
                        "heading": 0.0,
                        "current_mission": None,
                        "payload": {"first_aid_kit": 0, "water": 0, "food": 0},
                        "current_station": None
                    }
                    
                    logger.info(f"Initialized drone: {drone_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to initialize drone {drone_name}: {e}")
                    raise ConnectionError(f"Failed to initialize drone {drone_name}: {e}") from e
            
            # Takeoff all drones
            self._takeoff_all_drones()
            
            self._connected = True
            logger.info("All drones connected and ready")
            
        except msgpackrpc.error.TimeoutError as e:
            logger.error(f"Connection timeout: {e}")
            raise ConnectionError(
                f"Cannot connect to AirSim at {self.airsim_ip}:{self.airsim_port}\n"
                "Please ensure:\n"
                "1. Unreal Engine is running with AirSim plugin\n"
                "2. AirSim settings.json has 'ApiServerPort' configured\n"
                "3. No firewall is blocking the connection"
            ) from e
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise ConnectionError(
                f"Failed to connect to AirSim: {e}\n"
                "Please check that Unreal Engine is running and AirSim is properly configured."
            ) from e
    
    def _takeoff_all_drones(self) -> None:
        """Takeoff all drones asynchronously."""
        takeoff_tasks = []
        for drone_name in self.drone_names:
            try:
                task = self.client.takeoffAsync(vehicle_name=drone_name)
                takeoff_tasks.append((drone_name, task))
            except Exception as e:
                logger.warning(f"Takeoff failed for {drone_name}: {e}")
        
        # Wait for all to complete
        for drone_name, task in takeoff_tasks:
            try:
                task.join()
                self.drone_states[drone_name]["status"] = "flying"
                logger.info(f"Drone {drone_name} took off successfully")
            except Exception as e:
                logger.error(f"Takeoff wait failed for {drone_name}: {e}")
    
    def get_drone_telemetry(self, drone_name: str) -> Dict[str, Any]:
        """
        Get telemetry data for a specific drone.
        
        Args:
            drone_name: Name of the drone
            
        Returns:
            Dictionary containing:
                - drone_id: str
                - x, y, z: float - position in NED coordinates
                - battery_percent: float - estimated battery level
                - status: str - current status
                - velocity: dict - velocity vector
                - heading: float - yaw angle in degrees
        """
        if drone_name not in self.drone_states:
            logger.warning(f"Unknown drone: {drone_name}")
            return {}
        
        try:
            # Get state from AirSim
            state = self.client.getMultirotorState(vehicle_name=drone_name)
            kinematics = state.kinematics_estimated
            
            # Extract position
            position = kinematics.position
            x = position.x_val
            y = position.y_val
            z = position.z_val
            
            # Extract velocity
            velocity = kinematics.linear_velocity
            velocity_dict = {
                "x": velocity.x_val,
                "y": velocity.y_val,
                "z": velocity.z_val
            }
            
            # Calculate heading from velocity or orientation
            if state.kinematics_estimated.orientation:
                orientation = state.kinematics_estimated.orientation
                # Convert quaternion to yaw (heading)
                w, x, y, z = orientation.w_val, orientation.x_val, orientation.y_val, orientation.z_val
                heading = math.degrees(math.atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z)))
            else:
                heading = 0.0
            
            # Get GPS data
            try:
                gps_data = self.client.getGpsData(vehicle_name=drone_name)
                has_gps = gps_data.is_valid
            except:
                has_gps = False
            
            # Estimate battery based on flight time
            battery = self.drone_states[drone_name].get("battery_percent", 100.0)
            
            # Update state
            self.drone_states[drone_name].update({
                "x": x,
                "y": y,
                "z": z,
                "velocity": velocity_dict,
                "heading": heading,
                "gps_valid": has_gps
            })
            
            return {
                "drone_id": drone_name,
                "x": x,
                "y": y,
                "z": z,
                "battery_percent": battery,
                "status": self.drone_states[drone_name]["status"],
                "velocity": velocity_dict,
                "heading": heading,
                "gps_valid": has_gps
            }
            
        except Exception as e:
            logger.error(f"Failed to get telemetry for {drone_name}: {e}")
            # Return cached state on error
            return self.drone_states[drone_name].copy()
    
    def get_all_telemetry(self) -> List[Dict[str, Any]]:
        """Get telemetry for all drones."""
        return [self.get_drone_telemetry(name) for name in self.drone_names]
    
    def detect_victims(self) -> List[Dict[str, Any]]:
        """
        Detect victims in the scene using object poses.
        
        Looks for objects named "Victim_*", "Person_*", or "Survivor_*"
        
        Returns:
            List of victim dictionaries with:
                - victim_id: str
                - x, y, z: float - position
                - detected: bool
                - confidence: float - detection confidence (0.65-0.99)
        """
        detected_victims = []
        object_names = ["Victim_", "Person_", "Survivor_"]
        
        # Try to get object poses from AirSim
        try:
            # Get list of all object names in the scene
            object_names_list = self.client.simListSceneObjects(".*")
            
            for name in object_names_list:
                for prefix in object_names:
                    if name.startswith(prefix):
                        try:
                            pose = self.client.simGetObjectPose(name)
                            if pose.position:
                                detected_victims.append({
                                    "victim_id": name,
                                    "x": pose.position.x_val,
                                    "y": pose.position.y_val,
                                    "z": pose.position.z_val,
                                    "detected": True,
                                    "confidence": random.uniform(0.65, 0.99)
                                })
                                break
                        except Exception as e:
                            logger.debug(f"Could not get pose for {name}: {e}")
                            
        except Exception as e:
            logger.warning(f"Object detection failed, using manual victims: {e}")
        
        self.victims = detected_victims
        return detected_victims
    
    def fly_drone_to(self, drone_name: str, x: float, y: float, z: float, 
                     velocity: float = 5.0) -> None:
        """
        Move a drone to a target position.
        
        Args:
            drone_name: Name of the drone
            x, y, z: Target position in NED coordinates
            velocity: Movement speed in m/s
        """
        if drone_name not in self.drone_states:
            logger.error(f"Unknown drone: {drone_name}")
            return
        
        try:
            self.client.moveToPositionAsync(
                x, y, z, velocity, 
                vehicle_name=drone_name
            )
            self.drone_states[drone_name]["status"] = "flying"
            self.drone_states[drone_name]["current_mission"] = {
                "type": "fly_to",
                "target": (x, y, z)
            }
            logger.info(f"Drone {drone_name} moving to ({x}, {y}, {z})")
        except Exception as e:
            logger.error(f"Failed to move drone {drone_name}: {e}")
    
    def return_to_base(self, drone_name: str, station_index: int = 0) -> None:
        """
        Command drone to return to nearest rescue station.
        
        Args:
            drone_name: Name of the drone
            station_index: Index of the station to return to (default: 0)
        """
        if station_index >= len(self.rescue_stations):
            logger.warning(f"Invalid station index: {station_index}")
            station_index = 0
        
        station = self.rescue_stations[station_index]
        self.fly_drone_to(drone_name, station["x"], station["y"], station["z"], velocity=8.0)
        self.drone_states[drone_name]["status"] = "returning_to_base"
        self.drone_states[drone_name]["current_mission"] = {
            "type": "return_to_base",
            "station": station["name"]
        }
        logger.info(f"Drone {drone_name} returning to {station['name']}")
    
    def land_drone(self, drone_name: str) -> None:
        """
        Land a drone at current position.
        
        Args:
            drone_name: Name of the drone
        """
        if drone_name not in self.drone_states:
            return
        
        try:
            self.client.landAsync(vehicle_name=drone_name).join()
            self.drone_states[drone_name]["status"] = "landed"
            logger.info(f"Drone {drone_name} landed")
        except Exception as e:
            logger.error(f"Failed to land drone {drone_name}: {e}")
    
    def charge_drone(self, drone_name: str, station_index: int = 0) -> None:
        """
        Charge a drone at a station.
        
        Args:
            drone_name: Name of the drone
            station_index: Index of the charging station
        """
        if drone_name not in self.drone_states:
            return
            
        if station_index >= len(self.rescue_stations):
            station_index = 0
        
        station = self.rescue_stations[station_index]
        self.drone_states[drone_name]["status"] = "charging"
        self.drone_states[drone_name]["current_station"] = station["name"]
        
        # Add drone to station's drones_present
        if drone_name not in station["drones_present"]:
            station["drones_present"].append(drone_name)
        
        logger.info(f"Drone {drone_name} charging at {station['name']}")
    
    def deliver_supplies(self, drone_name: str, victim_id: str, 
                         supply_type: str = "first_aid_kit") -> bool:
        """
        Deliver supplies to a victim.
        
        Args:
            drone_name: Name of the delivering drone
            victim_id: ID of the victim to deliver to
            supply_type: Type of supply (first_aid_kit, water, food)
            
        Returns:
            True if delivery successful, False if out of stock
        """
        # Find victim's position
        victim_pos = None
        for victim in self.victims:
            if victim["victim_id"] == victim_id:
                victim_pos = (victim["x"], victim["y"], victim["z"])
                break
        
        if victim_pos is None:
            logger.warning(f"Victim {victim_id} not found")
            return False
        
        # Check supply availability at current station
        station_idx = 0
        current_station = self.drone_states[drone_name].get("current_station")
        
        if current_station:
            for idx, station in enumerate(self.rescue_stations):
                if station["name"] == current_station:
                    station_idx = idx
                    break
        
        station = self.rescue_stations[station_idx]
        
        if station["supplies"].get(supply_type, 0) <= 0:
            logger.warning(f"No {supply_type} available at {station['name']}")
            return False
        
        # Fly to victim location
        self.fly_drone_to(drone_name, victim_pos[0], victim_pos[1], max(victim_pos[2], 5.0))
        
        # Wait for arrival (simplified - in real code would wait for position)
        time.sleep(2)
        
        # Simulate delivery
        station["supplies"][supply_type] -= 1
        self.drone_states[drone_name]["payload"][supply_type] = max(
            0, self.drone_states[drone_name]["payload"].get(supply_type, 0) - 1
        )
        
        logger.info(f"Delivered {supply_type} to {victim_id} from {station['name']}")
        return True
    
    def update_battery(self, drone_name: str, dt: float) -> None:
        """
        Update battery level based on drone status and time delta.
        
        Args:
            drone_name: Name of the drone
            dt: Time delta in seconds
        """
        if drone_name not in self.drone_states:
            return
        
        state = self.drone_states[drone_name]
        status = state.get("status", "idle")
        
        # Calculate drain rate based on status
        if status == "flying" or status == "returning_to_base":
            drain = self.battery_drain_rate * dt
            self.flight_times[drone_name] += dt
        elif status == "charging":
            # Actually charging - increase battery
            state["battery_percent"] = min(
                100.0, 
                state["battery_percent"] + self.charging_rate * dt
            )
            return
        elif status == "hovering":
            drain = self.battery_drain_rate * 0.5 * dt
        else:  # idle or landed
            drain = self.battery_idle_drain * dt
            self.idle_times[drone_name] += dt
        
        # Update battery
        state["battery_percent"] = max(0.0, state["battery_percent"] - drain)
        
        # Check critical battery
        if state["battery_percent"] < self.battery_critical and status != "returning_to_base" and status != "charging":
            logger.warning(f"Drone {drone_name} battery critical ({state['battery_percent']:.1f}%)")
            state["status"] = "returning_to_base"
            self.return_to_base(drone_name)
        
        # Emergency landing
        if state["battery_percent"] <= 0:
            logger.error(f"Drone {drone_name} battery depleted - emergency landing")
            state["status"] = "emergency_landing"
            self.land_drone(drone_name)
    
    def step(self, dt: float = 1.0) -> Dict[str, Any]:
        """
        Advance simulation by one time step.
        
        Args:
            dt: Time delta in seconds
            
        Returns:
            Observation dictionary with all drone and victim states
        """
        self._tick += 1
        
        # Update all drone batteries
        for drone_name in self.drone_names:
            self.update_battery(drone_name, dt)
        
        # Refresh telemetry
        all_telemetry = self.get_all_telemetry()
        
        # Detect victims
        detected_victims = self.detect_victims()
        
        # Get station status
        station_status = self.get_station_status()
        
        return {
            "tick": self._tick,
            "dt": dt,
            "drones": all_telemetry,
            "victims": detected_victims,
            "stations": station_status,
            "connected": self._connected
        }
    
    def get_station_status(self) -> List[Dict[str, Any]]:
        """
        Get status of all rescue stations.
        
        Returns:
            List of station status dictionaries
        """
        status = []
        for station in self.rescue_stations:
            status.append({
                "name": station["name"],
                "x": station["x"],
                "y": station["y"],
                "z": station["z"],
                "supplies": station["supplies"].copy(),
                "charging_slots": station["charging_slots"],
                "available_slots": station["charging_slots"] - len(station["drones_present"]),
                "drones_present": station["drones_present"].copy()
            })
        return status
    
    def spawn_victims(self, count: int = 8) -> List[Dict[str, Any]]:
        """
        Spawn victim objects in the simulation.
        
        Uses AirSim's simSpawnObject if available, otherwise creates
        manual records with random positions.
        
        Args:
            count: Number of victims to spawn
            
        Returns:
            List of spawned victim dictionaries
        """
        spawned_victims = []
        
        # Define spawn area
        spawn_x_range = (-100, 100)
        spawn_y_range = (-100, 100)
        
        for i in range(count):
            victim_id = f"Victim_{i+1}"
            
            # Random position within spawn area
            x = random.uniform(*spawn_x_range)
            y = random.uniform(*spawn_y_range)
            z = 0.0  # Ground level
            
            try:
                # Try to spawn object in AirSim
                self.client.simSpawnObject(
                    object_name=victim_id,
                    object_asset_path="",
                    pose=airsim.Pose(
                        position=airsim.Vector3r(x_val=x, y_val=y, z_val=z),
                        orientation=airsim.Quaternionr()
                    ),
                    physics=False
                )
                logger.info(f"Spawned victim {victim_id} at ({x}, {y}, {z})")
                
            except Exception as e:
                # If spawning not available, just create record
                logger.debug(f"simSpawnObject not available: {e}")
            
            spawned_victims.append({
                "victim_id": victim_id,
                "x": x,
                "y": y,
                "z": z,
                "detected": False,
                "confidence": random.uniform(0.65, 0.99)
            })
        
        self.victims.extend(spawned_victims)
        return spawned_victims
    
    def reset(self) -> None:
        """Reset the simulation to initial state."""
        try:
            # Land all drones
            for drone_name in self.drone_names:
                try:
                    self.land_drone(drone_name)
                except:
                    pass
            
            # Reset states
            for drone_name in self.drone_names:
                self.drone_states[drone_name]["battery_percent"] = 100.0
                self.drone_states[drone_name]["status"] = "idle"
                self.drone_states[drone_name]["current_mission"] = None
            
            # Reset flight times
            self.flight_times = {name: 0.0 for name in self.drone_names}
            self.idle_times = {name: 0.0 for name in self.drone_names}
            
            # Clear victims
            self.victims = []
            
            logger.info("Environment reset complete")
            
        except Exception as e:
            logger.error(f"Reset failed: {e}")
    
    def close(self) -> None:
        """Clean up connection and resources."""
        try:
            # Disable API control for all drones
            for drone_name in self.drone_names:
                try:
                    self.client.enableApiControl(False, vehicle_name=drone_name)
                except:
                    pass
            
            self._connected = False
            logger.info("AirSim environment closed")
            
        except Exception as e:
            logger.error(f"Error during close: {e}")
    
    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        try:
            self.close()
        except:
            pass
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to AirSim."""
        return self._connected
    
    def get_drone_state(self, drone_name: str) -> Optional[Dict[str, Any]]:
        """Get current state of a drone."""
        return self.drone_states.get(drone_name)
    
    def get_victim(self, victim_id: str) -> Optional[Dict[str, Any]]:
        """Get victim by ID."""
        for victim in self.victims:
            if victim["victim_id"] == victim_id:
                return victim
        return None
    
    def get_station(self, station_name: str) -> Optional[Dict[str, Any]]:
        """Get station by name."""
        for station in self.rescue_stations:
            if station["name"] == station_name:
                return station
        return None
    
    def get_nearest_station(self, drone_name: str) -> Dict[str, Any]:
        """Find nearest rescue station to a drone."""
        if drone_name not in self.drone_states:
            return self.rescue_stations[0] if self.rescue_stations else {}
        
        drone_pos = (
            self.drone_states[drone_name]["x"],
            self.drone_states[drone_name]["y"],
            self.drone_states[drone_name]["z"]
        )
        
        nearest = None
        min_dist = float('inf')
        
        for station in self.rescue_stations:
            dist = math.sqrt(
                (station["x"] - drone_pos[0])**2 +
                (station["y"] - drone_pos[1])**2 +
                (station["z"] - drone_pos[2])**2
            )
            if dist < min_dist:
                min_dist = dist
                nearest = station
        
        return nearest if nearest else self.rescue_stations[0] if self.rescue_stations else {}