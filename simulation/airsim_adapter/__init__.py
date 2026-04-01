"""
AirSim adapter package for RescueNet AI.

This package provides structured data contracts and adapter patterns
for integrating with Microsoft AirSim.

Modules:
- contracts.py: Data contracts for telemetry, detections, faults, and commands
- adapter.py: Adapter implementation for connecting to AirSim
"""

from .contracts import (
    AirSimTelemetry,
    AirSimDetection,
    AirSimFaultEvent,
    AirSimMissionCommand,
    AirSimEnvironmentState,
    SensorType,
    SensorStatus,
    DroneOperationalStatus,
    DetectionConfidence,
    MissionCommandType,
    telemetry_to_drone_state,
    detection_to_victim_state,
    create_mission_command,
    validate_telemetry,
    validate_detection
)

from .adapter import AirSimAdapter, create_airsim_adapter

__all__ = [
    # Contracts
    "AirSimTelemetry",
    "AirSimDetection",
    "AirSimFaultEvent",
    "AirSimMissionCommand",
    "AirSimEnvironmentState",
    "SensorType",
    "SensorStatus",
    "DroneOperationalStatus",
    "DetectionConfidence",
    "MissionCommandType",
    
    # Transformation functions
    "telemetry_to_drone_state",
    "detection_to_victim_state",
    "create_mission_command",
    "validate_telemetry",
    "validate_detection",
    
    # Adapter
    "AirSimAdapter",
    "create_airsim_adapter"
]