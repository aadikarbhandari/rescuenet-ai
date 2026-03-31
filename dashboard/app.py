"""
Streamlit dashboard for RescueNet MVP.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from typing import Dict, Any, List

# Import existing backend modules
from simulation.mock_env import MockDisasterEnv
from state.fleet_state import FleetState
from agents.state_awareness import StateAwarenessAgent
from agents.coordinator import CoordinatorAgent
from agents.triage import TriageAgent, TriageVictim

# Initialize the environment and agents once per session
@st.cache_resource
def init_system():
    """Create mock environment, fleet state, and agents."""
    env = MockDisasterEnv(seed=42)
    fleet = FleetState()
    state_agent = StateAwarenessAgent(fleet)
    coordinator = CoordinatorAgent(fleet)
    triage = TriageAgent()
    
    # Ingest one snapshot of data
    drone_snapshots = env.get_drone_snapshots()
    victim_snapshots = env.get_victim_snapshots()
    
    # Update fleet state with drone data
    for d in drone_snapshots:
        from state.fleet_state import DroneState
        ds = DroneState(
            drone_id=d['drone_id'],
            battery_percent=d.get('battery_percent', d.get('battery', 100.0)),
            mechanical_health=d.get('mechanical_health', 'ok'),
            sensor_status=d.get('sensor_status', {}),
            payload_kg=d.get('payload_kg', 0.0),
            winch_status=d.get('winch_status', 'ready'),
            position=d.get('position', (0.0, 0.0, 0.0)),
            wind_speed_ms=d.get('wind_speed_ms', 0.0),
            temperature_c=d.get('temperature_c', 20.0),
            visibility_m=d.get('visibility_m', 1000.0),
            current_mission=d.get('current_mission', None)
        )
        fleet.add_or_update_drone(ds)
    
    # Update fleet state with victim data
    for v in victim_snapshots:
        from state.fleet_state import VictimState
        vs = VictimState(
            victim_id=v['victim_id'],
            position=v.get('position', (0.0, 0.0, 0.0)),
            injury_severity=v.get('injury_severity', 'unknown'),
            detected_by=v.get('detected_by', 'none'),
            assigned_drone=v.get('assigned_drone', None),
            mission_id=v.get('mission_id', None),
            cooldown_until_tick=v.get('cooldown_until_tick', 0)
        )
        fleet.add_or_update_victim(vs)
    
    # Let state awareness agent process raw data
    state_agent.ingest_raw_drone_data(drone_snapshots)
    
    return env, fleet, state_agent, coordinator, triage

def main():
    st.set_page_config(page_title="RescueNet MVP Dashboard", layout="wide")
    st.title("🚁 RescueNet MVP Dashboard")
    st.markdown("Real-time overview of drones, victims, missions, and fleet readiness.")
    
    env, fleet, state_agent, coordinator, triage = init_system()
    
    # Get fresh victim snapshots for accurate triage data
    victim_snapshots = env.get_victim_snapshots()
    victim_data_by_id = {v['victim_id']: v for v in victim_snapshots}
    
    # 1. Fleet readiness summary
    st.header("📊 Fleet Readiness Summary")
    readiness = state_agent.compute_fleet_readiness_summary()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Drones", readiness.get("total_drones", 0))
    col2.metric("Available Drones", readiness.get("available_drones", 0))
    col3.metric("Avg Battery", f"{readiness.get('avg_battery', 0):.1f}%")
    col4.metric("Operational %", f"{readiness.get('operational_percent', 0):.1f}%")
    
    # 2. Drone table
    st.header("🛸 Drones")
    drone_rows = []
    for drone_id, drone in fleet.drones.items():
        # Determine availability status
        availability = state_agent.mark_availability()
        is_available = availability.get(drone_id, False)
        
        # Get mission status
        mission_status = "Available"
        if drone.current_mission:
            # Find the mission assignment
            mission = next((m for m in fleet.assignments.values() if m.mission_id == drone.current_mission), None)
            if mission:
                mission_status = f"On mission: {mission.status}"
            else:
                mission_status = f"On mission: {drone.current_mission}"
        elif not is_available:
            # Determine why unavailable
            reasons = []
            if drone.battery_percent < 10.0:
                reasons.append("Low battery")
            if drone.mechanical_health == "critical":
                reasons.append("Critical health")
            if not state_agent._essential_sensors_ok(drone.sensor_status):
                reasons.append("Sensor fault")
            mission_status = f"Unavailable: {', '.join(reasons)}" if reasons else "Unavailable"
        
        # Format battery with color indication
        battery_color = "🟢" if drone.battery_percent > 50 else "🟡" if drone.battery_percent > 20 else "🔴"
        battery_display = f"{battery_color} {drone.battery_percent:.1f}%"
        
        # Format health status
        health_icon = "🟢" if drone.mechanical_health == "ok" else "🟡" if drone.mechanical_health == "degraded" else "🔴"
        
        drone_rows.append({
            "ID": drone.drone_id,
            "Position": f"({drone.position[0]:.1f}, {drone.position[1]:.1f})" if drone.position and len(drone.position) > 1 else "(0.0, 0.0)",
            "Battery": battery_display,
            "Health": f"{health_icon} {drone.mechanical_health}",
            "Mission Status": mission_status,
            "Sensors": ", ".join([f"{k}:{v}" for k, v in drone.sensor_status.items()]) if drone.sensor_status else "none"
        })
    if drone_rows:
        st.dataframe(pd.DataFrame(drone_rows), use_container_width=True)
    else:
        st.info("No drone data available.")
    
    # 3. Victim table (with triage priorities if available)
    st.header("🩸 Victims")
    victim_rows = []
    for victim_id, victim in fleet.victims.items():
        # Get actual victim data from environment for accurate triage
        raw_victim = victim_data_by_id.get(victim_id, {})
        
        # Compute triage priority using actual data if available, otherwise defaults
        triage_obj = TriageVictim(
            victim_id=victim.victim_id,
            severity=victim.injury_severity,  # map injury_severity to severity
            conscious=raw_victim.get('conscious', True),  # use actual data
            bleeding=raw_victim.get('bleeding', 'none'),  # use actual data
            body_temperature_c=raw_victim.get('body_temperature_c', 37.0),  # use actual data
            accessibility=raw_victim.get('accessibility', 0.5),  # use actual data
            position=victim.position
        )
        priority_score, priority_label = triage.compute_priority(triage_obj)
        
        # Add cooldown status if applicable
        cooldown_status = ""
        if victim.cooldown_until_tick > 0:
            cooldown_status = f"Cooldown until tick {victim.cooldown_until_tick}"
        
        victim_rows.append({
            "ID": victim.victim_id,
            "X": victim.position[0] if victim.position and len(victim.position) > 0 else 0.0,
            "Y": victim.position[1] if victim.position and len(victim.position) > 1 else 0.0,
            "Severity": victim.injury_severity,
            "Found By": victim.detected_by or "—",
            "Assigned To": victim.assigned_drone or "—",
            "Priority Score": f"{priority_score:.2f}",
            "Cooldown": cooldown_status
        })
    if victim_rows:
        st.dataframe(pd.DataFrame(victim_rows), use_container_width=True)
    else:
        st.info("No victim data available.")
    
    # 4. Active missions
    st.header("📋 Active Missions")
    mission_rows = []
    for mission_id, assignment in fleet.assignments.items():
        if assignment.status in ("pending", "active"):  # Show pending and active missions
            mission_rows.append({
                "Mission ID": mission_id,
                "Drone ID": assignment.drone_id,
                "Victim ID": assignment.victim_id or "—",
                "Task Type": assignment.task_type,
                "Estimated Duration": f"{assignment.estimated_duration_min:.1f} min",
                "Status": assignment.status
            })
    if mission_rows:
        st.dataframe(pd.DataFrame(mission_rows), use_container_width=True)
    else:
        st.info("No active missions.")
    
    # 5. Triage priorities (as a separate section)
    st.header("🚨 Triage Priorities")
    if fleet.victims:
        # Use the triage agent's prioritization method with actual data
        triage_victims = []
        for victim in fleet.victims.values():
            raw_victim = victim_data_by_id.get(victim.victim_id, {})
            triage_victims.append(TriageVictim(
                victim_id=victim.victim_id,
                severity=victim.injury_severity,  # map injury_severity to severity
                conscious=raw_victim.get('conscious', True),  # use actual data
                bleeding=raw_victim.get('bleeding', 'none'),  # use actual data
                body_temperature_c=raw_victim.get('body_temperature_c', 37.0),  # use actual data
                accessibility=raw_victim.get('accessibility', 0.5),  # use actual data
                position=victim.position
            ))
        prioritized = triage.prioritize_victims(triage_victims)
        if prioritized:
            st.subheader("Sorted by priority (highest first)")
            for idx, (victim_obj, score, label) in enumerate(prioritized[:10], 1):
                # Show cooldown status if applicable
                victim_state = fleet.victims.get(victim_obj.victim_id)
                cooldown_info = ""
                if victim_state and victim_state.cooldown_until_tick > 0:
                    cooldown_info = f" ⏳ (cooldown until tick {victim_state.cooldown_until_tick})"
                st.write(f"{idx}. **{victim_obj.victim_id}** – {label} (score: {score:.2f}) – "
                         f"Severity: {victim_obj.severity}{cooldown_info}")
        else:
            st.info("Could not compute triage priorities.")
    else:
        st.info("No victims to triage.")
    
    # Sidebar with refresh and info
    st.sidebar.title("Controls")
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_resource.clear()
        st.rerun()
    st.sidebar.info("Data is from a single simulation snapshot. Refresh to re‑initialize.")

if __name__ == "__main__":
    main()
