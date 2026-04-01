"""
Encryption, spoofing detection, audit logging
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


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
    
    # Calculate GPS distance if previous position available
    gps_jump_detected = False
    gps_jump_distance = 0.0
    
    if ('latitude' in telemetry and 'longitude' in telemetry and
        'prev_latitude' in telemetry and 'prev_longitude' in telemetry):
        
        current_lat = telemetry.get('latitude', 0)
        current_lon = telemetry.get('longitude', 0)
        prev_lat = telemetry.get('prev_latitude', 0)
        prev_lon = telemetry.get('prev_longitude', 0)
        
        # Simple Euclidean approximation (suitable for small distances)
        # 1 degree latitude ≈ 111km, 1 degree longitude ≈ 111km * cos(lat)
        lat_diff = abs(current_lat - prev_lat)
        lon_diff = abs(current_lon - prev_lon)
        
        # Average latitude for longitude scaling
        avg_lat = (current_lat + prev_lat) / 2
        lon_scale = abs(111320 * (1 - 0.142 * (avg_lat / 90) ** 2))  # Approximate
        
        gps_jump_distance = ((lat_diff * 111000) ** 2 + 
                            (lon_diff * lon_scale) ** 2) ** 0.5
        
        if gps_jump_distance > 100:
            gps_jump_detected = True
    
    # Check signal strength
    signal_strength = telemetry.get('signal_strength', 100)
    low_signal_detected = signal_strength < 20
    
    # Calculate altitude change if previous altitude available
    altitude_change_detected = False
    altitude_change = 0.0
    
    if 'altitude' in telemetry and 'prev_altitude' in telemetry:
        altitude_change = abs(telemetry.get('altitude', 0) - telemetry.get('prev_altitude', 0))
        if altitude_change > 50:
            altitude_change_detected = True
    
    # Determine alert level and details
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