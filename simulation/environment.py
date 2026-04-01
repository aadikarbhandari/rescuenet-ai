"""
Environment abstraction interface for RescueNet AI.

This module defines the abstract base class for all environment providers
(demo/mock, AirSim, etc.). The interface provides a clean boundary between
simulation data sources and the core AI logic.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class Environment(ABC):
    """Abstract base class for all environment providers."""
    
    @abstractmethod
    def step(self) -> None:
        """
        Advance simulation by one tick.
        Updates internal state, weather, drone/victim conditions, etc.
        """
        pass
    
    @abstractmethod
    def get_drone_snapshots(self) -> List[Dict[str, Any]]:
        """
        Return current drone states as a list of dictionaries.
        
        Returns:
            List of drone state dictionaries with at least:
            - drone_id: str
            - battery_percent: float
            - mechanical_health: str
            - sensor_status: Dict[str, str]
            - payload_kg: float
            - winch_status: str
            - position: Tuple[float, float, float]
            - wind_speed_ms: float
            - temperature_c: float
            - visibility_m: float
            - current_mission: Optional[str]
            - operational_status: str
        """
        pass
    
    @abstractmethod
    def get_victim_snapshots(self) -> List[Dict[str, Any]]:
        """
        Return current victim states as a list of dictionaries.
        
        Returns:
            List of victim state dictionaries with at least:
            - victim_id: str
            - position: Tuple[float, float, float]
            - injury_severity: str
            - detected_by: str
            - assigned_drone: Optional[str]
            - mission_id: Optional[str]
            - cooldown_until_tick: int
            - conscious: bool
            - bleeding: str
            - body_temperature_c: float
            - accessibility: float
        """
        pass
    
    @abstractmethod
    def get_completed_missions(self) -> List[str]:
        """
        Return list of mission IDs that completed in the last step.
        
        Returns:
            List of mission ID strings that completed in the most recent step().
            The list is cleared after being returned.
        """
        pass
    
    @abstractmethod
    def update_victim_assignment(self, victim_id: str, drone_id: str, mission_id: str) -> None:
        """
        Update victim assignment in the environment.
        
        Args:
            victim_id: ID of the victim to update
            drone_id: ID of the drone assigned to the victim
            mission_id: ID of the mission for this assignment
        """
        pass
    
    @abstractmethod
    def update_drone_mission(self, drone_id: str, mission_id: str) -> None:
        """
        Update drone mission assignment in the environment.
        
        Args:
            drone_id: ID of the drone to update
            mission_id: ID of the mission assigned to the drone
        """
        pass
    
    @property
    @abstractmethod
    def tick(self) -> int:
        """
        Current simulation tick counter.
        
        Returns:
            Current tick number (starts at 0, increments each step()).
        """
        pass
    
    def get_simulation_state(self) -> Dict[str, Any]:
        """
        Return a summary of the current simulation state.
        
        Returns:
            Dictionary with simulation state summary including:
            - tick: int
            - weather: Dict with visibility_m, wind_speed_ms, temperature_c
            - num_drones: int
            - num_victims: int
        """
        return {
            "tick": self.tick,
            "num_drones": len(self.get_drone_snapshots()),
            "num_victims": len(self.get_victim_snapshots()),
        }