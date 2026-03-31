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
            x=(d.get('x') if 'x' in d else d.get('position', (0, 0, 0))[0]),
            y=(d.get('y') if 'y' in d else d.get('position', (0, 0, 0))[1]),
            battery=d.get('battery', 100.0),
            status=d.get('status', 'idle'),
            sensor_status=d.get('sensor_status', {}),
            capabilities=d.get('capabilities', [])
        )
        fleet.add_or_update_drone(ds)
    
    # Update fleet state with victim data
    for v in victim_snapshots:
        from state.fleet_state import VictimState
        vs = VictimState(
            victim_id=v['id'],
            x=v['x'],
            y=v['y'],
            injury_severity=v.get('injury_severity', 'unknown'),
            found_by=v.get('found_by', None),
            last_seen=v.get('last_seen', 0)
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
    
    # 1. Fleet readiness summary
    st.header("📊 Fleet Readiness Summary")
    readiness = state_agent.compute_fleet_readiness_summary()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Drones", readiness.get("total_drones", 0))
    col2.metric("Available Drones", readiness.get("available_drones", 0))
    col3.metric("Operational Drones", readiness.get("operational_drones", 0))
    col4.metric("Readiness %", f"{readiness.get('readiness_percentage', 0):.1f}%")
    
    # 2. Drone table
    st.header("🛸 Drones")
    drone_rows = []
    for drone_id, drone in fleet.drones.items():
        drone_rows.append({
            "ID": drone.drone_id,
            "X": drone.x,
            "Y": drone.y,
            "Battery": f"{drone.battery:.1f}%",
            "Status": drone.status,
            "Capabilities": ", ".join(drone.capabilities) if drone.capabilities else "none"
        })
    if drone_rows:
        st.dataframe(pd.DataFrame(drone_rows), use_container_width=True)
    else:
        st.info("No drone data available.")
    
    # 3. Victim table (with triage priorities if available)
    st.header("🩸 Victims")
    victim_rows = []
    for victim_id, victim in fleet.victims.items():
        # Try to compute triage priority
        triage_obj = TriageVictim(
            victim_id=victim.victim_id,
            x=victim.x,
            y=victim.y,
            injury_severity=victim.injury_severity,
            found_by=victim.found_by,
            last_seen=victim.last_seen
        )
        priority_score, priority_label = triage.compute_priority(triage_obj)
        victim_rows.append({
            "ID": victim.victim_id,
            "X": victim.x,
            "Y": victim.y,
            "Severity": victim.injury_severity,
            "Found By": victim.found_by or "—",
            "Priority Score": f"{priority_score:.2f}",
            "Priority Label": priority_label
        })
    if victim_rows:
        st.dataframe(pd.DataFrame(victim_rows), use_container_width=True)
    else:
        st.info("No victim data available.")
    
    # 4. Active missions
    st.header("📋 Active Missions")
    mission_rows = []
    for mission_id, assignment in fleet.assignments.items():
        if not assignment.completed:
            mission_rows.append({
                "Mission ID": mission_id,
                "Drone ID": assignment.drone_id,
                "Victim ID": assignment.victim_id or "—",
                "Task Type": assignment.task_type,
                "Estimated Duration": f"{assignment.estimated_duration_min:.1f} min",
                "Assigned At": assignment.assigned_at
            })
    if mission_rows:
        st.dataframe(pd.DataFrame(mission_rows), use_container_width=True)
    else:
        st.info("No active missions.")
    
    # 5. Triage priorities (as a separate section)
    st.header("🚨 Triage Priorities")
    if fleet.victims:
        # Use the triage agent's prioritization method
        triage_victims = []
        for victim in fleet.victims.values():
            triage_victims.append(TriageVictim(
                victim_id=victim.victim_id,
                x=victim.x,
                y=victim.y,
                injury_severity=victim.injury_severity,
                found_by=victim.found_by,
                last_seen=victim.last_seen
            ))
        prioritized = triage.prioritize_victims(triage_victims)
        if prioritized:
            st.subheader("Sorted by priority (highest first)")
            for idx, (victim_obj, score, label) in enumerate(prioritized[:10], 1):
                st.write(f"{idx}. **{victim_obj.victim_id}** – {label} (score: {score:.2f}) – "
                         f"Severity: {victim_obj.injury_severity}")
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
