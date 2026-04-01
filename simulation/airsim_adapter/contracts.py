"""
AirSim data contracts and models for RescueNet AI.

This module defines structured data contracts for AirSim telemetry and observations.
These contracts provide a clear interface between AirSim raw data and RescueNet's
internal state models.

Key principles:
1. Type-safe data structures using dataclasses
2. Clear mapping between AirSim raw data and RescueNet models
3. Validation and transformation logic
4. Support for both real AirSim data and placeholder data during development
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import logging


class SensorType(str, Enum):
    """Types of sensors available on drones."""
    RGB_CAMERA = "rgb_camera"
    THERMAL_CAMERA = "thermal_camera"
    LIDAR = "lidar"
    GPS = "gps"
    IMU = "imu"
    BAROMETER = "barometer"
    WIND_SPEED = "wind_speed"
    TEMPERATURE = "temperature"
    VISIBILITY = "visibility"


class SensorStatus(str, Enum):
    """Status of a sensor."""
    OK = "ok"
    DEGRADED = "degraded"
    FAULT = "fault"
    CALIBRATING = "calibrating"
    OFFLINE = "offline"


class DroneOperationalStatus(str, Enum):
    """Operational status of a drone."""
    IDLE = "idle"
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    ACTION_IN_PROGRESS = "action_in_progress"
    RETURNING_TO_BASE = "returning_to_base"
    CHARGING = "charging"
    UNAVAILABLE_FAULT = "unavailable_fault"


class DetectionConfidence(str, Enum):
    """Confidence levels for victim detections."""
    HIGH = "high"      # > 0.8 confidence
    MEDIUM = "medium"  # 0.5-0.8 confidence
    LOW = "low"        # < 0.5 confidence
    UNCONFIRMED = "unconfirmed"  # Initial detection


class MissionCommandType(str, Enum):
    """Types of mission commands that can be sent to AirSim."""
    TAKEOFF = "takeoff"
    LAND = "land"
    GOTO = "goto"
    HOVER = "hover"
    SCAN_AREA = "scan_area"
    APPROACH_VICTIM = "approach_victim"
    DEPLOY_WINCH = "deploy_winch"
    RETRACT_WINCH = "retract_winch"
    RETURN_TO_BASE = "return_to_base"
    ABORT_MISSION = "abort_mission"


@dataclass
class AirSimTelemetry:
    """
    Raw telemetry data from AirSim for a single drone.
    
    This represents the direct output from AirSim APIs before any processing.
    """
    drone_id: str
    timestamp: float  # Unix timestamp or simulation time
    
    # Position and orientation
    position: Tuple[float, float, float]  # (x, y, z) in NED coordinates
    orientation: Tuple[float, float, float, float]  # (w, x, y, z) quaternion
    velocity: Tuple[float, float, float]  # (vx, vy, vz) in m/s
    angular_velocity: Tuple[float, float, float]  # (wx, wy, wz) in rad/s
    
    # Sensor readings
    gps_position: Optional[Tuple[float, float, float]] = None  # (lat, lon, alt)
    gps_velocity: Optional[Tuple[float, float, float]] = None  # GPS velocity
    imu_acceleration: Optional[Tuple[float, float, float]] = None  # (ax, ay, az)
    imu_gyro: Optional[Tuple[float, float, float]] = None  # (gx, gy, gz)
    barometer_altitude: Optional[float] = None  # Altitude from barometer
    barometer_pressure: Optional[float] = None  # Pressure in hPa
    
    # Environmental sensors
    wind_speed_ms: Optional[float] = None
    temperature_c: Optional[float] = None
    visibility_m: Optional[float] = None
    
    # System status
    battery_percent: Optional[float] = None  # 0-100%
    is_armed: bool = False
    is_flying: bool = False
    flight_mode: str = "Unknown"
    
    # Camera and sensor status
    camera_images: Dict[str, Any] = field(default_factory=dict)  # Raw image data
    lidar_point_cloud: Optional[List[Tuple[float, float, float]]] = None
    
    # Metadata
    frame_id: Optional[int] = None  # AirSim frame ID
    collision_count: int = 0
    ground_truth: bool = False  # Whether this is ground truth data


@dataclass
class AirSimDetection:
    """
    Raw detection/observation from AirSim sensors.
    
    This represents objects detected by drone sensors (victims, obstacles, etc.)
    """
    detection_id: str
    timestamp: float
    drone_id: str
    sensor_type: SensorType
    
    # Detection location
    position: Tuple[float, float, float]  # World coordinates
    bounding_box: Optional[Tuple[float, float, float, float]] = None  # (x1, y1, x2, y2) in image space
    
    # Detection properties
    confidence: float = 0.0  # 0.0-1.0
    detection_class: str = "unknown"  # "victim", "obstacle", "landmark", etc.
    
    # Additional metadata
    sensor_reading: Optional[Dict[str, Any]] = None  # Raw sensor data
    image_frame: Optional[Any] = None  # Reference to image frame
    distance_to_drone: Optional[float] = None  # Distance in meters
    
    # For victim detections
    injury_severity: Optional[str] = None  # "minor", "moderate", "severe", "critical"
    victim_state: Optional[Dict[str, Any]] = None  # Additional victim state


@dataclass
class AirSimFaultEvent:
    """
    Fault or health event from AirSim.
    
    Represents system faults, sensor failures, or other health events.
    """
    event_id: str
    timestamp: float
    drone_id: str
    event_type: str  # "sensor_fault", "motor_fault", "battery_low", "collision", "communication_loss"
    
    severity: str  # "info", "warning", "error", "critical"
    component: str  # Component name (e.g., "motor_1", "rgb_camera", "gps")
    description: str
    
    # Additional data
    metrics: Dict[str, Any] = field(default_factory=dict)
    recovery_action: Optional[str] = None
    is_resolved: bool = False


@dataclass
class AirSimMissionCommand:
    """
    Mission command to be sent to AirSim.
    
    This represents high-level mission commands that the RescueNet system
    sends to AirSim for execution.
    """
    command_id: str
    timestamp: float
    drone_id: str
    command_type: MissionCommandType
    
    # Command parameters
    target_position: Optional[Tuple[float, float, float]] = None
    target_altitude: Optional[float] = None
    speed_ms: Optional[float] = None
    duration_s: Optional[float] = None
    
    # Mission context
    mission_id: Optional[str] = None
    victim_id: Optional[str] = None
    
    # Command options
    wait_for_completion: bool = True
    timeout_s: Optional[float] = None
    
    # Metadata
    priority: int = 1  # 1=lowest, 10=highest
    retry_count: int = 0


@dataclass
class AirSimEnvironmentState:
    """
    Overall environment state from AirSim.
    
    This provides a snapshot of the entire simulation environment.
    """
    timestamp: float
    tick: int
    
    # Active drones
    active_drones: List[str]
    
    # Environment conditions
    weather: Dict[str, Any]  # temperature, wind, visibility, etc.
    time_of_day: str  # "day", "night", "dawn", "dusk"
    
    # Simulation state
    is_paused: bool = False
    simulation_speed: float = 1.0  # 1.0 = realtime
    
    # Performance metrics
    frame_rate: Optional[float] = None
    latency_ms: Optional[float] = None


# Transformation functions for converting AirSim data to RescueNet models

def telemetry_to_drone_state(telemetry: AirSimTelemetry, 
                            previous_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convert AirSim telemetry to RescueNet DroneState dictionary.
    
    Args:
        telemetry: Raw AirSim telemetry
        previous_state: Previous drone state for delta calculations
        
    Returns:
        Dictionary compatible with DroneState constructor
    """
    # Calculate battery health based on telemetry
    battery_percent = telemetry.battery_percent or 100.0
    
    # Determine mechanical health based on fault events and telemetry
    mechanical_health = "ok"
    if telemetry.collision_count > 0:
        mechanical_health = "degraded"
    if telemetry.collision_count > 2:
        mechanical_health = "critical"
    
    # Map sensor status
    sensor_status = {
        "rgb": "ok",  # Default, would be updated based on actual sensor status
        "thermal": "ok",
        "lidar": "ok",
        "gps": "ok" if telemetry.gps_position else "degraded",
        "imu": "ok" if telemetry.imu_acceleration else "degraded"
    }
    
    # Determine operational status from flight mode and telemetry
    operational_status = "idle"
    if telemetry.is_flying:
        if telemetry.flight_mode == "ReturnToLaunch":
            operational_status = "returning_to_base"
        else:
            operational_status = "en_route"  # Default for flying
    
    return {
        "drone_id": telemetry.drone_id,
        "battery_percent": battery_percent,
        "mechanical_health": mechanical_health,
        "sensor_status": sensor_status,
        "payload_kg": 0.0,  # Would come from winch/payload sensors
        "winch_status": "ready",  # Default
        "position": telemetry.position,
        "wind_speed_ms": telemetry.wind_speed_ms or 0.0,
        "temperature_c": telemetry.temperature_c or 22.0,
        "visibility_m": telemetry.visibility_m or 1000.0,
        "current_mission": None,  # Would be populated from mission tracking
        "operational_status": operational_status,
        "target_position": None  # Would come from mission commands
    }


def detection_to_victim_state(detection: AirSimDetection, 
                             current_tick: int) -> Dict[str, Any]:
    """
    Convert AirSim detection to RescueNet VictimState dictionary.
    
    Args:
        detection: Raw AirSim detection
        current_tick: Current simulation tick
        
    Returns:
        Dictionary compatible with VictimState constructor
    """
    # Only process victim detections
    if detection.detection_class != "victim":
        return None
    
    # Map detection confidence to RescueNet confidence
    detection_confidence = detection.confidence
    
    # Determine if detection is confirmed
    is_confirmed = detection_confidence >= 0.6
    
    # Map injury severity
    injury_severity = detection.injury_severity or "moderate"
    
    # Extract additional victim state if available
    victim_state = detection.victim_state or {}
    
    return {
        "victim_id": detection.detection_id,
        "position": detection.position,
        "injury_severity": injury_severity,
        "detected_by": detection.drone_id if is_confirmed else "none",
        "first_detected_tick": current_tick if is_confirmed else 0,
        "detection_confidence": detection_confidence,
        "assigned_drone": None,
        "mission_id": None,
        "cooldown_until_tick": 0,
        "conscious": victim_state.get("conscious", True),
        "bleeding": victim_state.get("bleeding", "none"),
        "body_temperature_c": victim_state.get("body_temperature_c", 37.0),
        "accessibility": victim_state.get("accessibility", 0.5)
    }


def create_mission_command(drone_id: str, 
                          command_type: MissionCommandType,
                          mission_id: Optional[str] = None,
                          **kwargs) -> AirSimMissionCommand:
    """
    Create a mission command for sending to AirSim.
    
    Args:
        drone_id: Target drone ID
        command_type: Type of command
        mission_id: Associated mission ID
        **kwargs: Additional command parameters
        
    Returns:
        Configured mission command
    """
    import time
    
    return AirSimMissionCommand(
        command_id=f"cmd_{int(time.time() * 1000)}_{drone_id}",
        timestamp=time.time(),
        drone_id=drone_id,
        command_type=command_type,
        mission_id=mission_id,
        **kwargs
    )


# Validation functions

def validate_telemetry(telemetry: AirSimTelemetry) -> bool:
    """Validate AirSim telemetry data."""
    if not telemetry.drone_id:
        return False
    
    if not telemetry.position or len(telemetry.position) != 3:
        return False
    
    # Check for NaN or infinite values
    for coord in telemetry.position:
        if not isinstance(coord, (int, float)):
            return False
    
    return True


def validate_detection(detection: AirSimDetection) -> bool:
    """Validate AirSim detection data."""
    if not detection.detection_id:
        return False
    
    if not detection.position or len(detection.position) != 3:
        return False
    
    if not 0.0 <= detection.confidence <= 1.0:
        return False
    
    return True