"""
Streamlit dashboard for RescueNet MVP.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from typing import Dict, Any, List

# Import existing backend modules
from simulation.mock_env import MockDisasterEnv
from state.fleet_state import FleetState, DroneState, VictimState
from agents.state_awareness import StateAwarenessAgent
from agents.coordinator import CoordinatorAgent
from agents.triage import TriageAgent, TriageVictim

# Initialize the environment and agents in session state
def init_system():
    """Create mock environment, fleet state, and agents."""
    if 'env' not in st.session_state:
        st.session_state.env = MockDisasterEnv(seed=42)
        st.session_state.fleet = FleetState()
        st.session_state.state_agent = StateAwarenessAgent(st.session_state.fleet)
        st.session_state.coordinator = CoordinatorAgent(st.session_state.fleet)
        st.session_state.triage = TriageAgent()
        st.session_state.simulation_running = False
        st.session_state.last_update_time = time.time()
        st.session_state.auto_refresh = False
        st.session_state.refresh_interval = 2.0  # seconds
        
        # Initial data ingestion
        update_fleet_from_env()
        
        print(f"[Dashboard] System initialized at tick {st.session_state.env.tick}")
    
    # Always return the 5 expected values
    return (
        st.session_state.env,
        st.session_state.fleet,
        st.session_state.state_agent,
        st.session_state.coordinator,
        st.session_state.triage
    )

def update_fleet_from_env():
    """Update fleet state with latest data from environment."""
    env = st.session_state.env
    fleet = st.session_state.fleet
    state_agent = st.session_state.state_agent
    
    # Get latest snapshots
    drone_snapshots = env.get_drone_snapshots()
    victim_snapshots = env.get_victim_snapshots()
    
    # Update fleet state with drone data
    for d in drone_snapshots:
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
            current_mission=d.get('current_mission', None),
            operational_status=d.get('operational_status', 'available')
        )
        fleet.add_or_update_drone(ds)
    
    # Update fleet state with victim data
    for v in victim_snapshots:
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
    
    # Check for completed missions and update FleetState
    completed_missions = env.get_completed_missions()
    for mission_id in completed_missions:
        if fleet.complete_assignment(mission_id):
            print(f"[Dashboard] Mission {mission_id} marked as completed in FleetState")
    
    # Create new mission assignments if needed
    create_new_assignments()
    
    st.session_state.last_update_time = time.time()

def create_new_assignments():
    """Create new mission assignments based on current state."""
    env = st.session_state.env
    fleet = st.session_state.fleet
    coordinator = st.session_state.coordinator
    
    # Get current victim states
    victim_objs = list(fleet.victims.values())
    
    # Filter out victims in cooldown
    available_victims = [v for v in victim_objs if v.cooldown_until_tick <= env.tick and v.assigned_drone is None]
    
    if available_victims:
        assignments = coordinator.assign_missions(available_victims, env.tick)
        for assignment in assignments:
            if assignment.victim_id:
                env.update_victim_assignment(assignment.victim_id, assignment.drone_id, assignment.mission_id)
            env.update_drone_mission(assignment.drone_id, assignment.mission_id)
            print(f"[Dashboard] Created new assignment: {assignment.mission_id}")

def main():
    st.set_page_config(page_title="RescueNet MVP Dashboard", layout="wide")
    st.title("🚁 RescueNet MVP Dashboard")
    st.markdown("Real-time overview of drones, victims, missions, and fleet readiness.")
    
    env, fleet, state_agent, coordinator, triage = init_system()
    
    # Simulation controls in sidebar
    with st.sidebar:
        st.header("Simulation Controls")
        
        # Auto-refresh toggle
        auto_refresh = st.toggle("Auto-refresh", value=st.session_state.auto_refresh, 
                                help="Continuously update dashboard with simulation state")
        if auto_refresh != st.session_state.auto_refresh:
            st.session_state.auto_refresh = auto_refresh
        
        # Refresh interval slider
        refresh_interval = st.slider("Refresh interval (seconds)", min_value=2, max_value=10, 
                                    value=int(st.session_state.refresh_interval),
                                    help="How often to update when auto-refresh is enabled")
        if refresh_interval != st.session_state.refresh_interval:
            st.session_state.refresh_interval = float(refresh_interval)
        
        # Manual controls
        col1, col2 = st.columns(2)
        with col1:
            step_clicked = st.button("Step Simulation", help="Advance simulation by one tick")
        with col2:
            reset_clicked = st.button("Reset Simulation", help="Reset simulation to initial state")
        
        # Status display
        st.divider()
        st.subheader("Simulation Status")
        st.write(f"**Current tick:** {env.tick}")
        st.write(f"**Last update:** {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_update_time))}")
        
        if st.session_state.auto_refresh:
            st.success("🔄 Auto-refresh enabled")
        else:
            st.info("⏸️ Auto-refresh paused")
    
    # Handle simulation controls
    if step_clicked:
        env.step()
        update_fleet_from_env()
        st.rerun()
    
    if reset_clicked:
        # Reset environment
        st.session_state.env = MockDisasterEnv(seed=42)
        st.session_state.fleet = FleetState()
        st.session_state.state_agent = StateAwarenessAgent(st.session_state.fleet)
        st.session_state.coordinator = CoordinatorAgent(st.session_state.fleet)
        st.session_state.triage = TriageAgent()
        st.session_state.simulation_running = False
        st.session_state.last_update_time = time.time()
        
        # Re-initialize
        env, fleet, state_agent, coordinator, triage = init_system()
        st.rerun()
    
    # Auto-refresh logic
    if st.session_state.auto_refresh:
        current_time = time.time()
        if current_time - st.session_state.last_update_time >= st.session_state.refresh_interval:
            env.step()
            update_fleet_from_env()
            st.rerun()
    
    # Always update fleet state before rendering to ensure we have latest data
    update_fleet_from_env()

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
    
    # Get availability status once
    availability = state_agent.mark_availability() if hasattr(state_agent, 'mark_availability') else {}
    
    for drone_id, drone in fleet.drones.items():
        # Determine availability status
        is_available = availability.get(drone_id, False)
        
        # Get mission/operational status
        mission_status = drone.operational_status.replace("_", " ").title()
        
        # Add more descriptive status based on operational state
        if drone.operational_status == "on_mission" and drone.current_mission:
            # Find the mission assignment
            mission = None
            if hasattr(fleet, 'assignments'):
                mission = next((m for m in fleet.assignments.values() if m.mission_id == drone.current_mission), None)
            if mission:
                mission_status = f"On Mission: {mission.task_type} ({mission.status})"
            else:
                mission_status = f"On Mission: {drone.current_mission}"
        elif drone.operational_status == "returning_to_base":
            mission_status = f"Returning to Base ({drone.battery_percent:.1f}%)"
        elif drone.operational_status == "charging":
            mission_status = f"Charging ({drone.battery_percent:.1f}%)"
        elif drone.operational_status == "available" and not is_available:
            # Determine why unavailable even though status says available
            reasons = []
            if drone.battery_percent < 10.0:
                reasons.append("Low battery")
            if drone.mechanical_health == "critical":
                reasons.append("Critical health")
            if hasattr(state_agent, '_essential_sensors_ok') and not state_agent._essential_sensors_ok(drone.sensor_status):
                reasons.append("Sensor fault")
            if reasons:
                mission_status = f"Available but: {', '.join(reasons)}"
        
        # Format battery with color indication
        battery_color = "🟢" if drone.battery_percent > 50 else "🟡" if drone.battery_percent > 20 else "🔴"
        battery_display = f"{battery_color} {drone.battery_percent:.1f}%"
        
        # Format health status
        health_icon = "🟢" if drone.mechanical_health == "ok" else "🟡" if drone.mechanical_health == "degraded" else "🔴"
        
        # Format sensor status cleanly
        sensor_display = "none"
        if drone.sensor_status:
            # Show only essential sensors or first 2
            sensor_items = list(drone.sensor_status.items())
            if len(sensor_items) > 2:
                sensor_display = f"{sensor_items[0][0]}:{sensor_items[0][1]}, {sensor_items[1][0]}:{sensor_items[1][1]}, ..."
            else:
                sensor_display = ", ".join([f"{k}:{v}" for k, v in sensor_items])
        
        drone_rows.append({
            "ID": drone.drone_id,
            "Position": f"({drone.position[0]:.1f}, {drone.position[1]:.1f})" if drone.position and len(drone.position) > 1 else "(0.0, 0.0)",
            "Battery": battery_display,
            "Health": f"{health_icon} {drone.mechanical_health}",
            "Mission Status": mission_status,
            "Sensors": sensor_display
        })
    
    if drone_rows:
        # Create dataframe with consistent column ordering
        df_drones = pd.DataFrame(drone_rows)
        st.dataframe(df_drones, use_container_width=True, hide_index=True)
    else:
        st.info("No drone data available.")
    
    # 3. Victim table (with triage priorities if available)
    st.header("🩸 Victims")
    victim_rows = []
    for victim_id, victim in fleet.victims.items():
        # Get actual victim data from environment for accurate triage
        raw_victim = victim_data_by_id.get(victim_id, {})
        
        # Compute triage priority using actual data if available, otherwise defaults
        try:
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
        except Exception as e:
            # Fallback if triage computation fails
            priority_score = 0.0
            priority_label = "Unknown"
        
        # Add cooldown status if applicable
        cooldown_status = ""
        if victim.cooldown_until_tick > 0:
            if victim.cooldown_until_tick > env.tick:
                remaining = victim.cooldown_until_tick - env.tick
                cooldown_status = f"⏳ {remaining} tick(s)"
            else:
                cooldown_status = "✅ Ready"
        
        # Format position cleanly
        position_display = "—"
        if victim.position and len(victim.position) >= 2:
            position_display = f"({victim.position[0]:.1f}, {victim.position[1]:.1f})"
        
        victim_rows.append({
            "ID": victim.victim_id,
            "Position": position_display,
            "Severity": victim.injury_severity,
            "Found By": victim.detected_by or "—",
            "Assigned To": victim.assigned_drone or "—",
            "Priority": f"{priority_score:.1f}",
            "Cooldown": cooldown_status
        })
    
    if victim_rows:
        # Create dataframe with consistent column ordering
        df_victims = pd.DataFrame(victim_rows)
        st.dataframe(df_victims, use_container_width=True, hide_index=True)
    else:
        st.info("No victim data available.")
    
    # 4. Active missions
    st.header("📋 Active Missions")
    mission_rows = []
    
    # Check if fleet has assignments attribute
    if hasattr(fleet, 'assignments') and fleet.assignments:
        for mission_id, assignment in fleet.assignments.items():
            if assignment.status in ("pending", "active"):  # Show pending and active missions
                mission_rows.append({
                    "Mission ID": mission_id,
                    "Drone": assignment.drone_id,
                    "Victim": assignment.victim_id or "—",
                    "Task": assignment.task_type,
                    "Duration": f"{assignment.estimated_duration_min:.0f} min",
                    "Status": assignment.status.capitalize()
                })
    
    if mission_rows:
        # Create dataframe with consistent column ordering
        df_missions = pd.DataFrame(mission_rows)
        st.dataframe(df_missions, use_container_width=True, hide_index=True)
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
                    if victim_state.cooldown_until_tick > env.tick:
                        remaining = victim_state.cooldown_until_tick - env.tick
                        cooldown_info = f" ⏳ (cooldown: {remaining} tick(s) remaining)"
                    else:
                        cooldown_info = " ✅ (cooldown complete)"
                st.write(f"{idx}. **{victim_obj.victim_id}** – {label} (score: {score:.2f}) – "
                         f"Severity: {victim_obj.severity}{cooldown_info}")
        else:
            st.info("Could not compute triage priorities.")
    else:
        st.info("No victims to triage.")
    
if __name__ == "__main__":
    main()
