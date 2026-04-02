from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import threading
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

app = FastAPI(title="RescueNet AI API")

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
_state: Dict[str, Any] = {
    "mode": "idle",
    "tick": 0,
    "drones": [],
    "victims": [],
    "missions": [],
    "stations": [],
    "security_alerts": [],
    "decisions": [],
    "active_missions": 0,
    "drones_available": 0,
    "total_victims_rescued": 0,
    "total_victims_lost": 0,
    "system_start_time": datetime.now().isoformat(),
}


def update_state(new_state: dict) -> None:
    """Update the global _state dict with new data from simulation tick."""
    global _state
    _state.update(new_state)


@app.get("/health")
def health() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "tick": _state.get("tick", 0),
        "mode": _state.get("mode", "idle"),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/status")
def get_status() -> Dict[str, Any]:
    """Overall system status."""
    drones = _state.get("drones", [])
    missions = _state.get("missions", [])
    
    return {
        "mode": _state.get("mode", "idle"),
        "tick": _state.get("tick", 0),
        "drones_available": _state.get("drones_available", sum(1 for d in drones if d.get("status") == "available")),
        "drones_total": len(drones),
        "active_missions": _state.get("active_missions", sum(1 for m in missions if m.get("status") == "active")),
        "total_missions": len(missions),
        "total_victims": len(_state.get("victims", [])),
        "victims_rescued": _state.get("total_victims_rescued", 0),
        "victims_lost": _state.get("total_victims_lost", 0),
        "security_alerts_count": len(_state.get("security_alerts", [])),
        "uptime_start": _state.get("system_start_time", ""),
    }


@app.get("/drones")
def get_drones() -> List[Dict[str, Any]]:
    """List of all drone states."""
    return _state.get("drones", [])


@app.get("/drones/{drone_id}")
def get_drone(drone_id: str) -> Dict[str, Any]:
    """Get single drone state by ID."""
    drones = _state.get("drones", [])
    for drone in drones:
        if drone.get("id") == drone_id:
            return drone
    raise HTTPException(status_code=404, detail=f"Drone {drone_id} not found")


@app.get("/victims")
def get_victims() -> List[Dict[str, Any]]:
    """All detected victims with triage scores."""
    victims = _state.get("victims", [])
    # Sort by triage score (priority) descending
    return sorted(victims, key=lambda v: v.get("triage_score", 0), reverse=True)


@app.get("/victims/critical")
def get_critical_victims() -> List[Dict[str, Any]]:
    """Get only critical priority victims."""
    return [v for v in _state.get("victims", []) if v.get("triage_priority") == "critical"]


@app.get("/missions")
def get_missions() -> List[Dict[str, Any]]:
    """All missions."""
    return _state.get("missions", [])


@app.get("/missions/active")
def get_active_missions() -> List[Dict[str, Any]]:
    """Only active missions."""
    return [m for m in _state.get("missions", []) if m.get("status") == "active"]


@app.get("/stations")
def get_stations() -> List[Dict[str, Any]]:
    """Rescue station status."""
    return _state.get("stations", [])


@app.get("/security/alerts")
def get_security_alerts() -> List[Dict[str, Any]]:
    """Recent security alerts."""
    alerts = _state.get("security_alerts", [])
    # Return last 20 alerts sorted by timestamp descending
    return sorted(alerts, key=lambda a: a.get("timestamp", ""), reverse=True)[:20]


@app.get("/decisions")
def get_decisions() -> List[Dict[str, Any]]:
    """Last 10 coordinator decisions."""
    decisions = _state.get("decisions", [])
    return decisions[-10:] if len(decisions) > 10 else decisions


@app.get("/decisions/recent")
def get_recent_decisions(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent coordinator decisions with configurable limit."""
    decisions = _state.get("decisions", [])
    return decisions[-limit:] if len(decisions) > limit else decisions


@app.get("/analytics/summary")
def get_analytics_summary() -> Dict[str, Any]:
    """Analytics summary for the rescue operation."""
    drones = _state.get("drones", [])
    missions = _state.get("missions", [])
    victims = _state.get("victims", [])
    
    drone_stats: Dict[str, int] = {
        "total": len(drones),
        "available": sum(1 for d in drones if d.get("status") == "available"),
        "en_route": sum(1 for d in drones if d.get("status") == "en_route"),
        "on_mission": sum(1 for d in drones if d.get("status") == "on_mission"),
        "returning": sum(1 for d in drones if d.get("status") == "returning"),
        "charging": sum(1 for d in drones if d.get("status") == "charging"),
    }
    
    mission_stats: Dict[str, int] = {
        "total": len(missions),
        "active": sum(1 for m in missions if m.get("status") == "active"),
        "completed": sum(1 for m in missions if m.get("status") == "completed"),
        "failed": sum(1 for m in missions if m.get("status") == "failed"),
    }
    
    victim_stats: Dict[str, Any] = {
        "total_detected": len(victims),
        "critical": sum(1 for v in victims if v.get("triage_priority") == "critical"),
        "serious": sum(1 for v in victims if v.get("triage_priority") == "serious"),
        "moderate": sum(1 for v in victims if v.get("triage_priority") == "moderate"),
        "minor": sum(1 for v in victims if v.get("triage_priority") == "minor"),
        "rescued": _state.get("total_victims_rescued", 0),
        "lost": _state.get("total_victims_lost", 0),
    }
    
    return {
        "tick": _state.get("tick", 0),
        "mode": _state.get("mode", "idle"),
        "drone_stats": drone_stats,
        "mission_stats": mission_stats,
        "victim_stats": victim_stats,
    }


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the FastAPI server synchronously."""
    uvicorn.run(app, host=host, port=port, log_level="error")


def run_server_background(host: str = "0.0.0.0", port: int = 8000) -> threading.Thread:
    """Run the FastAPI server in a background thread."""
    t = threading.Thread(target=run_server, args=(host, port), daemon=True)
    t.start()
    print(f"[API] RescueNet AI Server running at http://{host}:{port}")
    return t


def get_state() -> Dict[str, Any]:
    """Get current global state (for external simulation access)."""
    return _state.copy()


if __name__ == "__main__":
    run_server_background()
    # Keep main thread alive for background server
    while True:
        time.sleep(1)