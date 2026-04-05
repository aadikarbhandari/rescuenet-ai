import sys
import os
import time
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import requests
from typing import Dict, Any, List
from datetime import datetime, timedelta
from utils.reliability import RetryPolicy, resilient_post

# Import existing backend modules
from simulation.factory import get_environment
from simulation.mock_env import MockDisasterEnv
from state.fleet_state import FleetState, DroneState, VictimState, DroneStatus, MissionStatus
from agents.state_awareness import StateAwarenessAgent
from agents.coordinator import CoordinatorAgent
from agents.triage import TriageAgent, TriageVictim
from config.settings import Settings

def _build_runtime_components(env):
    """Build fleet and agents from an environment snapshot."""
    initial_drones = env.get_drone_snapshots()
    drone_ids = [d.get('drone_id') or d.get('id') for d in initial_drones if (d.get('drone_id') or d.get('id'))]
    if not drone_ids:
        drone_ids = ['drone_1', 'drone_2', 'drone_3']
    fleet = FleetState(drone_ids)
    state_agent = StateAwarenessAgent(fleet)
    coordinator = CoordinatorAgent(fleet)
    triage = TriageAgent()
    return fleet, state_agent, coordinator, triage


def _station_panel_data(env) -> List[Dict[str, Any]]:
    """Build station table rows from env when available, with safe fallback."""
    if hasattr(env, "get_station_status"):
        try:
            rows = []
            for stn in env.get_station_status():
                supplies = stn.get("supplies", {})
                remaining = sum(v for v in supplies.values() if isinstance(v, (int, float)))
                rows.append({
                    "Station": stn.get("name", "Station"),
                    "First Aid Kits": int(supplies.get("first_aid_kit", 0)),
                    "Water": int(supplies.get("water", 0)),
                    "Food": int(supplies.get("food", 0)),
                    "Supplies Remaining": int(remaining),
                    "Charging Slots": int(stn.get("charging_slots", 0)),
                    "Drones Present": len(stn.get("drones_present", [])),
                })
            if rows:
                return rows
        except Exception:
            pass
    return [
        {"Station": "Station Alpha", "First Aid Kits": 40, "Water": 80, "Food": 60, "Supplies Remaining": 180, "Charging Slots": 4, "Drones Present": 2},
        {"Station": "Station Beta", "First Aid Kits": 35, "Water": 70, "Food": 55, "Supplies Remaining": 160, "Charging Slots": 2, "Drones Present": 3},
        {"Station": "Station Gamma", "First Aid Kits": 45, "Water": 90, "Food": 75, "Supplies Remaining": 210, "Charging Slots": 6, "Drones Present": 1},
    ]

# Initialize the environment and agents in session state
def init_system():
    """Create mock environment, fleet state, and agents."""
    if 'env' not in st.session_state:
        try:
            st.session_state.env = get_environment()
            fleet, state_agent, coordinator, triage = _build_runtime_components(st.session_state.env)
            st.session_state.fleet = fleet
            st.session_state.state_agent = state_agent
            st.session_state.coordinator = coordinator
            st.session_state.triage = triage
            st.session_state.simulation_running = False
            st.session_state.last_update_time = time.time()
            st.session_state.start_time = time.time()
            st.session_state.auto_refresh = True
            st.session_state.refresh_interval = 2.0
            st.session_state.system_status = "running"
            st.session_state.demo_num_drones = st.session_state.get('demo_num_drones', len(fleet.drones))
            st.session_state.demo_num_victims = st.session_state.get('demo_num_victims', len(st.session_state.env.get_victim_snapshots()))
            
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
            if drone_id not in fleet.drones:
                fleet.drones[drone_id] = DroneState(id=drone_id)
            drone = fleet.drones[drone_id]
            drone.battery = d.get('battery_percent', d.get('battery', 100.0))
            drone.position = tuple(d.get('position', (0.0, 0.0, 0.0)))
            status = str(d.get('operational_status', 'idle')).lower()
            if status in ('idle', 'available'):
                drone.status = DroneStatus.AVAILABLE
            elif status in ('charging',):
                drone.status = DroneStatus.CHARGING
            elif status in ('offline',):
                drone.status = DroneStatus.OFFLINE
            else:
                drone.status = DroneStatus.BUSY
            drone.current_mission_id = d.get('current_mission', None)
        
        st.session_state['victim_raw'] = {v.get('victim_id', v.get('id','')): v for v in victim_snapshots}
        for v in victim_snapshots:
            victim_id = v.get('victim_id', v.get('id', 'unknown'))
            injury = str(v.get('injury_severity', v.get('severity', 'moderate'))).lower()
            sev_map = {'critical': 95, 'severe': 75, 'moderate': 50, 'minor': 25}
            normalized = {
                "id": victim_id,
                "position": v.get("position", (0.0, 0.0, 0.0)),
                "severity": sev_map.get(injury, 50),
                "triage_score": sev_map.get(injury, 50),
                "status": v.get("status", "assigned" if v.get("assigned_drone") else "discovered"),
                "assigned_drone_id": v.get("assigned_drone"),
                "assigned_mission_id": v.get("mission_id"),
            }
            fleet.update_victim(normalized)
        
        state_agent.ingest_raw_drone_data(drone_snapshots)
        
        completed_missions = env.get_completed_missions()
        for mission_id in completed_missions:
            fleet.update_mission_status(mission_id, MissionStatus.COMPLETED)
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
    
    victim_raw = st.session_state.get('victim_raw', {})
    victim_objs = list(fleet.victims.values())
    available_victims = [
        v for v in victim_objs
        if (
            v.assigned_drone_id is None
            and str(v.status).lower() not in ("rescued", "completed")
            and (
                bool(victim_raw.get(v.id, {}).get("is_confirmed"))
                or str(victim_raw.get(v.id, {}).get("detected_by", "none")).lower() not in ("none", "", "unknown")
            )
        )
    ]

    if available_victims:
        victim_dicts = [{"victim_id": v.id, "severity": str(v.severity), "score": v.triage_score, "position": list(v.position)} for v in available_victims]
        assignments = coordinator.decide_dispatch(victim_dicts)
        coordinator.execute_dispatch(assignments, env)

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


def _build_ops_context(env, fleet) -> Dict[str, Any]:
    """Build compact operational context for LLM dashboard briefing."""
    drones = []
    for d in fleet.drones.values():
        status = d.status.value if hasattr(d.status, "value") else str(d.status)
        drones.append({
            "id": d.id,
            "status": status,
            "battery": round(float(d.battery), 1),
            "mission_id": d.current_mission_id,
            "position": list(d.position),
        })

    victims = []
    for v in fleet.victims.values():
        victims.append({
            "id": v.id,
            "severity": v.severity,
            "triage_score": v.triage_score,
            "status": v.status,
            "assigned_drone_id": v.assigned_drone_id,
        })

    return {
        "tick": getattr(env, "tick", 0),
        "drones": drones,
        "victims": victims,
        "active_missions": len([m for m in fleet.missions.values() if str(getattr(m.status, "value", m.status)).lower() in ("active", "pending")]),
    }


def _coerce_message_content_to_text(message: Any) -> str:
    """
    Convert provider-specific message payloads into plain text.
    Supports:
    - {"content": "text"}
    - {"content": [{"type":"text","text":"..."}]}
    - raw string message payloads
    """
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return ""

    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                txt = item.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
        return "\n".join(parts)
    if isinstance(content, dict):
        txt = content.get("text")
        return txt if isinstance(txt, str) else ""
    return ""


def _extract_first_json_object(text: str) -> Dict[str, Any] | None:
    """
    Extract and parse the first balanced JSON object from arbitrary text.
    Works with plain JSON and fenced markdown JSON blocks.
    """
    if not isinstance(text, str) or not text:
        return None
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:idx + 1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    return None
    return None


def generate_ai_dashboard_brief(env, fleet) -> Dict[str, Any]:
    """
    Ask LLM for operational dashboard briefing.
    Falls back to deterministic summary if LLM unavailable.
    """
    context = _build_ops_context(env, fleet)
    settings = Settings()
    api_key = settings.deepseek.deepseek_api_key
    base_url = settings.deepseek.deepseek_base_url
    model = settings.deepseek.deepseek_model

    fallback = {
        "headline": "Autonomous Ops Brief",
        "priority_actions": [
            "Keep critical victims prioritized for nearest available drones.",
            "Route low-battery drones toward charging after mission completion.",
            "Maintain at least one standby drone for sudden incidents."
        ],
        "alerts": [],
        "confidence": "fallback"
    }

    if not api_key or api_key == "YOUR_API_KEY_HERE":
        fallback["confidence"] = "ai_unavailable_no_key"
        fallback["alerts"] = ["LLM key not configured; using deterministic operations brief."]
        return fallback

    prompt = (
        "You are RescueNet operations AI. Return strict JSON with keys: "
        "headline (string), priority_actions (array of 3 short strings), "
        "alerts (array of short strings), confidence (string). "
        "Context: " + json.dumps(context)
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You generate concise emergency-ops dashboard summaries in strict JSON."},
            {"role": "user", "content": prompt + " Return ONLY valid JSON. Do not include markdown fences."},
        ],
        "temperature": 0.2,
        "max_tokens": 450,
    }
    try:
        r = resilient_post(
            url=f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            payload=payload,
            policy=RetryPolicy(max_attempts=2, timeout_seconds=12),
            breaker_key="dashboard_ai_brief",
        )
        if r is None:
            fallback["alerts"] = ["AI briefing service timed out/unavailable. Using deterministic brief."]
            fallback["confidence"] = "ai_unavailable_brief_timeout"
            return fallback
        r.raise_for_status()
        body = r.json()
        choices = body.get("choices", []) if isinstance(body, dict) else []
        message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
        content_text = _coerce_message_content_to_text(message)
        parsed = _extract_first_json_object(content_text)
        if isinstance(parsed, dict):
            parsed["confidence"] = parsed.get("confidence", "ai_live")
            return parsed
        fallback["alerts"] = ["AI brief response was not valid JSON. Using deterministic brief."]
        fallback["confidence"] = "ai_unavailable_brief_parse"
        return fallback
    except Exception as e:
        fallback["alerts"] = [f"AI brief unavailable: {type(e).__name__} ({e}). Using deterministic brief."]
        fallback["confidence"] = "ai_unavailable_brief_error"
    return fallback

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
        elif 'AirSimEnvironment' in env.__class__.__name__ or 'AirSimEnv' in env.__class__.__name__:
            runtime_mode = "SIM"
    
    # Header with title and system status badge
    status_badge = "🟢 Running" if st.session_state.get('system_status') == 'running' else "🔴 Offline"
    st.markdown(f"# 🚁 RescueNet AI - Live Dashboard <span style='font-size: 16px; margin-left: 20px;'>{status_badge}</span>", unsafe_allow_html=True)
    st.markdown("---")

    # AI operational overlay
    st.subheader("🧠 AI Operations Brief")
    ai_brief = generate_ai_dashboard_brief(env, fleet)
    st.markdown(f"**{ai_brief.get('headline', 'Autonomous Ops Brief')}**")
    for item in ai_brief.get("priority_actions", [])[:3]:
        st.markdown(f"- {item}")
    alerts = ai_brief.get("alerts", []) or []
    if alerts:
        st.warning(" | ".join(alerts[:3]))
    st.caption(f"AI brief mode: {ai_brief.get('confidence', 'unknown')}")
    st.markdown("---")
    
    # Calculate metrics
    total_drones = len(fleet.drones) if fleet else 0
    available_drones = len([d for d in fleet.drones.values() if d.status == DroneStatus.AVAILABLE]) if fleet else 0
    active_missions = len([d for d in fleet.drones.values() if d.current_mission_id is not None]) if fleet else 0
    
    victims_detected = len(fleet.victims) if fleet else 0
    victims_rescued = len([v for v in fleet.victims.values() if str(v.status).lower() in ("rescued", "completed")]) if fleet else 0
    
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
                    "Status": drone.status.value if hasattr(drone.status, "value") else str(drone.status),
                    "Battery": f"{drone.battery:.1f}%",
                    
                    "Mission": drone.current_mission_id if drone.current_mission_id else "None",
                    "Position": f"({drone.position[0]:.1f}, {drone.position[1]:.1f})",
                    "Health": drone.status.value if hasattr(drone.status, "value") else str(drone.status)
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
                st.caption(f"{len(active_mission_list)} active missions")
                mission_rows = [{
                    "Drone": drone_id,
                    "Mission": drone.current_mission_id,
                    "Battery": f"{drone.battery:.1f}%",
                } for drone_id, drone in active_mission_list]
                preview = mission_rows[:25]
                st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True, height=280)
                if len(mission_rows) > 25:
                    with st.expander(f"Show all {len(mission_rows)} active missions"):
                        st.dataframe(pd.DataFrame(mission_rows), use_container_width=True, hide_index=True, height=420)
            else:
                st.info("No active missions")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Security Alerts (simulated - would come from actual alerts)
        st.subheader("⚠️ Security Alerts")
        
        # Check for low battery drones
        low_battery_drones = [d for d in fleet.drones.values() if d.battery <= 25] if fleet else []
        # Check for drones with mechanical issues
        unhealthy_drones = [d for d in fleet.drones.values() if str(getattr(d.status, "value", d.status)).lower() in ['unavailable_fault', 'fault']] if fleet else []
        
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
                "Assigned Drone": st.session_state.get('victim_raw', {}).get(victim.id, {}).get('assigned_drone', victim.assigned_drone_id) or "Unassigned",
                "Status": ("Assigned" if (st.session_state.get('victim_raw', {}).get(victim.id, {}).get('assigned_drone') or victim.assigned_drone_id) else victim.status.capitalize() if victim.status else "Discovered")
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
    
    station_data = _station_panel_data(env)
    
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
        is_demo = runtime_mode == "DEMO"
        if is_demo:
            st.subheader("🧪 Demo Scenario")
            prev_drones = int(st.session_state.get('demo_num_drones', len(fleet.drones) if fleet else 3))
            prev_victims = int(st.session_state.get('demo_num_victims', len(fleet.victims) if fleet else 4))
            st.session_state.demo_num_drones = st.number_input(
                "Demo drones",
                min_value=1,
                max_value=100,
                value=prev_drones,
                step=1,
            )
            st.session_state.demo_num_victims = st.number_input(
                "Demo victims",
                min_value=1,
                max_value=200,
                value=prev_victims,
                step=1,
            )
            fault_mode_options = ["auto_return_if_flyable", "human_recovery", "recovery_drone"]
            current_mode = getattr(st.session_state.env, "get_failure_handling_mode", lambda: "auto_return_if_flyable")()
            selected_fault_mode = st.selectbox(
                "Fault handling mode",
                options=fault_mode_options,
                index=fault_mode_options.index(current_mode) if current_mode in fault_mode_options else 0,
                help="How demo handles mechanical-fault drones."
            )
            if hasattr(st.session_state.env, "set_failure_handling_mode"):
                st.session_state.env.set_failure_handling_mode(selected_fault_mode)
            st.caption("Counts apply instantly with 'Apply Scenario'. Reset also applies and clears mission state.")
            if st.button("Apply Scenario", type="primary"):
                try:
                    st.session_state.env = MockDisasterEnv(
                        num_drones=int(st.session_state.get('demo_num_drones', 3)),
                        num_victims=int(st.session_state.get('demo_num_victims', 4)),
                    )
                    fleet, state_agent, coordinator, triage = _build_runtime_components(st.session_state.env)
                    st.session_state.fleet = fleet
                    st.session_state.state_agent = state_agent
                    st.session_state.coordinator = coordinator
                    st.session_state.triage = triage
                    update_fleet_from_env()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error applying scenario: {e}")
            st.subheader("🏭 Stations")
            station_names = [r.get("Station") for r in _station_panel_data(st.session_state.env)]
            selected_station = st.selectbox("Station", options=station_names, index=0 if station_names else None)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("➕ Add Station"):
                    try:
                        if hasattr(st.session_state.env, "add_station"):
                            st.session_state.env.add_station()
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error adding station: {e}")
            with c2:
                if st.button("➖ Remove Station"):
                    try:
                        if hasattr(st.session_state.env, "remove_station") and selected_station:
                            removed = st.session_state.env.remove_station(selected_station)
                            if not removed:
                                st.warning("Keep at least one station.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error removing station: {e}")
            sel_row = next((r for r in _station_panel_data(st.session_state.env) if r.get("Station") == selected_station), None)
            if sel_row:
                kit = st.number_input("First aid kits", min_value=0, max_value=500, value=int(sel_row.get("First Aid Kits", 0)), step=1)
                water = st.number_input("Emergency water", min_value=0, max_value=1000, value=int(sel_row.get("Water", 0)), step=1)
                food = st.number_input("Emergency food", min_value=0, max_value=1000, value=int(sel_row.get("Food", 0)), step=1)
                if st.button("Update Supplies"):
                    try:
                        if hasattr(st.session_state.env, "update_station_supplies") and selected_station:
                            st.session_state.env.update_station_supplies(selected_station, int(kit), int(water), int(food))
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error updating supplies: {e}")
            recovery_tasks = getattr(st.session_state.env, "recovery_tasks", {})
            if recovery_tasks:
                st.markdown("**Recovery Ops**")
                st.json(recovery_tasks)
        
        # Refresh rate slider
        refresh_rate = st.slider("Refresh Rate (seconds)", min_value=1, max_value=10, value=2, help="Auto-refresh interval")
        st.session_state.refresh_interval = refresh_rate
        
        # Mode indicator
        mode_color = "1f7a1f" if runtime_mode == "DEMO" else "1f4e8a"
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
        if is_demo:
            quick1, quick2 = st.columns(2)
            with quick1:
                if st.button("➕ Add Drone"):
                    try:
                        if hasattr(st.session_state.env, "add_drone"):
                            new_drone_id = st.session_state.env.add_drone()
                            st.success(f"Added {new_drone_id}")
                            update_fleet_from_env()
                            st.rerun()
                        else:
                            st.warning("Current environment does not support runtime drone creation.")
                    except Exception as e:
                        st.error(f"Error adding drone: {e}")
            with quick2:
                if st.button("➕ Add Victim"):
                    try:
                        if hasattr(st.session_state.env, "add_victim"):
                            new_victim_id = st.session_state.env.add_victim()
                            st.success(f"Added {new_victim_id}")
                            update_fleet_from_env()
                            st.rerun()
                        else:
                            st.warning("Current environment does not support runtime victim creation.")
                    except Exception as e:
                        st.error(f"Error adding victim: {e}")
            st.caption("New victims are auto-dispatched when free drones are available.")
        
        if st.button("Step Simulation"):
            try:
                env.step()
                update_fleet_from_env()
                st.rerun()
            except Exception as e:
                st.error(f"Error stepping simulation: {e}")
        
        if st.button("Reset Simulation"):
            try:
                if runtime_mode == "DEMO":
                    st.session_state.env = MockDisasterEnv(
                        num_drones=int(st.session_state.get('demo_num_drones', 3)),
                        num_victims=int(st.session_state.get('demo_num_victims', 4)),
                    )
                else:
                    st.session_state.env = get_environment()
                fleet, state_agent, coordinator, triage = _build_runtime_components(st.session_state.env)
                st.session_state.fleet = fleet
                st.session_state.state_agent = state_agent
                st.session_state.coordinator = coordinator
                st.session_state.triage = triage
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
