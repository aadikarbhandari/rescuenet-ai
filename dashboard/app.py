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
from simulation.factory import get_environment
from state.fleet_state import FleetState, DroneState, VictimState
from agents.state_awareness import StateAwarenessAgent
from agents.coordinator import CoordinatorAgent
from agents.triage import TriageAgent, TriageVictim

# Initialize the environment and agents in session state
def init_system():
    """Create mock environment, fleet state, and agents."""
    if 'env' not in st.session_state:
        # Use factory to create environment (defaults to demo mode)
        st.session_state.env = get_environment()
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
    
    env, fleet, state_agent, coordinator, triage = init_system()
    
    # Get runtime mode from environment
    runtime_mode = "DEMO"  # Default
    if hasattr(env, '__class__'):
        if 'MockDisasterEnv' in env.__class__.__name__:
            runtime_mode = "DEMO"
        elif 'AirSimEnvironment' in env.__class__.__name__:
            runtime_mode = "SIM"
    
    # Runtime mode indicator
    mode_color = "🟢" if runtime_mode == "DEMO" else "🔵"
    mode_text = f"{mode_color} Runtime Mode: **{runtime_mode}**"
    if runtime_mode == "DEMO":
        mode_text += " (Mock Environment)"
    else:
        mode_text += " (AirSim Simulation)"
    
    st.markdown(f"{mode_text} | 📊 Real-time overview of drones, victims, missions, and fleet readiness.")
    
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
        
        # Current tick and freshness
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current Tick", env.tick)
        with col2:
            time_since_update = time.time() - st.session_state.last_update_time
            freshness = "🟢 Fresh" if time_since_update < 5 else "🟡 Stale" if time_since_update < 30 else "🔴 Old"
            st.metric("Data Freshness", freshness)
        
        st.write(f"**Last update:** {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_update_time))}")
        st.write(f"**Elapsed:** {time_since_update:.1f}s ago")
        
        # Auto-refresh status
        if st.session_state.auto_refresh:
            st.success(f"🔄 Auto-refresh enabled ({st.session_state.refresh_interval}s)")
        else:
            st.info("⏸️ Auto-refresh paused")
        
        # System status
        st.divider()
        st.subheader("System Status")
        
        # Fleet readiness summary
        readiness = state_agent.compute_fleet_readiness_summary()
        available_pct = readiness.get('operational_percent', 0)
        status_color = "🟢" if available_pct > 50 else "🟡" if available_pct > 20 else "🔴"
        st.write(f"{status_color} **Fleet readiness:** {available_pct:.1f}%")
        st.write(f"📊 **Available drones:** {readiness.get('available_drones', 0)}/{readiness.get('total_drones', 0)}")
        st.write(f"🔋 **Avg battery:** {readiness.get('avg_battery', 0):.1f}%")
    
    # Handle simulation controls
    if step_clicked:
        env.step()
        update_fleet_from_env()
        st.rerun()
    
    if reset_clicked:
        # Reset environment using factory
        st.session_state.env = get_environment()
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
    
    # 2. Drone table with improved operational display
    st.header("🛸 Drones")
    
    # Create columns for key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_drones = len(fleet.drones)
        st.metric("Total Drones", total_drones)
    with col2:
        available_count = sum(1 for drone in fleet.drones.values() 
                            if drone.operational_status in ["idle", "available"])
        st.metric("Available", available_count)
    with col3:
        active_count = sum(1 for drone in fleet.drones.values() 
                          if drone.operational_status in ["assigned", "en_route", "on_scene"])
        st.metric("Active", active_count)
    with col4:
        charging_count = sum(1 for drone in fleet.drones.values() 
                           if drone.operational_status in ["charging", "returning_to_base"])
        st.metric("Charging/Returning", charging_count)
    
    drone_rows = []
    
    # Get availability status once
    availability = state_agent.mark_availability() if hasattr(state_agent, 'mark_availability') else {}
    
    for drone_id, drone in fleet.drones.items():
        # Determine availability status
        is_available = availability.get(drone_id, False)
        
        # Get mission/operational status with better formatting
        op_status = drone.operational_status
        status_display = op_status.replace("_", " ").title()
        
        # Color code operational status
        if op_status in ["idle", "available"]:
            status_color = "🟢"
        elif op_status in ["assigned", "en_route", "on_scene"]:
            status_color = "🔵"
        elif op_status in ["charging"]:
            status_color = "🟡"
        elif op_status in ["returning_to_base"]:
            status_color = "🟠"
        elif op_status in ["unavailable_fault"]:
            status_color = "🔴"
        else:
            status_color = "⚪"
        
        status_display = f"{status_color} {status_display}"
        
        # Add mission details if applicable
        mission_details = ""
        if drone.current_mission and op_status in ["assigned", "en_route", "on_scene"]:
            mission = None
            if hasattr(fleet, 'assignments'):
                mission = next((m for m in fleet.assignments.values() if m.mission_id == drone.current_mission), None)
            if mission:
                mission_details = f"📋 {mission.task_type} ({mission.current_phase})"
            else:
                mission_details = f"📋 {drone.current_mission}"
        
        # Format battery with color and critical warning
        battery = drone.battery_percent
        if battery > 50:
            battery_color = "🟢"
            battery_status = "Good"
        elif battery > 20:
            battery_color = "🟡"
            battery_status = "Low"
        else:
            battery_color = "🔴"
            battery_status = "Critical"
        
        battery_display = f"{battery_color} {battery:.1f}% ({battery_status})"
        
        # Format health status with severity
        health = drone.mechanical_health
        if health == "ok":
            health_color = "🟢"
            health_status = "Operational"
        elif health == "degraded":
            health_color = "🟡"
            health_status = "Degraded"
        else:  # critical
            health_color = "🔴"
            health_status = "Critical"
        
        health_display = f"{health_color} {health_status}"
        
        # Format sensor status cleanly
        sensor_display = "—"
        if drone.sensor_status:
            # Count operational sensors
            ok_sensors = sum(1 for status in drone.sensor_status.values() if status == "ok")
            total_sensors = len(drone.sensor_status)
            sensor_status = f"{ok_sensors}/{total_sensors} OK"
            
            # Show key sensor status
            key_sensors = []
            for sensor, status in drone.sensor_status.items():
                if sensor in ["rgb", "thermal", "lidar"]:
                    key_sensors.append(f"{sensor}:{status}")
            
            if key_sensors:
                sensor_display = f"{sensor_status} ({', '.join(key_sensors[:2])})"
            else:
                sensor_display = sensor_status
        
        # Position with altitude if available
        position_display = "—"
        if drone.position and len(drone.position) >= 2:
            if len(drone.position) >= 3:
                position_display = f"({drone.position[0]:.0f}, {drone.position[1]:.0f}, {drone.position[2]:.0f}m)"
            else:
                position_display = f"({drone.position[0]:.0f}, {drone.position[1]:.0f})"
        
        drone_rows.append({
            "ID": drone.drone_id,
            "Status": status_display,
            "Battery": battery_display,
            "Health": health_display,
            "Position": position_display,
            "Mission": mission_details if mission_details else "—",
            "Sensors": sensor_display
        })
    
    if drone_rows:
        # Create dataframe with consistent column ordering
        df_drones = pd.DataFrame(drone_rows)
        st.dataframe(df_drones, use_container_width=True, hide_index=True)
        
        # Add legend for status colors
        with st.expander("Status Legend"):
            cols = st.columns(4)
            with cols[0]:
                st.write("🟢 Idle/Available")
                st.write("🔵 Active Mission")
            with cols[1]:
                st.write("🟡 Charging")
                st.write("🟠 Returning to Base")
            with cols[2]:
                st.write("🔴 Fault/Unavailable")
                st.write("⚪ Other")
            with cols[3]:
                st.write("🔋 >50% Good")
                st.write("🔋 20-50% Low")
                st.write("🔋 <20% Critical")
    else:
        st.info("No drone data available.")
    
    # 3. Victim table with improved state display
    st.header("🩸 Victims")
    
    # Victim summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_victims = len(fleet.victims)
        st.metric("Total Victims", total_victims)
    with col2:
        detected_count = sum(1 for v in fleet.victims.values() if v.is_detected)
        st.metric("Detected", detected_count)
    with col3:
        assigned_count = sum(1 for v in fleet.victims.values() if v.assigned_drone)
        st.metric("Assigned", assigned_count)
    with col4:
        critical_count = sum(1 for v in fleet.victims.values() if v.injury_severity == "critical")
        st.metric("Critical", critical_count)
    
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
        
        # Color code severity
        severity = victim.injury_severity
        if severity == "critical":
            severity_color = "🔴"
            severity_display = f"{severity_color} Critical"
        elif severity == "severe":
            severity_color = "🟠"
            severity_display = f"{severity_color} Severe"
        elif severity == "moderate":
            severity_color = "🟡"
            severity_display = f"{severity_color} Moderate"
        elif severity == "minor":
            severity_color = "🟢"
            severity_display = f"{severity_color} Minor"
        else:
            severity_color = "⚪"
            severity_display = f"{severity_color} {severity}"
        
        # Detection status
        if victim.is_detected:
            if victim.is_confirmed:
                detection_status = "✅ Confirmed"
            else:
                detection_status = "🟡 Detected"
        else:
            detection_status = "❓ Undetected"
        
        # Assignment status
        if victim.assigned_drone:
            assignment_status = f"📋 Assigned to {victim.assigned_drone}"
            if victim.mission_id:
                assignment_status += f" ({victim.mission_id})"
        else:
            assignment_status = "—"
        
        # Cooldown status with time remaining
        cooldown_status = ""
        if victim.cooldown_until_tick > 0:
            if victim.cooldown_until_tick > env.tick:
                remaining = victim.cooldown_until_tick - env.tick
                cooldown_status = f"⏳ {remaining} tick(s) remaining"
            else:
                cooldown_status = "✅ Ready for reassignment"
        
        # Position with altitude if available
        position_display = "—"
        if victim.position and len(victim.position) >= 2:
            if len(victim.position) >= 3:
                position_display = f"({victim.position[0]:.0f}, {victim.position[1]:.0f}, {victim.position[2]:.0f}m)"
            else:
                position_display = f"({victim.position[0]:.0f}, {victim.position[1]:.0f})"
        
        # Priority with color coding
        if priority_score > 70:
            priority_color = "🔴"
            priority_text = "Immediate"
        elif priority_score > 40:
            priority_color = "🟠"
            priority_text = "High"
        elif priority_score > 20:
            priority_color = "🟡"
            priority_text = "Medium"
        else:
            priority_color = "🟢"
            priority_text = "Low"
        
        priority_display = f"{priority_color} {priority_score:.1f} ({priority_text})"
        
        victim_rows.append({
            "ID": victim.victim_id,
            "Severity": severity_display,
            "Priority": priority_display,
            "Status": detection_status,
            "Position": position_display,
            "Assignment": assignment_status,
            "Cooldown": cooldown_status if cooldown_status else "—"
        })
    
    if victim_rows:
        # Create dataframe with consistent column ordering
        df_victims = pd.DataFrame(victim_rows)
        st.dataframe(df_victims, use_container_width=True, hide_index=True)
    else:
        st.info("No victim data available.")
    
    # 4. Active missions with phase progression
    st.header("📋 Active Missions")
    
    # Mission summary metrics
    if hasattr(fleet, 'assignments') and fleet.assignments:
        total_missions = len(fleet.assignments)
        active_missions = sum(1 for a in fleet.assignments.values() 
                             if a.current_phase not in ("completed", "aborted"))
        completed_missions = sum(1 for a in fleet.assignments.values() 
                                if a.current_phase == "completed")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Missions", total_missions)
        with col2:
            st.metric("Active", active_missions)
        with col3:
            st.metric("Completed", completed_missions)
    
    mission_rows = []
    
    # Check if fleet has assignments attribute
    if hasattr(fleet, 'assignments') and fleet.assignments:
        for mission_id, assignment in fleet.assignments.items():
            # Show all missions including completed for tracking
            show_mission = True  # Show all missions for tracking
            
            if show_mission:
                # Get drone status for this mission
                drone_status = "Unknown"
                drone_battery = "—"
                if assignment.drone_id in fleet.drones:
                    drone = fleet.drones[assignment.drone_id]
                    drone_status = drone.operational_status.replace("_", " ").title()
                    drone_battery = f"{drone.battery_percent:.1f}%"
                
                # Color code mission phase
                phase = assignment.current_phase
                if phase == "completed":
                    phase_color = "✅"
                    phase_display = f"{phase_color} Completed"
                elif phase == "aborted":
                    phase_color = "❌"
                    phase_display = f"{phase_color} Aborted"
                elif phase == "en_route":
                    phase_color = "🟡"
                    phase_display = f"{phase_color} En Route"
                elif phase == "on_scene":
                    phase_color = "🔵"
                    phase_display = f"{phase_color} On Scene"
                elif phase == "returning":
                    phase_color = "🟠"
                    phase_display = f"{phase_color} Returning"
                else:
                    phase_color = "⚪"
                    phase_display = f"{phase_color} {phase.capitalize()}"
                
                # Task type with icon
                task_type = assignment.task_type
                if task_type == "scan":
                    task_icon = "📡"
                elif task_type == "extract":
                    task_icon = "🔄"
                elif task_type == "deliver":
                    task_icon = "📦"
                else:
                    task_icon = "📋"
                
                # Duration with progress indicator
                duration = assignment.estimated_duration_min
                if phase == "completed":
                    duration_display = f"✅ {duration:.0f} min (done)"
                elif phase in ["en_route", "on_scene"]:
                    duration_display = f"⏳ {duration:.0f} min (in progress)"
                else:
                    duration_display = f"{duration:.0f} min"
                
                # Mission age (ticks since creation if available)
                mission_age = f"Tick {env.tick}"  # Simplified - could track creation tick
                
                mission_rows.append({
                    "Mission ID": mission_id,
                    "Drone": f"{assignment.drone_id} ({drone_status})",
                    "Victim": assignment.victim_id or "—",
                    "Task": f"{task_icon} {task_type}",
                    "Duration": duration_display,
                    "Phase": phase_display,
                    "Drone Battery": drone_battery,
                    "Age": mission_age
                })
    
    if mission_rows:
        # Create dataframe with consistent column ordering
        df_missions = pd.DataFrame(mission_rows)
        st.dataframe(df_missions, use_container_width=True, hide_index=True)
        
        # Mission phase progression visualization
        with st.expander("Mission Phase Progression"):
            st.markdown("""
            **Mission Lifecycle:**
            1. **Assigned** → Drone assigned to mission
            2. **En Route** → Drone traveling to victim
            3. **On Scene** → Drone performing task (scan/extract/deliver)
            4. **Returning** → Drone returning to base
            5. **Completed** → Mission successfully completed
            6. **Aborted** → Mission failed or cancelled
            """)
            
            # Show current phase distribution
            if hasattr(fleet, 'assignments') and fleet.assignments:
                phase_counts = {}
                for assignment in fleet.assignments.values():
                    phase = assignment.current_phase
                    phase_counts[phase] = phase_counts.get(phase, 0) + 1
                
                if phase_counts:
                    st.write("**Current Phase Distribution:**")
                    for phase, count in phase_counts.items():
                        st.write(f"- {phase.capitalize()}: {count} mission(s)")
    else:
        st.info("No active missions.")
    
    # 5. Triage priorities with urgency indicators
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
            # Triage summary
            col1, col2, col3 = st.columns(3)
            with col1:
                immediate_count = sum(1 for _, score, _ in prioritized if score > 70)
                st.metric("Immediate", immediate_count, delta=None)
            with col2:
                high_count = sum(1 for _, score, _ in prioritized if 40 < score <= 70)
                st.metric("High", high_count, delta=None)
            with col3:
                medium_low_count = sum(1 for _, score, _ in prioritized if score <= 40)
                st.metric("Medium/Low", medium_low_count, delta=None)
            
            st.subheader("Priority Queue (Top 10)")
            for idx, (victim_obj, score, label) in enumerate(prioritized[:10], 1):
                # Get victim state
                victim_state = fleet.victims.get(victim_obj.victim_id)
                
                # Priority indicator
                if score > 70:
                    priority_icon = "🔴"
                    urgency = "IMMEDIATE"
                elif score > 40:
                    priority_icon = "🟠"
                    urgency = "HIGH"
                elif score > 20:
                    priority_icon = "🟡"
                    urgency = "MEDIUM"
                else:
                    priority_icon = "🟢"
                    urgency = "LOW"
                
                # Status indicators
                status_indicators = []
                
                # Detection status
                if victim_state:
                    if victim_state.is_detected:
                        if victim_state.is_confirmed:
                            status_indicators.append("✅ Confirmed")
                        else:
                            status_indicators.append("🟡 Detected")
                    else:
                        status_indicators.append("❓ Undetected")
                    
                    # Assignment status
                    if victim_state.assigned_drone:
                        status_indicators.append(f"📋 Assigned to {victim_state.assigned_drone}")
                    
                    # Cooldown status
                    if victim_state.cooldown_until_tick > 0:
                        if victim_state.cooldown_until_tick > env.tick:
                            remaining = victim_state.cooldown_until_tick - env.tick
                            status_indicators.append(f"⏳ Cooldown: {remaining} tick(s)")
                        else:
                            status_indicators.append("✅ Ready")
                
                # Format output
                status_text = " | ".join(status_indicators) if status_indicators else "No status"
                
                st.write(f"{priority_icon} **{idx}. {victim_obj.victim_id}** – **{urgency}** priority")
                st.write(f"   Score: {score:.1f} | Severity: {victim_obj.severity} | {status_text}")
                st.write("---")
        else:
            st.info("Could not compute triage priorities.")
    else:
        st.info("No victims to triage.")
    
    # 6. System status footer
    st.divider()
    
    # Current system status
    current_time = time.strftime('%H:%M:%S', time.localtime(time.time()))
    time_since_update = time.time() - st.session_state.last_update_time
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Last Update:** {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_update_time))}")
        st.write(f"**Elapsed:** {time_since_update:.1f}s")
    with col2:
        st.write(f"**Current Tick:** {env.tick}")
        st.write(f"**Runtime Mode:** {runtime_mode}")
    with col3:
        if st.session_state.auto_refresh:
            st.write("**Refresh:** 🔄 Auto")
            st.write(f"**Interval:** {st.session_state.refresh_interval}s")
        else:
            st.write("**Refresh:** ⏸️ Manual")
            st.write("**Click 'Step' to advance**")
    
    # Quick status summary
    readiness = state_agent.compute_fleet_readiness_summary()
    available_pct = readiness.get('operational_percent', 0)
    
    if available_pct > 50:
        system_status = "🟢 Operational"
    elif available_pct > 20:
        system_status = "🟡 Degraded"
    else:
        system_status = "🔴 Critical"
    
    st.write(f"**System Status:** {system_status} | **Fleet Readiness:** {available_pct:.1f}%")
    st.caption(f"RescueNet AI Dashboard • {current_time} • Demo Mode: Mock Environment")
    
if __name__ == "__main__":
    main()
