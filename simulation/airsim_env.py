"""
AirSim environment adapter for RescueNet AI.

This module implements the Environment interface for AirSim integration
using structured data contracts and adapter patterns.

Key features:
1. Lazy imports: AirSim dependencies are only loaded when needed
2. Activation path: Clean initialization with clear error messages
3. Data contracts: Type-safe data structures for telemetry, detections, etc.
4. Transformation logic: Converts AirSim data to RescueNet models

Note: This module uses lazy imports to avoid loading AirSim dependencies
in demo mode. All AirSim-specific imports are deferred until needed.
"""
import logging
import time
from typing import Dict, List, Any, Optional
from .environment import Environment


class AirSimEnvironment(Environment):
    """
    AirSim environment adapter using structured data contracts.
    
    This class provides the interface between RescueNet and AirSim
    using type-safe data contracts and adapter patterns.
    
    Architecture:
    1. AirSimAdapter handles low-level communication
    2. Data contracts ensure type safety
    3. Transformation functions convert between AirSim and RescueNet models
    4. Mission tracking maintains state between ticks
    """
    
    def __init__(self, host: str = "localhost", port: int = 41451):
        """
        Initialize AirSim environment with lazy imports and activation path.
        
        Args:
            host: AirSim simulator hostname or IP address
            port: AirSim simulator port
            
        Raises:
            ImportError: If AirSim adapter modules are not available
            RuntimeError: If AirSim adapter initialization fails
            
        Note: This uses lazy imports to avoid loading AirSim dependencies
        in demo mode. All AirSim-specific code is loaded on-demand.
        """
        self.host = host
        self.port = port
        self._tick = 0
        self._logger = logging.getLogger(__name__)
        
        # Lazy import AirSim adapter modules
        try:
            from .airsim_adapter.adapter import create_airsim_adapter
            from .airsim_adapter.contracts import (
                AirSimTelemetry,
                AirSimDetection,
                telemetry_to_drone_state,
                detection_to_victim_state,
                create_mission_command,
                MissionCommandType
            )
            
            # Store imported modules for later use
            self._create_airsim_adapter = create_airsim_adapter
            self._AirSimTelemetry = AirSimTelemetry
            self._AirSimDetection = AirSimDetection
            self._telemetry_to_drone_state = telemetry_to_drone_state
            self._detection_to_victim_state = detection_to_victim_state
            self._create_mission_command = create_mission_command
            self._MissionCommandType = MissionCommandType
            
        except ImportError as e:
            self._logger.error(f"Failed to import AirSim adapter modules: {e}")
            raise ImportError(
                "AirSim adapter modules not available. "
                "This may indicate missing files or a corrupted installation. "
                "Required modules: airsim_adapter.adapter, airsim_adapter.contracts"
            ) from e
        
        # Initialize AirSim adapter
        try:
            self._adapter = self._create_airsim_adapter(host=host, port=port)
        except Exception as e:
            self._logger.error(f"Failed to initialize AirSim adapter: {e}")
            raise RuntimeError(
                f"AirSim adapter initialization failed: {e}\n"
                f"This may indicate missing dependencies or configuration issues."
            ) from e
        
        # Mission tracking
        self._active_missions: Dict[str, Dict[str, Any]] = {}  # mission_id -> mission data
        self._completed_missions_buffer: List[str] = []
        
        # Data buffers for transformation
        self._last_telemetry: Dict[str, Any] = {}  # Will store AirSimTelemetry objects
        self._last_detections: List[Any] = []  # Will store AirSimDetection objects
        
        # Performance tracking
        self._last_update_time = time.time()
        self._update_count = 0
        
        # Activation status
        self._activation_status = "activated"
        self._adapter_connected = self._adapter.is_connected()
        
        self._logger.info(
            f"AirSim environment activated successfully "
            f"(host={host}, port={port}, adapter_connected={self._adapter_connected})"
        )
        self._logger.info(
            "Using structured data contracts with lazy imports. "
            "Actual AirSim connectivity deferred to future phase."
        )
    
    def step(self) -> None:
        """
        Advance simulation by one tick using data contracts.
        
        This method:
        1. Increments the tick counter
        2. Fetches latest telemetry from AirSim adapter
        3. Fetches latest detections from AirSim adapter
        4. Checks for completed missions
        5. Updates internal state buffers
        
        Raises:
            RuntimeError: If adapter fails during step operation
        """
        self._tick += 1
        self._logger.debug(f"Step tick {self._tick}")
        
        try:
            # Update telemetry from adapter
            telemetry_list = self._adapter.get_telemetry()
            for telemetry in telemetry_list:
                self._last_telemetry[telemetry.drone_id] = telemetry
            
            # Update detections from adapter
            self._last_detections = self._adapter.get_detections()
            
            # Check for mission completions (simulated)
            self._check_mission_completions()
            
            # Update performance metrics
            self._update_count += 1
            self._last_update_time = time.time()
            
        except Exception as e:
            self._logger.error(f"Step operation failed: {e}")
            raise RuntimeError(
                f"AirSim environment step failed: {e}\n"
                f"This may indicate adapter communication issues."
            ) from e
    
    def get_drone_snapshots(self) -> List[Dict[str, Any]]:
        """
        Get drone states transformed from AirSim telemetry.
        
        Returns:
            List of drone state dictionaries compatible with RescueNet models
            
        Raises:
            RuntimeError: If transformation fails
        """
        drone_states = []
        
        try:
            # Convert each telemetry reading to drone state
            for drone_id, telemetry in self._last_telemetry.items():
                drone_state = self._telemetry_to_drone_state(telemetry)
                if drone_state:
                    drone_states.append(drone_state)
            
            self._logger.debug(f"Returning {len(drone_states)} drone snapshots from telemetry")
            return drone_states
            
        except Exception as e:
            self._logger.error(f"Drone snapshot transformation failed: {e}")
            raise RuntimeError(
                f"Failed to transform AirSim telemetry to drone states: {e}\n"
                f"This may indicate data contract compatibility issues."
            ) from e
    
    def get_victim_snapshots(self) -> List[Dict[str, Any]]:
        """
        Get victim states transformed from AirSim detections.
        
        Returns:
            List of victim state dictionaries compatible with RescueNet models
            
        Raises:
            RuntimeError: If transformation fails
        """
        victim_states = []
        
        try:
            # Convert each detection to victim state
            for detection in self._last_detections:
                victim_state = self._detection_to_victim_state(detection, self._tick)
                if victim_state:
                    victim_states.append(victim_state)
            
            self._logger.debug(f"Returning {len(victim_states)} victim snapshots from detections")
            return victim_states
            
        except Exception as e:
            self._logger.error(f"Victim snapshot transformation failed: {e}")
            raise RuntimeError(
                f"Failed to transform AirSim detections to victim states: {e}\n"
                f"This may indicate data contract compatibility issues."
            ) from e
    
    def get_completed_missions(self) -> List[str]:
        """
        Get list of completed mission IDs.
        
        Returns:
            List of completed mission IDs
        """
        # Return and clear the buffer
        completed = self._completed_missions_buffer.copy()
        self._completed_missions_buffer.clear()
        
        self._logger.debug(f"Returning {len(completed)} completed missions")
        return completed
    
    def update_victim_assignment(self, victim_id: str, drone_id: str, mission_id: str) -> None:
        """
        Update victim assignment and send appropriate commands to AirSim.
        
        This method:
        1. Logs the assignment
        2. Updates internal mission tracking
        3. Sends mission commands to AirSim via adapter
        
        Raises:
            RuntimeError: If command creation or sending fails
        """
        self._logger.info(
            f"Victim assignment: {victim_id} -> {drone_id} (mission: {mission_id})"
        )
        
        try:
            # Create mission in tracking
            self._active_missions[mission_id] = {
                "victim_id": victim_id,
                "drone_id": drone_id,
                "start_tick": self._tick,
                "status": "assigned"
            }
            
            # Send initial mission command to AirSim
            # For now, just send a goto command to victim location
            # In future, this would use actual victim position
            command = self._create_mission_command(
                drone_id=drone_id,
                command_type=self._MissionCommandType.GOTO,
                mission_id=mission_id,
                target_position=(50.0, 50.0, 10.0),  # Placeholder
                speed_ms=5.0
            )
            
            success = self._adapter.send_command(command)
            if success:
                self._logger.info(f"Mission command sent to {drone_id} for mission {mission_id}")
            else:
                self._logger.warning(f"Failed to send mission command to {drone_id}")
                
        except Exception as e:
            self._logger.error(f"Victim assignment failed: {e}")
            raise RuntimeError(
                f"Failed to create or send mission command: {e}\n"
                f"This may indicate adapter communication issues."
            ) from e
    
    def update_drone_mission(self, drone_id: str, mission_id: str) -> None:
        """
        Update drone mission assignment.
        
        This is a convenience method that delegates to update_victim_assignment
        when victim_id is not available.
        
        Raises:
            RuntimeError: If command creation or sending fails
        """
        self._logger.info(f"Drone mission update: {drone_id} -> {mission_id}")
        
        try:
            # Update mission tracking
            if mission_id in self._active_missions:
                self._active_missions[mission_id]["drone_id"] = drone_id
                self._active_missions[mission_id]["status"] = "active"
            
            # Send mission command
            command = self._create_mission_command(
                drone_id=drone_id,
                command_type=self._MissionCommandType.GOTO,
                mission_id=mission_id,
                target_position=(30.0, 30.0, 15.0),  # Placeholder
                speed_ms=5.0
            )
            
            self._adapter.send_command(command)
            
        except Exception as e:
            self._logger.error(f"Drone mission update failed: {e}")
            raise RuntimeError(
                f"Failed to update drone mission: {e}\n"
                f"This may indicate adapter communication issues."
            ) from e
    
    def _check_mission_completions(self) -> None:
        """
        Check for completed missions based on simulation logic.
        
        In a real implementation, this would check AirSim for mission
        completion status. For now, we simulate completions after
        a fixed number of ticks.
        """
        completed_missions = []
        
        for mission_id, mission_data in list(self._active_missions.items()):
            start_tick = mission_data.get("start_tick", 0)
            elapsed_ticks = self._tick - start_tick
            
            # Simulate mission completion after 5 ticks
            if elapsed_ticks >= 5 and mission_data.get("status") == "active":
                mission_data["status"] = "completed"
                mission_data["completion_tick"] = self._tick
                completed_missions.append(mission_id)
                self._logger.info(f"Mission {mission_id} completed at tick {self._tick}")
        
        # Add completed missions to buffer
        self._completed_missions_buffer.extend(completed_missions)
        
        # Remove completed missions from active tracking
        for mission_id in completed_missions:
            self._active_missions.pop(mission_id, None)
    
    @property
    def tick(self) -> int:
        """
        Current simulation tick counter.
        
        Returns:
            Current tick number
        """
        return self._tick
    
    def get_simulation_state(self) -> Dict[str, Any]:
        """
        Return a summary of the current simulation state.
        
        Returns:
            Dictionary with simulation state summary
            
        Raises:
            RuntimeError: If adapter state retrieval fails
        """
        state = super().get_simulation_state()
        
        try:
            # Get adapter metrics
            adapter_metrics = self._adapter.get_metrics()
            
            # Get environment state from adapter
            env_state = self._adapter.get_environment_state()
            
            state.update({
                "airsim_host": self.host,
                "airsim_port": self.port,
                "integration_status": self._activation_status,
                "adapter_connected": self._adapter_connected,
                "active_missions": len(self._active_missions),
                "completed_missions_buffer": len(self._completed_missions_buffer),
                "telemetry_count": len(self._last_telemetry),
                "detection_count": len(self._last_detections),
                "adapter_metrics": adapter_metrics,
                "environment_state": {
                    "tick": env_state.tick,
                    "active_drones": env_state.active_drones,
                    "weather": env_state.weather,
                    "time_of_day": env_state.time_of_day
                },
                "note": "Using structured data contracts with lazy imports. Actual AirSim connectivity deferred."
            })
            return state
            
        except Exception as e:
            self._logger.error(f"Failed to get simulation state: {e}")
            # Return partial state if adapter fails
            state.update({
                "airsim_host": self.host,
                "airsim_port": self.port,
                "integration_status": "adapter_error",
                "adapter_connected": False,
                "active_missions": len(self._active_missions),
                "completed_missions_buffer": len(self._completed_missions_buffer),
                "telemetry_count": len(self._last_telemetry),
                "detection_count": len(self._last_detections),
                "adapter_metrics": {"error": str(e)},
                "environment_state": {
                    "tick": self._tick,
                    "active_drones": [],
                    "weather": {},
                    "time_of_day": "unknown"
                },
                "note": f"Adapter state retrieval failed: {e}"
            })
            return state
