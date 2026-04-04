"""
Vendor adapter contracts + registry.

This allows RescueNet to support mixed drone/sensor vendors without hardcoding
vendor-specific fields in core mission logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NormalizedDrone:
    id: str
    battery: float
    position: List[float]
    status: str
    payload_kg: float = 0.0
    current_mission_id: Optional[str] = None
    vendor_meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedVictimSignal:
    id: str
    position: List[float]
    severity: str
    confidence: float
    detected_by: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class DroneAdapter(ABC):
    """Contract for vendor-specific drone control + telemetry adapters."""

    @abstractmethod
    def list_drones(self) -> List[NormalizedDrone]:
        raise NotImplementedError

    @abstractmethod
    def dispatch(self, drone_id: str, target: Dict[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send_to_charge(self, drone_id: str, station: Dict[str, Any]) -> bool:
        raise NotImplementedError


class SensorAdapter(ABC):
    """Contract for external disaster/sensor systems."""

    @abstractmethod
    def list_signals(self) -> List[NormalizedVictimSignal]:
        raise NotImplementedError


class AdapterRegistry:
    """Simple runtime registry for heterogenous vendor integrations."""

    def __init__(self):
        self._drone_adapters: Dict[str, DroneAdapter] = {}
        self._sensor_adapters: Dict[str, SensorAdapter] = {}

    def register_drone_adapter(self, vendor: str, adapter: DroneAdapter) -> None:
        self._drone_adapters[vendor] = adapter

    def register_sensor_adapter(self, vendor: str, adapter: SensorAdapter) -> None:
        self._sensor_adapters[vendor] = adapter

    def get_drone_adapter(self, vendor: str) -> Optional[DroneAdapter]:
        return self._drone_adapters.get(vendor)

    def get_sensor_adapter(self, vendor: str) -> Optional[SensorAdapter]:
        return self._sensor_adapters.get(vendor)

    def list_registered(self) -> Dict[str, List[str]]:
        return {
            "drone_vendors": sorted(self._drone_adapters.keys()),
            "sensor_vendors": sorted(self._sensor_adapters.keys()),
        }

