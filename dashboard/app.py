import sys
import os
import time
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Import existing backend modules
from simulation.factory import get_environment
from state.fleet_state import FleetState, DroneState, VictimState
from agents.state_awareness import StateAwarenessAgent
from agents.coordinator import CoordinatorAgent
from agents.triage import TriageAgent, TriageVictim

# Initialize the environment and agents in session state
def init_system():
    """Create mock environment, fleet state, and agents."""
    if 'env' not in st.session_state:
        try:
            st.session_state.env = get_environment()
            st.session_state.fleet = FleetState(['drone_1', 'drone_2', 'drone_3'])
            st.session_state.state_agent = StateAwarenessAgent(st.session_state.fleet)
            st.session_state.coordinator = CoordinatorAgent(st.session_state.fleet)
            st.session_state.triage = TriageAgent()
            st.session_state.simulation_running = False
            st.session_state.last_update_time = time.time()
            st.session_state.start_time = time.time()
            st.session_state.auto_refresh = True
            st.session_state.refresh_interval = 2.0
            st.session_state.system_status = "running"
            
            update_fleet_from_env()
            
            print(f"[Dashboard] System initialized at tick {st.session_state.env.tick}")
        except Exception as e:
            st.session_state.system_status = "offline"
            import traceback; st.error(str(e)); traceback.print_exc()
    
    return (
        st.session_state.get('env', None),
        st.session_state.get('fleet', None),
        st.session_state.get('state_agent', None),
        st.session_state.get('coordinator', None),
        st.session_state.get('triage', None)
    )

def update_fleet_from_env():
    """Update fleet state with latest data from environment."""
    env = st.session_state.env
    fleet = st.session_state.fleet
    state_agent = st.session_state.state_agent
    
    try:
        drone_snapshots = env.get_drone_snapshots()
        victim_snapshots = env.get_victim_snapshots()
        
        for d in drone_snapshots:
            drone_id = d.get('drone_id', d.get('id', 'unknown'))
            if drone_id in fleet.drones:
                drone = fleet.drones[drone_id]
                drone.battery = d.get('battery_percent', d.get('battery', 100.0))
                drone.position = tuple(d.get('position', (0.0, 0.0, 0.0)))
                status = d.get('operational_status', 'idle')
                drone.status = status
                drone.current_mission_id = d.get('current_mission', None)
        
        st.session_state['victim_raw'] = {v.get('victim_id', v.get('id','')): v for v in victim_snapshots}
        for v in victim_snapshots:
            victim_id = v.get('victim_id', v.get('id', 'unknown'))
            fleet.update_victim(v)
        
        state_agent.ingest_raw_drone_data(drone_snapshots)
        
        completed_missions = env.get_completed_missions()
        for mission_id in completed_missions:
            fleet.update_mission_status(mission_id, 'COMPLETED')
            if True:
                print(f"[Dashboard] Mission {mission_id} marked as completed in FleetState")
        
        create_new_assignments()
        
        st.session_state.last_update_time = time.time()
    except Exception as e:
        print(f"[Dashboard] Error updating fleet: {e}")
        st.session_state.system_status = "offline"

def create_new_assignments():
    """Create new mission assignments based on current state."""
    env = st.session_state.env
    fleet = st.session_state.fleet
    coordinator = st.session_state.coordinator
    
    victim_objs = list(fleet.victims.values())
    available_victims = [v for v in victim_objs if 0 <= env.tick and v.assigned_drone_id is None]
    
    if available_victims:
        victim_dicts = [{"victim_id": v.id, "severity": str(v.severity), "score": v.triage_score, "position": list(v.position)} for v in available_victims]
        assignments = coordinator.decide_dispatch(victim_dicts)
        for assignment in assignments:
            if assignment.get("victim_id"):
                env.update_victim_assignment(assignment.get("victim_id"), assignment.get("drone_id"), assignment.get("mission_id", "m1"))
            env.update_drone_mission(assignment.get("drone_id"), assignment.get("mission_id", "m1"))

def load_ai_decisions() -> List[Dict[str, Any]]:
    """Load AI decisions from JSON file."""
    decisions_file = "/tmp/rescuenet_decisions.json"
    
    if os.path.exists(decisions_file):
        try:
            with open(decisions_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data[-10:] if len(data) > 10 else data
                elif isinstance(data, dict) and 'decisions' in data:
                    return data['decisions'][-10:] if len(data.get('decisions', [])) > 10 else data.get('decisions', [])
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Dashboard] Error loading AI decisions: {e}")
    return []

def get_battery_color(battery: float) -> str:
    """Return color for battery percentage."""
    try:
        b = float(str(battery).replace("%",""))
    except: b = 0
    if b > 50:
        return "🟢"
    elif b > 25:
        return "🟠"
    else:
        return "🔴"

def get_battery_style(battery) -> str:
    """Return color style for battery percentage."""
    try:
        b = float(str(battery).replace("%",""))
    except: b = 0
    if b > 50:
        return "color: green"
    elif b > 25:
        return "color: orange"
    else:
        return "color: red; font-weight: bold"

def calculate_victim_score(victim: VictimState) -> float:
    """Calculate triage score for a victim."""
    severity_scores = {
        'critical': 100,
        'severe': 75,
        'moderate': 50,
        'minor': 25,
        'unknown': 10
    }
    base_score = severity_scores.get(str(victim.severity).lower() if hasattr(str(victim.severity), 'lower') else 'unknown', 10)
    if victim.assigned_drone_id is None:
        base_score += 20
    return base_score

def main():
    st.set_page_config(
        page_title="RescueNet AI - Live Dashboard",
        page_icon="🚁",
        layout="wide"
    )
    
    env, fleet, state_agent, coordinator, triage = init_system()
    
    # Handle offline state
    if st.session_state.get('system_status') == 'offline' or env is None:
        st.markdown("""
        <div style='text-align: center; padding: 50px;'>
            <h2>🔄 Connecting to simulation...</h2>
            <p>Please wait while the system initializes.
        """, unsafe_allow_html=True)
        return
    
    # Determine runtime mode
    runtime_mode = "DEMO"
    if hasattr(env, '__class__'):
        if 'MockDisasterEnv' in env.__class__.__name__:
            runtime_mode = "DEMO"
        elif 'AirSimEnvironment' in env.__class__.__name__:
            runtime_mode = "SIM"
    
    # Header with title and system status badge
    status_badge = "🟢 Running" if st.session_state.get('system_status') == 'running' else "🔴 Offline"
    st.markdown(f"# 🚁 RescueNet AI - Live Dashboard <span style='font-size: 16px; margin-left: 20px;'>{status_badge}</span>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Calculate metrics
    total_drones = len(fleet.drones) if fleet else 0
    available_drones = len([d for d in fleet.drones.values() if d.status == 'available']) if fleet else 0
    active_missions = len([d for d in fleet.drones.values() if d.current_mission_id is not None]) if fleet else 0
    
    victims_detected = len(fleet.victims) if fleet else 0
    victims_rescued = len([v for v in fleet.victims.values() if v.assigned_drone_id is None and 0 <= env.tick]) if fleet else 0
    
    # Top metrics row
    st.subheader("📊 Fleet Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Drones", total_drones)
    with col2:
        st.metric("Available", available_drones)
    with col3:
        st.metric("Active Missions", active_missions)
    with col4:
        st.metric("Victims Detected", victims_detected)
    with col5:
        st.metric("Victims Rescued", victims_rescued)
    
    st.markdown("---")
    
    # Two columns: Left (60%) Drone Fleet Status, Right (40%) Missions + Alerts
    col_left, col_right = st.columns([6, 4])
    
    with col_left:
        st.subheader("🚁 Drone Fleet Status")
        
        if fleet and fleet.drones:
            drone_data = []
            for drone_id, drone in fleet.drones.items():
                drone_data.append({
                    "Drone ID": drone.id,
                    "Status": drone.status,
                    "Battery": f"{drone.battery:.1f}%",
                    
                    "Mission": drone.current_mission_id if drone.current_mission_id else "None",
                    "Position": f"({drone.position[0]:.1f}, {drone.position[1]:.1f})",
                    "Health": drone.status
                })
            
            df = pd.DataFrame(drone_data)
            
            if not df.empty:
                # Apply styling for battery
                st.dataframe(
                    df.style.map(get_battery_style, subset=['Battery']),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No drones in fleet")
        else:
            st.info("No drones available")
    
    with col_right:
        st.subheader("🎯 Active Missions")
        
        # Active missions list
        if fleet and fleet.drones:
            active_mission_list = [(d_id, d) for d_id, d in fleet.drones.items() if d.current_mission_id is not None]
            if active_mission_list:
                for drone_id, drone in active_mission_list:
                    st.markdown(f"""
                    <div style='padding: 10px; margin: 5px 0; background-color: #1E3A5F; border-radius: 5px;'>
                        <strong>🛸 {drone_id}</strong><br>
                        <span style='color: #AAAAAA;'>Mission: {drone.current_mission_id}
                    """, unsafe_allow_html=True)
            else:
                st.info("No active missions")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Security Alerts (simulated - would come from actual alerts)
        st.subheader("⚠️ Security Alerts")
        
        # Check for low battery drones
        low_battery_drones = [d for d in fleet.drones.values() if d.battery <= 25] if fleet else []
        # Check for drones with mechanical issues
        unhealthy_drones = [d for d in fleet.drones.values() if d.status in ['unavailable_fault', 'fault']] if fleet else []
        
        alerts = []
        for drone in low_battery_drones:
            alerts.append(f"⚠️ {drone.id}: Low battery ({drone.battery:.1f}%)")
        for drone in unhealthy_drones:
            alerts.append(f"🔧 {drone.id}: Mechanical issue - {drone.status}")
        
        if alerts:
            for alert in alerts:
                st.markdown(f"<div style='color: #FF6B6B; padding: 5px;'>{alert}</div>", unsafe_allow_html=True)
        else:
            st.success("No active alerts")
    
    st.markdown("---")
    
    # Full-width Victim Triage Panel
    st.subheader("🏥 Victim Triage Panel")
    
    if fleet and fleet.victims:
        victim_data = []
        for victim_id, victim in fleet.victims.items():
            score = calculate_victim_score(victim)
            victim_data.append({
                "Victim ID": victim.id,
                "Severity": ("critical" if victim.severity >= 80 else "severe" if victim.severity >= 60 else "moderate" if victim.severity >= 40 else "minor"),
                "Score": score,
                "Position": f"({victim.position[0]:.1f}, {victim.position[1]:.1f}, {victim.position[2]:.1f})",
                "Detected By": st.session_state.get('victim_raw', {}).get(victim.id, {}).get('detected_by', 'unknown'),
                "Assigned Drone": victim.assigned_drone_id if victim.assigned_drone_id else "Unassigned",
                "Status": ("Assigned" if victim.assigned_drone_id else victim.status.capitalize() if victim.status else "Discovered")
            })
        
        df_victims = pd.DataFrame(victim_data)
        
        if not df_victims.empty:
            # Sort by score descending
            df_victims = df_victims.sort_values(by='Score', ascending=False)
            
            # Style severity column
            def severity_color(val):
                val_lower = str(val).lower()
                if 'critical' in val_lower:
                    return 'color: red; font-weight: bold'
                elif 'severe' in val_lower:
                    return 'color: orange; font-weight: bold'
                elif 'moderate' in val_lower:
                    return 'color: #FFD700'
                else:
                    return 'color: green'
            
            st.dataframe(
                df_victims.style.map(severity_color, subset=['Severity']),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No victims detected")
    else:
        st.info("No victims in system")
    
    st.markdown("---")
    
    # AI Decisions Log
    st.subheader("🤖 AI Decisions Log")
    
    decisions = load_ai_decisions()
    
    if decisions:
        for i, decision in enumerate(reversed(decisions)):
            with st.expander(f"Decision {len(decisions) - i}: {decision.get('timestamp', 'N/A')} - {decision.get('type', 'Unknown')}", expanded=False):
                st.json(decision)
    else:
        st.info("No AI decisions logged yet")
    
    st.markdown("---")
    
    # Rescue Stations Panel
    st.subheader("🏭 Rescue Stations Panel")
    
    # Simulated rescue station data (would come from environment in real system)
    station_data = [
        {"Station": "Station Alpha", "Supplies Remaining": 85, "Charging Slots": 4, "Drones Present": 2},
        {"Station": "Station Beta", "Supplies Remaining": 60, "Charging Slots": 2, "Drones Present": 3},
        {"Station": "Station Gamma", "Supplies Remaining": 92, "Charging Slots": 6, "Drones Present": 1},
    ]
    
    df_stations = pd.DataFrame(station_data)
    
    # Style supplies based on level
    def supplies_color(val):
        if val >= 70:
            return 'color: green'
        elif val >= 40:
            return 'color: orange'
        else:
            return 'color: red; font-weight: bold'
    
    st.dataframe(
        df_stations.style.map(supplies_color, subset=['Supplies Remaining']),
        use_container_width=True,
        hide_index=True
    )
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Controls")
        
        # Refresh rate slider
        refresh_rate = st.slider("Refresh Rate (seconds)", min_value=1, max_value=10, value=2, help="Auto-refresh interval")
        st.session_state.refresh_interval = refresh_rate
        
        # Mode indicator
        mode_color = "green" if runtime_mode == "DEMO" else "blue"
        st.markdown(f"""
        <div style='padding: 10px; background-color: #{mode_color}; border-radius: 5px; text-align: center;'>
            <strong>Mode: {runtime_mode}
        """, unsafe_allow_html=True)
        
        # Runtime calculation
        if 'start_time' in st.session_state:
            runtime_seconds = int(time.time() - st.session_state.start_time)
            hours = runtime_seconds // 3600
            minutes = (runtime_seconds % 3600) // 60
            seconds = runtime_seconds % 60
            st.metric("Total Runtime", f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        st.divider()
        
        # Manual controls
        st.subheader("🔧 Manual Controls")
        
        if st.button("Step Simulation"):
            try:
                env.step()
                update_fleet_from_env()
                st.rerun()
            except Exception as e:
                st.error(f"Error stepping simulation: {e}")
        
        if st.button("Reset Simulation"):
            try:
                st.session_state.env = get_environment()
                st.session_state.fleet = FleetState(['drone_1', 'drone_2', 'drone_3'])
                update_fleet_from_env()
                st.session_state.start_time = time.time()
                st.rerun()
            except Exception as e:
                st.error(f"Error resetting simulation: {e}")
        
        # Current tick display
        st.divider()
        st.metric("Current Tick", env.tick)
        
        # Data freshness
        time_since_update = time.time() - st.session_state.get('last_update_time', time.time())
        if time_since_update < 5:
            freshness = "🟢 Fresh"
        elif time_since_update < 30:
            freshness = "🟡 Stale"
        else:
            freshness = "🔴 Old"
        st.metric("Data Freshness", freshness)
        
        st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
