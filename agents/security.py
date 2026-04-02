import logging
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from config.settings import Settings
import math

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    NONE = "none"
    GPS_SPOOFING = "gps_spoofing"
    SIGNAL_JAMMING = "signal_jamming"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    POSITION_JUMP = "position_jump"
    SIGNAL_LOSS = "signal_loss"


@dataclass
class SecurityAlert:
    alert_id: str
    drone_id: str
    alert_type: AlertType
    severity: AlertSeverity
    timestamp: float
    details: Dict[str, Any]
    position: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "drone_id": self.drone_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "details": self.details,
            "position": self.position
        }


class SecurityAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.position_history: Dict[str, List[Dict[str, Any]]] = {}
        self.alerts: List[SecurityAlert] = []
        self.alert_counter = 0
        self.max_history_size = settings.security.get("max_position_history", 100) if hasattr(settings, 'security') else 100
        self.gps_jump_threshold = settings.security.get("gps_jump_threshold_mps", 100) if hasattr(settings, 'security') else 100
        self.altitude_jump_threshold = settings.security.get("altitude_jump_threshold_m", 50) if hasattr(settings, 'security') else 50
        self.min_signal_strength = settings.security.get("min_signal_strength", 20) if hasattr(settings, 'security') else 20
        self.required_telemetry_fields = [
            "drone_id", "latitude", "longitude", "altitude", 
            "timestamp", "signal_strength", "battery_level"
        ]
        self._alert_id_lock = 0
        self.logger.info("SecurityAgent initialized with GPS spoofing, signal jamming, and behavior monitoring")

    def _generate_alert_id(self) -> str:
        self._alert_id_lock += 1
        return f"sec_{int(time.time() * 1000)}_{self._alert_id_lock}"

    def _store_position(self, drone_id: str, position: dict, timestamp: float) -> None:
        if drone_id not in self.position_history:
            self.position_history[drone_id] = []
        
        position_entry = {
            "latitude": position.get("latitude"),
            "longitude": position.get("longitude"),
            "altitude": position.get("altitude"),
            "timestamp": timestamp
        }
        self.position_history[drone_id].append(position_entry)
        
        if len(self.position_history[drone_id]) > self.max_history_size:
            self.position_history[drone_id] = self.position_history[drone_id][-self.max_history_size:]

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    def check_gps_spoofing(self, drone_id: str, position: dict) -> dict:
        current_time = time.time()
        current_lat = position.get("latitude")
        current_lon = position.get("longitude")
        current_alt = position.get("altitude")
        
        if current_lat is None or current_lon is None:
            return {
                "alert": False,
                "alert_data": None,
                "reason": "Incomplete position data"
            }
        
        self._store_position(drone_id, position, current_time)
        
        history = self.position_history.get(drone_id, [])
        
        if len(history) < 2:
            return {
                "alert": False,
                "alert_data": None,
                "reason": "Insufficient position history for velocity calculation"
            }
        
        last_pos = history[-2]
        current_pos = history[-1]
        
        time_delta = current_pos["timestamp"] - last_pos["timestamp"]
        
        if time_delta <= 0:
            return {
                "alert": False,
                "alert_data": None,
                "reason": "Invalid timestamp delta"
            }
        
        distance = self._calculate_distance(
            last_pos["latitude"], last_pos["longitude"],
            current_pos["latitude"], current_pos["longitude"]
        )
        
        velocity = distance / time_delta
        
        alert_detected = False
        alert_details = {}
        
        if velocity > self.gps_jump_threshold:
            alert_detected = True
            alert_details["velocity_mps"] = round(velocity, 2)
            alert_details["threshold_mps"] = self.gps_jump_threshold
            alert_details["distance_m"] = round(distance, 2)
            alert_details["time_delta_s"] = round(time_delta, 3)
            alert_details["type"] = "impossible_velocity"
            self.logger.warning(
                f"GPS spoofing detected for drone {drone_id}: "
                f"velocity {velocity:.2f} m/s exceeds threshold {self.gps_jump_threshold} m/s"
            )
        
        altitude_change = abs(current_alt - last_pos.get("altitude", 0)) if current_alt is not None and last_pos.get("altitude") is not None else 0
        if altitude_change > self.altitude_jump_threshold:
            alert_detected = True
            alert_details["altitude_change_m"] = round(altitude_change, 2)
            alert_details["altitude_threshold_m"] = self.altitude_jump_threshold
            self.logger.warning(
                f"Altitude anomaly for drone {drone_id}: "
                f"change {altitude_change:.2f}m exceeds threshold {self.altitude_jump_threshold}m"
            )
        
        if alert_detected:
            alert = SecurityAlert(
                alert_id=self._generate_alert_id(),
                drone_id=drone_id,
                alert_type=AlertType.GPS_SPOOFING,
                severity=AlertSeverity.HIGH,
                timestamp=current_time,
                details=alert_details,
                position={"latitude": current_lat, "longitude": current_lon, "altitude": current_alt}
            )
            self.alerts.append(alert)
            
            return {
                "alert": True,
                "alert_data": alert.to_dict()
            }
        
        return {
            "alert": False,
            "alert_data": None
        }

    def check_signal_integrity(self, drone_id: str, telemetry: dict) -> dict:
        current_time = time.time()
        missing_fields = []
        weak_signal = False
        
        for field in self.required_telemetry_fields:
            if field not in telemetry or telemetry[field] is None:
                missing_fields.append(field)
        
        signal_strength = telemetry.get("signal_strength")
        if signal_strength is not None and signal_strength < self.min_signal_strength:
            weak_signal = True
        
        alert_detected = False
        alert_details = {}
        
        if missing_fields:
            alert_detected = True
            alert_details["missing_fields"] = missing_fields
            alert_details["type"] = "missing_telemetry"
            self.logger.warning(
                f"Signal jamming detected for drone {drone_id}: "
                f"missing fields {missing_fields}"
            )
        
        if weak_signal:
            alert_detected = True
            alert_details["signal_strength"] = signal_strength
            alert_details["threshold"] = self.min_signal_strength
            alert_details["type"] = "weak_signal"
            self.logger.warning(
                f"Weak signal detected for drone {drone_id}: "
                f"strength {signal_strength} below threshold {self.min_signal_strength}"
            )
        
        if alert_detected:
            severity = AlertSeverity.HIGH if missing_fields else AlertSeverity.MEDIUM
            
            alert = SecurityAlert(
                alert_id=self._generate_alert_id(),
                drone_id=drone_id,
                alert_type=AlertType.SIGNAL_JAMMING,
                severity=severity,
                timestamp=current_time,
                details=alert_details,
                position={
                    "latitude": telemetry.get("latitude"),
                    "longitude": telemetry.get("longitude"),
                    "altitude": telemetry.get("altitude")
                }
            )
            self.alerts.append(alert)
            
            return {
                "alert": True,
                "alert_data": alert.to_dict(),
                "missing_fields": missing_fields,
                "weak_signal": weak_signal
            }
        
        return {
            "alert": False,
            "alert_data": None
        }

    def check_anomalous_behavior(self, drone_id: str, telemetry: dict) -> dict:
        current_time = time.time()
        anomalies = []
        
        battery = telemetry.get("battery_level")
        if battery is not None and battery < 10:
            anomalies.append(f"Critical battery: {battery}%")
        
        speed = telemetry.get("speed")
        if speed is not None:
            if speed > 50:
                anomalies.append(f"Excessive speed: {speed} m/s")
            elif speed < 0:
                anomalies.append(f"Invalid speed: {speed} m/s")
        
        heading = telemetry.get("heading")
        if heading is not None:
            if heading < 0 or heading > 360:
                anomalies.append(f"Invalid heading: {heading}")
        
        history = self.position_history.get(drone_id, [])
        if len(history) >= 10:
            recent_lats = [h["latitude"] for h in history[-10:] if h.get("latitude")]
            if recent_lats and len(set(recent_lats)) == 1:
                anomalies.append("Stationary for extended period (possible hijack)")
        
        if anomalies:
            alert = SecurityAlert(
                alert_id=self._generate_alert_id(),
                drone_id=drone_id,
                alert_type=AlertType.ANOMALOUS_BEHAVIOR,
                severity=AlertSeverity.MEDIUM,
                timestamp=current_time,
                details={"anomalies": anomalies},
                position={
                    "latitude": telemetry.get("latitude"),
                    "longitude": telemetry.get("longitude"),
                    "altitude": telemetry.get("altitude")
                }
            )
            self.alerts.append(alert)
            
            return {
                "alert": True,
                "alert_data": alert.to_dict()
            }
        
        return {
            "alert": False,
            "alert_data": None
        }

    def scan_all(self, telemetry_list: list) -> list:
        active_alerts = []
        
        for telemetry in telemetry_list:
            drone_id = telemetry.get("drone_id", "unknown")
            
            position = {
                "latitude": telemetry.get("latitude"),
                "longitude": telemetry.get("longitude"),
                "altitude": telemetry.get("altitude")
            }
            
            gps_result = self.check_gps_spoofing(drone_id, position)
            if gps_result.get("alert"):
                active_alerts.append(gps_result["alert_data"])
            
            signal_result = self.check_signal_integrity(drone_id, telemetry)
            if signal_result.get("alert"):
                active_alerts.append(signal_result["alert_data"])
            
            behavior_result = self.check_anomalous_behavior(drone_id, telemetry)
            if behavior_result.get("alert"):
                active_alerts.append(behavior_result["alert_data"])
        
        self.logger.info(f"Security scan complete: {len(active_alerts)} alerts from {len(telemetry_list)} drones")
        return active_alerts

    def get_alert_summary(self) -> dict:
        recent_alerts = sorted(self.alerts, key=lambda x: x.timestamp, reverse=True)[:5]
        
        return {
            "total_alerts": len(self.alerts),
            "recent_alerts": [a.to_dict() for a in recent_alerts]
        }

    def clear_old_alerts(self, max_age_seconds: int = 3600) -> int:
        current_time = time.time()
        original_count = len(self.alerts)
        self.alerts = [a for a in self.alerts if current_time - a.timestamp < max_age_seconds]
        cleared = original_count - len(self.alerts)
        
        if cleared > 0:
            self.logger.info(f"Cleared {cleared} alerts older than {max_age_seconds}s")
        
        return cleared

    def get_drone_security_status(self, drone_id: str) -> dict:
        drone_alerts = [a for a in self.alerts if a.drone_id == drone_id]
        history = self.position_history.get(drone_id, [])
        
        return {
            "drone_id": drone_id,
            "alert_count": len(drone_alerts),
            "has_active_alerts": any(a.timestamp > time.time() - 300 for a in drone_alerts),
            "position_history_size": len(history),
            "last_position": history[-1] if history else None
        }


def check_for_spoofing(telemetry: dict) -> dict:
    """
    Check telemetry data for spoofing anomalies.
    
    Analyzes GPS jumps, signal strength, and altitude changes to detect
    potential GPS spoofing or signal interference attacks.
    
    Args:
        telemetry: Dictionary containing drone telemetry with keys like
                   'drone_id', 'latitude', 'longitude', 'altitude',
                   'signal_strength', and optionally 'prev_latitude',
                   'prev_longitude', 'prev_altitude' for delta calculations.
    
    Returns:
        Dictionary with alert status and details:
        {alert: bool, type: str, severity: str, details: str}
    """
    result = {
        'alert': False,
        'type': 'none',
        'severity': 'none',
        'details': 'No anomalies detected'
    }
    
    drone_id = telemetry.get('drone_id', 'unknown')
    
    gps_jump_detected = False
    gps_jump_distance = 0.0
    
    if ('latitude' in telemetry and 'longitude' in telemetry and
        'prev_latitude' in telemetry and 'prev_longitude' in telemetry):
        
        current_lat = telemetry.get('latitude', 0)
        current_lon = telemetry.get('longitude', 0)
        prev_lat = telemetry.get('prev_latitude', 0)
        prev_lon = telemetry.get('prev_longitude', 0)
        
        lat_diff = abs(current_lat - prev_lat)
        lon_diff = abs(current_lon - prev_lon)
        
        avg_lat = (current_lat + prev_lat) / 2
        lon_scale = abs(111320 * (1 - 0.142 * (avg_lat / 90) ** 2))
        
        gps_jump_distance = ((lat_diff * 111000) ** 2 + 
                            (lon_diff * lon_scale) ** 2) ** 0.5
        
        if gps_jump_distance > 100:
            gps_jump_detected = True
    
    signal_strength = telemetry.get('signal_strength', 100)
    low_signal_detected = signal_strength < 20
    
    altitude_change_detected = False
    altitude_change = 0.0
    
    if 'altitude' in telemetry and 'prev_altitude' in telemetry:
        altitude_change = abs(telemetry.get('altitude', 0) - telemetry.get('prev_altitude', 0))
        if altitude_change > 50:
            altitude_change_detected = True
    
    anomalies = []
    severity = 'none'
    
    if gps_jump_detected:
        anomalies.append(f"GPS jump: {gps_jump_distance:.1f}m")
        severity = 'high'
    
    if low_signal_detected:
        anomalies.append(f"Low signal: {signal_strength}")
        if severity == 'none':
            severity = 'medium'
    
    if altitude_change_detected:
        anomalies.append(f"Altitude jump: {altitude_change:.1f}m")
        if severity == 'none':
            severity = 'high'
        elif severity == 'medium':
            severity = 'high'
    
    if anomalies:
        result['alert'] = True
        result['type'] = 'spoofing'
        result['severity'] = severity
        result['details'] = f"Drone {drone_id}: {'; '.join(anomalies)}"
        logger.warning(f"Spoofing detection alert for drone {drone_id}: {result['details']}")
    
    return result


def get_security_alerts(fleet_state: dict) -> list:
    """
    Run spoofing detection checks on all drones in the fleet.
    
    Args:
        fleet_state: Dictionary containing fleet information with a 'drones'
                     key containing a list of drone telemetry dictionaries.
    
    Returns:
        List of active alert dictionaries from check_for_spoofing.
    """
    alerts = []
    
    drones = fleet_state.get('drones', [])
    
    for drone in drones:
        alert = check_for_spoofing(drone)
        if alert['alert']:
            alerts.append(alert)
    
    logger.info(f"Security scan complete: {len(alerts)} alerts found across {len(drones)} drones")
    
    return alerts


def log_security_event(event_type: str, details: dict) -> None:
    """
    Log a security event for audit purposes.
    
    Args:
        event_type: Type of security event (e.g., 'spoofing_detected', 'encryption_error')
        details: Dictionary containing event details
    """
    logger.info(f"Security event [{event_type}]: {details}")