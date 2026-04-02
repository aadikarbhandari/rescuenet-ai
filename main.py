#!/usr/bin/env python3
"""
RescueNet AI - Main Entry Point
Autonomous disaster response multi-agent system
"""
import argparse
import logging
import sys
import time
from typing import List, Dict, Any

from config.settings import load_settings
from simulation.factory import SimulationFactory
from state.fleet_state import FleetState
from agents.triage import TriageAgent
from agents.coordinator import CoordinatorAgent
from agents.security import SecurityAgent
from api.server import run_server_background, update_state


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
    busy = sum(1 for d in fleet.drones.values() if d.status == 'BUSY' or (hasattr(d.status, 'value') and d.status.value == 'BUSY'))
    charging = sum(1 for d in fleet.drones.values() if d.status == 'CHARGING' or (hasattr(d.status, 'value') and d.status.value == 'CHARGING'))
    
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
            
            # Security scan
            alerts = security_agent.scan_all(telemetry)
            if alerts:
                logger.info(f"Security scan found {len(alerts)} alerts")
            
            # Get current victims from environment
            victim_snapshots = env.get_victim_snapshots()
            
            # Update fleet victims
            for vs in victim_snapshots:
                victim_id = vs.get('victim_id')
                if victim_id:
                    fleet.update_victim(vs)
            
            # Triage: prioritize victims
            triage_results = triage_agent.prioritize_all(victim_snapshots)
            
            # Coordinator: decide dispatch
            assignments = coordinator.decide_dispatch(triage_results)
            
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
                'stats': {
                    'tick': tick,
                    'available_drones': len(fleet.get_available_drones()),
                    'active_missions': len([m for m in fleet.missions.values() 
                                           if m.status in ['ACTIVE', 'PENDING'] or (hasattr(m.status, 'value') and m.status.value in ['ACTIVE', 'PENDING'])]),
                    'completed_missions': len(completed)
                }
            }
            update_state(state_update)
            
            # Print summary
            print_tick_summary(tick, fleet, len([m for m in fleet.missions.values() 
                                                  if m.status in ['ACTIVE', 'PENDING'] or (hasattr(m.status, 'value') and m.status.value in ['ACTIVE', 'PENDING'])]),
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
