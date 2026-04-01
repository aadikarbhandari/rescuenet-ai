"""
RescueNet AI - Main simulation loop.

This is the primary entry point for running RescueNet AI simulations.
Supports multiple runtime modes for different use cases.

Usage:
  python main.py --mode demo --ticks 10      # Run demo mode for 10 ticks
  python main.py --mode sim --ticks 5        # Run sim mode for 5 ticks
  python main.py --help                      # Show all options

Environment variables:
  RESCUENET_MODE=demo|sim                    # Set runtime mode
  RESCUENET_LOG_LEVEL=INFO|DEBUG|WARNING     # Set logging level
  RESCUENET_MOCK_SEED=42                     # Set random seed for demo mode

Configuration file:
  config.json                                # JSON config file (optional)
"""
import sys
import argparse
import logging
sys.path.append('.')  # ensure local imports work

from state.fleet_state import FleetState, VictimState
from agents.state_awareness import StateAwarenessAgent
from agents.triage import TriageAgent, TriageVictim
from agents.coordinator import CoordinatorAgent
from config import get_settings, RuntimeMode
from simulation.factory import create_environment

def setup_logging(log_level: str = "INFO"):
    """Configure logging for RescueNet AI."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

def print_startup_banner(settings):
    """Print informative startup banner."""
    print("=" * 60)
    print("🚁 RESCUENET AI - AUTONOMOUS DISASTER RESPONSE SYSTEM")
    print("=" * 60)
    print(f"Runtime Mode: {settings.mode.value.upper()}")
    
    if settings.mode == RuntimeMode.DEMO:
        print(f"  • Using mock environment with seed={settings.mock_seed}")
        print(f"  • {settings.mock_num_drones} drones, {settings.mock_num_victims} victims")
        print(f"  • Perfect for testing and development")
    elif settings.mode == RuntimeMode.SIM:
        print(f"  • Using AirSim environment at {settings.airsim_host}:{settings.airsim_port}")
        print(f"  • Requires AirSim simulator running")
        print(f"  • For production simulation workflows")
    
    print(f"Log Level: {settings.log_level}")
    print("-" * 60)

def main():
    parser = argparse.ArgumentParser(
        description='RescueNet AI - Autonomous disaster response system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode demo --ticks 10      # Run demo mode for 10 ticks
  python main.py --mode sim --ticks 5        # Run sim mode for 5 ticks
  python main.py --mode demo                 # Run demo mode with default 5 ticks
  
Environment variables:
  RESCUENET_MODE=demo|sim                    # Set runtime mode
  RESCUENET_LOG_LEVEL=INFO|DEBUG|WARNING     # Set logging level
  RESCUENET_MOCK_SEED=42                     # Set random seed for demo mode
  
Configuration file (config.json):
  {
    "mode": "demo",
    "mock_seed": 42,
    "mock_num_drones": 3,
    "mock_num_victims": 4,
    "log_level": "INFO"
  }
        """
    )
    parser.add_argument('--ticks', type=int, default=5, 
                       help='Number of simulation ticks to run (default: 5)')
    parser.add_argument('--mode', type=str, choices=['demo', 'sim'], 
                       help='Runtime mode: "demo" for mock environment, "sim" for AirSim')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging (DEBUG level)')
    args = parser.parse_args()
    
    # Get configuration settings
    settings = get_settings(mode_arg=args.mode)
    
    # Override log level if verbose flag is set
    if args.verbose:
        settings.log_level = "DEBUG"
    
    # Setup logging
    logger = setup_logging(settings.log_level)
    
    # Print startup banner
    print_startup_banner(settings)
    logger.info(f"Starting RescueNet AI simulation with mode={settings.mode.value}")
    logger.info(f"Configuration: {settings}")

    # 1. Initialize environment using factory
    logger.info(f"Creating {settings.mode.value} environment...")
    try:
        env = create_environment(settings)
        logger.info(f"Environment created: {type(env).__name__}")
    except Exception as e:
        logger.error(f"Failed to create environment: {e}")
        print(f"\n❌ ERROR: Failed to initialize {settings.mode.value} environment")
        print(f"   Reason: {e}")
        if settings.mode == RuntimeMode.SIM:
            print(f"   Try running with: python main.py --mode demo")
            print(f"   Or check that AirSim is running at {settings.airsim_host}:{settings.airsim_port}")
        sys.exit(1)
    
    # Get initial state info (environment-specific)
    drone_snapshots = env.get_drone_snapshots()
    victim_snapshots = env.get_victim_snapshots()
    
    print(f"\n✅ Environment initialized: {settings.mode.value.upper()} mode")
    print(f"   • Drones: {len(drone_snapshots)}")
    print(f"   • Victims: {len(victim_snapshots)}")
    if settings.mode == RuntimeMode.DEMO:
        print(f"   • Random seed: {settings.mock_seed}")
    elif settings.mode == RuntimeMode.SIM:
        if hasattr(env, '_adapter_connected'):
            status = "✅ Connected" if env._adapter_connected else "⚠️  Not connected"
            print(f"   • AirSim adapter: {status}")
    print()

    # 2. Create FleetState
    fleet = FleetState()
    logger.info("Created FleetState")
    print("✅ Fleet state initialized")

    # 3. Create agents
    state_agent = StateAwarenessAgent(fleet)
    triage_agent = TriageAgent()
    coordinator = CoordinatorAgent(fleet)
    logger.info("Created agents: StateAwareness, Triage, Coordinator")
    print("✅ AI agents initialized: StateAwareness, Triage, Coordinator")
    print()

    # 4. Run simulation for several ticks
    total_ticks = args.ticks
    all_assignments = []
    
    print(f"\n{'='*60}")
    print(f"🚀 STARTING SIMULATION: {total_ticks} ticks")
    print(f"{'='*60}")
    logger.info(f"Starting simulation with {total_ticks} ticks")

    for tick in range(1, total_ticks + 1):  # Start at 1 to match env.tick
        print(f"\n{'─'*40}")
        print(f"📈 TICK {tick}/{total_ticks}")
        print(f"{'─'*40}")
        logger.info(f"Starting tick {tick}/{total_ticks}")

        # Step the environment
        try:
            env.step()
            logger.debug(f"Environment stepped to tick {env.tick}")
            print(f"✅ Environment advanced to tick {env.tick}")
        except Exception as e:
            logger.error(f"Failed to step environment: {e}")
            print(f"❌ Failed to step environment: {e}")
            if settings.mode == RuntimeMode.SIM:
                print(f"   AirSim connection may have been lost")
            break
        
        # Check for completed missions and update FleetState
        completed_missions = env.get_completed_missions()
        if completed_missions:
            logger.info(f"Found {len(completed_missions)} completed mission(s)")
            for mission_id in completed_missions:
                if fleet.complete_assignment(mission_id, current_tick=tick):
                    print(f"✅ Mission {mission_id} completed")
                else:
                    print(f"⚠️  Mission {mission_id} not found in FleetState")
        else:
            logger.debug("No completed missions this tick")

        # Get raw drone data and ingest into fleet state
        raw_drones = env.get_drone_snapshots()
        state_agent.ingest_raw_drone_data(raw_drones)
        logger.debug(f"Ingested {len(raw_drones)} drone snapshots")
        print(f"📊 Drone data: {len(raw_drones)} snapshots ingested")
        
        # Sync mission phases with drone operational status
        fleet.sync_mission_phases_from_drones(current_tick=tick)

        # Get victim snapshots and convert to VictimState objects
        raw_victims = env.get_victim_snapshots()
        victim_objs = []
        for v in raw_victims:
            vs = VictimState(
                victim_id=v["victim_id"],
                position=v["position"],
                injury_severity=v["injury_severity"],
                detected_by=v.get("detected_by", "none"),
                first_detected_tick=v.get("first_detected_tick", 0),
                detection_confidence=v.get("detection_confidence", 0.0),
                assigned_drone=v.get("assigned_drone"),
                mission_id=v.get("mission_id"),
                cooldown_until_tick=v.get("cooldown_until_tick", 0),
                conscious=v.get("conscious", True),
                bleeding=v.get("bleeding", "none"),
                body_temperature_c=v.get("body_temperature_c", 37.0),
                accessibility=v.get("accessibility", 0.5)
            )
            victim_objs.append(vs)
            fleet.add_or_update_victim(vs)
        
        # Count victims by status
        detected_count = sum(1 for v in victim_objs if v.is_detected)
        confirmed_count = sum(1 for v in victim_objs if v.is_confirmed)
        assigned_count = sum(1 for v in victim_objs if v.is_assigned)
        logger.info(f"Victim states: {len(victim_objs)} total, {detected_count} detected, {confirmed_count} confirmed, {assigned_count} assigned")
        print(f"👥 Victim status: {detected_count} detected, {confirmed_count} confirmed, {assigned_count} assigned")

        # Compute fleet readiness
        readiness = state_agent.compute_fleet_readiness_summary()
        logger.info(f"Fleet readiness: {readiness['available_drones']}/{readiness['total_drones']} drones available")
        print(f"🚁 Fleet readiness: {readiness['available_drones']}/{readiness['total_drones']} drones available")

        # Triage victims (only detected victims)
        triage_results = triage_agent.triage_from_victim_states(victim_objs)
        if triage_results:
            logger.info(f"Triage completed: {len(triage_results)} victims prioritized")
            print(f"🏥 Triage: {len(triage_results)} victims prioritized")
            # Show top 3 with emoji indicators
            for i, (victim_id, score, reason) in enumerate(triage_results[:3], 1):
                if score > 70:
                    emoji = "🔴"
                elif score > 40:
                    emoji = "🟠"
                elif score > 20:
                    emoji = "🟡"
                else:
                    emoji = "🟢"
                print(f"   {emoji} {victim_id}: {score:.1f} - {reason}")
            if len(triage_results) > 3:
                print(f"   ... and {len(triage_results) - 3} more")
        else:
            logger.debug("No victims to triage")
            print("🏥 Triage: No victims to prioritize")

        # Assign missions via coordinator
        assignments = coordinator.assign_missions(victim_objs, env.tick)
        all_assignments.extend(assignments)
        if assignments:
            logger.info(f"Coordinator created {len(assignments)} new mission(s)")
            print(f"🎯 Coordinator: {len(assignments)} new mission(s) created")
            for assignment in assignments:
                print(f"   • {assignment.mission_id}: {assignment.drone_id} → {assignment.victim_id or 'patrol'}")
        else:
            logger.debug("No new missions assigned this tick")
            print("🎯 Coordinator: No new missions assigned")
        
        # Update environment with new mission assignments
        for assignment in assignments:
            if assignment.victim_id:
                env.update_victim_assignment(assignment.victim_id, assignment.drone_id, assignment.mission_id)
            env.update_drone_mission(assignment.drone_id, assignment.mission_id)

        # Print current assignments summary
        active_missions = [ass for ass in fleet.assignments.values() if ass.status in ("pending", "active")]
        if active_missions:
            logger.info(f"{len(active_missions)} active mission(s)")
            print(f"📋 Active missions: {len(active_missions)}")
            for ass in active_missions[:3]:  # Show top 3
                print(f"   • {ass.mission_id}: {ass.drone_id} → {ass.victim_id} ({ass.task_type})")
            if len(active_missions) > 3:
                print(f"   ... and {len(active_missions) - 3} more")
        else:
            logger.debug("No active missions")
            print("📋 Active missions: None")

    # 5. Final summary
    print(f"\n{'='*60}")
    print("🎉 SIMULATION COMPLETE")
    print(f"{'='*60}")
    logger.info(f"Simulation completed: {total_ticks} ticks, {len(fleet.assignments)} missions")
    print(f"📊 Simulation Summary:")
    print(f"   • Ticks simulated: {total_ticks}")
    print(f"   • Total missions: {len(fleet.assignments)}")
    print(f"   • Runtime mode: {settings.mode.value.upper()}")
    print()

    # Fleet readiness final
    final_readiness = state_agent.compute_fleet_readiness_summary()
    print(f"🚁 Final Fleet Status:")
    print(f"   • Drones total: {final_readiness['total_drones']}")
    print(f"   • Drones available: {final_readiness['available_drones']}")
    print(f"   • Average battery: {final_readiness['avg_battery']:.1f}%")
    
    # Operational status indicator
    operational_pct = final_readiness['operational_percent']
    if operational_pct > 75:
        status_emoji = "🟢"
    elif operational_pct > 50:
        status_emoji = "🟡"
    elif operational_pct > 25:
        status_emoji = "🟠"
    else:
        status_emoji = "🔴"
    print(f"   • Operational: {status_emoji} {operational_pct:.1f}%")
    print()

    # Mission breakdown
    status_counts = {}
    for ass in fleet.assignments.values():
        status_counts[ass.status] = status_counts.get(ass.status, 0) + 1
    
    if status_counts:
        print(f"📋 Mission Status Breakdown:")
        for status, count in sorted(status_counts.items()):
            if status == "completed":
                emoji = "✅"
            elif status == "active":
                emoji = "🟡"
            elif status == "pending":
                emoji = "🟠"
            elif status == "failed":
                emoji = "🔴"
            else:
                emoji = "⚪"
            print(f"   • {emoji} {status}: {count}")
    else:
        print(f"📋 Mission Status: No missions created")
    print()

    # Victim assignment summary
    assigned_victims = [v for v in fleet.victims.values() if v.assigned_drone is not None]
    victims_in_cooldown = [v for v in fleet.victims.values() if v.cooldown_until_tick > env.tick]
    
    print(f"👥 Victim Assignment Summary:")
    print(f"   • Total victims: {len(fleet.victims)}")
    print(f"   • Assigned to drones: {len(assigned_victims)}")
    
    if assigned_victims:
        print(f"   • Assigned victims:")
        for v in assigned_victims[:5]:  # Show first 5
            print(f"     - {v.victim_id} → drone {v.assigned_drone} (mission {v.mission_id})")
        if len(assigned_victims) > 5:
            print(f"     ... and {len(assigned_victims) - 5} more")
    
    if victims_in_cooldown:
        print(f"   • Victims in cooldown: {len(victims_in_cooldown)}")
        for v in victims_in_cooldown[:3]:  # Show first 3
            remaining = v.cooldown_until_tick - env.tick
            print(f"     - {v.victim_id}: {remaining} tick(s) remaining")
        if len(victims_in_cooldown) > 3:
            print(f"     ... and {len(victims_in_cooldown) - 3} more")
    print()
    
    # Drone status summary
    print(f"🚁 Individual Drone Status:")
    for drone_id, drone in fleet.drones.items():
        # Status indicator
        if drone.operational_status == "available":
            status_emoji = "🟢"
        elif drone.operational_status in ["assigned", "en_route", "on_scene"]:
            status_emoji = "🟡"
        elif drone.operational_status == "returning":
            status_emoji = "🔵"
        elif drone.operational_status == "maintenance":
            status_emoji = "🟠"
        else:
            status_emoji = "⚪"
        
        # Battery indicator
        if drone.battery_percent < 10.0:
            battery_emoji = "🔴"
        elif drone.battery_percent < 20.0:
            battery_emoji = "🟠"
        elif drone.battery_percent < 50.0:
            battery_emoji = "🟡"
        else:
            battery_emoji = "🟢"
        
        # Mission info
        mission_info = ""
        if drone.current_mission:
            mission_info = f" | Mission: {drone.current_mission}"
        
        print(f"   • {status_emoji} {drone_id}: {drone.operational_status}{mission_info}")
        print(f"     {battery_emoji} Battery: {drone.battery_percent:.1f}% | Health: {drone.mechanical_health}")

    print(f"\n{'='*60}")
    print("🏁 RESCUENET AI SIMULATION END")
    print(f"{'='*60}")
    logger.info("RescueNet AI simulation ended successfully")

if __name__ == "__main__":
    main()
