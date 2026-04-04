#!/usr/bin/env python3
"""
RescueNet AI - Main Entry Point
Autonomous disaster response multi-agent system
"""
import argparse
import logging
import sys
import time
import os
from typing import List, Dict, Any

from config.settings import load_settings
from simulation.factory import SimulationFactory
from state.fleet_state import FleetState, DroneStatus, MissionStatus
from agents.triage import TriageAgent
from agents.coordinator import CoordinatorAgent
from agents.security import SecurityAgent
from agents.policy_engine import PolicyEngine, PolicyConfig
from api.server import run_server_background, update_state
from integration.manager import AdapterManager


def setup_logging(verbose: bool = False):
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def print_startup_banner(settings):
    """Print startup configuration banner."""
    print("=" * 66)
    print("RESCUENET AI - AUTONOMOUS DISASTER RESPONSE SYSTEM")
    print("=" * 66)
    print(f"Runtime Mode:  {settings.mode}")
    print(f"Simulation:    {settings.ticks} ticks")
    print(f"API Server:    {'Enabled' if settings.api_enabled else 'Disabled'}")
    if settings.api_enabled:
        print(f"API Port:      {settings.api_port}")
    print("-" * 66)


def print_tick_summary(tick: int, fleet: FleetState, active_missions: int, 
                       alerts: List, victims: List, new_assignments: int):
    """Print simulation tick summary."""
    available = len(fleet.get_available_drones())
    busy = sum(1 for d in fleet.drones.values() if d.status == DroneStatus.BUSY)
    charging = sum(1 for d in fleet.drones.values() if d.status == DroneStatus.CHARGING)
    
    print(f"\n--- Tick {tick} ---")
    print(f"Fleet: {available} available, {busy} busy, {charging} charging")
    print(f"Active Missions: {active_missions}")
    print(f"Victims: {len(victims)} total")
    print(f"New Assignments: {new_assignments}")
    
    if alerts:
        print(f"Alerts: {len(alerts)} security alerts")


def land_all_drones(env):
    """Emergency landing procedure for all drones."""
    logging.info("Emergency landing all drones...")
    try:
        for drone in env.drones:
            drone_id = drone.get("drone_id")
            if drone_id:
                drone["operational_status"] = "returning_to_base"
    except Exception as e:
        logging.error(f"Error during emergency landing: {e}")


def normalize_victim_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize environment victim snapshot into FleetState-compatible shape."""
    victim_id = snapshot.get("victim_id") or snapshot.get("id")
    injury = str(snapshot.get("injury_severity", snapshot.get("severity", "moderate"))).lower()
    sev_map = {"critical": 95, "severe": 75, "moderate": 50, "minor": 25}
    triage_score = float(snapshot.get("triage_score", sev_map.get(injury, 50)))
    return {
        "id": victim_id,
        "position": snapshot.get("position", (0.0, 0.0, 0.0)),
        "severity": int(sev_map.get(injury, 50)),
        "triage_score": triage_score,
        "status": "assigned" if snapshot.get("assigned_drone") else "discovered",
        "assigned_drone_id": snapshot.get("assigned_drone"),
        "assigned_mission_id": snapshot.get("mission_id"),
    }


def warn_if_llm_not_configured(logger: logging.Logger) -> None:
    """
    Show non-fatal startup warnings when LLM environment variables are missing.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL")
    model = os.getenv("DEEPSEEK_MODEL")

    if not api_key:
        logger.warning("LLM is not connected (DEEPSEEK_API_KEY is missing). Running with fallback logic.")
        logger.warning("Set env vars before running, for example:")
        logger.warning("  export DEEPSEEK_API_KEY='your_key'")
        logger.warning("  export DEEPSEEK_BASE_URL='https://api.vultrinference.com/v1'")
        logger.warning("  export DEEPSEEK_MODEL='DeepSeek-V3.2'")
        logger.warning("See README env setup table for details.")
        return

    if not base_url or not model:
        logger.warning("DEEPSEEK_BASE_URL or DEEPSEEK_MODEL is not set; defaults will be used.")
        logger.warning("See README env setup table for recommended values.")


def main():
    """Main entry point for RescueNet AI."""
    parser = argparse.ArgumentParser(description='RescueNet AI - Autonomous Disaster Response')
    parser.add_argument('--mode', type=str, default='demo', 
                       choices=['demo', 'sim'], help='Runtime mode')
    parser.add_argument('--ticks', type=int, default=20, 
                       help='Number of simulation ticks')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--api-port', type=int, default=8000,
                       help='API server port')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger("rescuenet")
    
    # Load settings
    settings = load_settings()
    settings.ticks = args.ticks
    settings.mode = args.mode
    settings.api_enabled = True
    settings.api_port = args.api_port
    warn_if_llm_not_configured(logger)
    
    print_startup_banner(settings)
    
    # Initialize environment
    logger.info("Creating environment...")
    try:
        env = SimulationFactory.create(settings)
        logger.info(f"Environment created: {type(env).__name__}")
    except Exception as e:
        logger.error(f"Failed to create environment: {e}")
        return 1
    
    # Initialize fleet state
    drone_names = getattr(settings, 'drone_names', ['drone_1', 'drone_2', 'drone_3'])
    fleet = FleetState(drone_names=drone_names)
    logger.info("FleetState initialized")
    
    # Initialize agents
    triage_agent = TriageAgent()
    logger.info("TriageAgent initialized")
    
    coordinator = CoordinatorAgent(fleet, settings)
    logger.info("CoordinatorAgent initialized")
    
    security_agent = SecurityAgent(settings)
    logger.info("SecurityAgent initialized")
    adapter_manager = AdapterManager()
    adapter_manager.load_from_config("config.json")
    logger.info(f"AdapterManager initialized: {adapter_manager.health_report()}")
    policy_engine = PolicyEngine(
        PolicyConfig(
            min_battery_for_new_mission=25.0,
            min_reserve_available_drones=1,
            critical_override_score=90.0,
            low_battery_return_threshold=20.0,
            min_supply_drone_reserve=0,
        )
    )
    logger.info("PolicyEngine initialized")
    
    # Start API server in background
    if settings.api_enabled:
        run_server_background(port=settings.api_port)
        logger.info(f"FastAPI server started on port {settings.api_port}")
    
    # Simulation loop
    logger.info(f"Starting simulation loop for {settings.ticks} ticks")
    
    try:
        for tick in range(1, settings.ticks + 1):
            # Step environment
            obs = env.step()
            
            # Get telemetry and update fleet state
            telemetry = env.get_all_telemetry()
            fleet.update_from_telemetry(telemetry)
            recharge_moves = policy_engine.apply_recharge_policy(env, fleet)
            
            # Security scan
            alerts = security_agent.scan_all(telemetry)
            if alerts:
                logger.info(f"Security scan found {len(alerts)} alerts")
            
            # Get current victims from environment
            victim_snapshots = env.get_victim_snapshots()
            
            # Update fleet victims
            for vs in victim_snapshots:
                victim_id = vs.get('victim_id') or vs.get('id')
                if victim_id:
                    fleet.update_victim(normalize_victim_snapshot(vs))
            
            # Triage: prioritize victims
            triage_results = triage_agent.prioritize_all(victim_snapshots)
            
            # Coordinator: decide dispatch
            assignments = coordinator.decide_dispatch(triage_results)
            assignments = policy_engine.filter_assignments(assignments, fleet)
            
            # Execute dispatch
            new_assignments = 0
            if assignments:
                mission_assignments = coordinator.execute_dispatch(assignments, env)
                if mission_assignments:
                    new_assignments = len(mission_assignments)
            
            # Check for replanning needs
            coordinator.replan_if_needed(env)
            
            # Get completed missions for reporting
            completed = env.get_completed_missions()
            
            # Update API state
            state_update = {
                'drones': list(fleet.drones.values()),
                'victims': list(fleet.victims.values()),
                'missions': list(fleet.missions.values()),
                'adapters': adapter_manager.health_report(),
                'policy': {
                    'recharge_moves': recharge_moves,
                },
                'stats': {
                    'tick': tick,
                    'available_drones': len(fleet.get_available_drones()),
                    'active_missions': len([m for m in fleet.missions.values() 
                                           if m.status in [MissionStatus.ACTIVE, MissionStatus.PENDING]]),
                    'completed_missions': len(completed)
                }
            }
            update_state(state_update)
            
            # Print summary
            print_tick_summary(tick, fleet, len([m for m in fleet.missions.values() 
                                                  if m.status in [MissionStatus.ACTIVE, MissionStatus.PENDING]]),
                             alerts, victim_snapshots, new_assignments)
            
            # Small delay between ticks
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
        land_all_drones(env)
    except Exception as e:
        logger.error(f"Unexpected error in simulation loop: {e}", exc_info=True)
        land_all_drones(env)
        return 1
    
    logger.info("Simulation completed successfully")
    return 0


if __name__ == '__main__':
    sys.exit(main())
