"""
RescueNet AI - Main simulation loop.
"""
import sys
sys.path.append('.')  # ensure local imports work

from simulation.mock_env import MockDisasterEnv
from state.fleet_state import FleetState, VictimState
from agents.state_awareness import StateAwarenessAgent
from agents.triage import TriageAgent, TriageVictim
from agents.coordinator import CoordinatorAgent

def main():
    print("=== RescueNet AI Simulation Start ===")
    print()

    # 1. Initialize mock environment
    env = MockDisasterEnv(seed=42)
    print(f"Initialized mock environment with {len(env.drones)} drones, {len(env.victims)} victims.")
    print()

    # 2. Create FleetState
    fleet = FleetState()
    print("Created empty FleetState.")
    print()

    # 3. Create agents
    state_agent = StateAwarenessAgent(fleet)
    triage_agent = TriageAgent()
    coordinator = CoordinatorAgent(fleet)
    print("Agents created: StateAwareness, Triage, Coordinator.")
    print()

    # 4. Run simulation for several ticks
    total_ticks = 5
    all_assignments = []

    for tick in range(1, total_ticks + 1):  # Start at 1 to match env.tick
        print(f"\n--- Tick {tick} ---")

        # Step the environment
        env.step()
        print(f"Environment stepped (tick={env.tick}).")
        
        # Check for completed missions and update FleetState
        completed_missions = env.get_completed_missions()
        for mission_id in completed_missions:
            if fleet.complete_assignment(mission_id):
                print(f"[Main] Mission {mission_id} marked as completed in FleetState")
            else:
                print(f"[Main] Warning: Mission {mission_id} not found in FleetState")

        # Get raw drone data and ingest into fleet state
        raw_drones = env.get_drone_snapshots()
        state_agent.ingest_raw_drone_data(raw_drones)
        print(f"Ingested {len(raw_drones)} drone snapshots.")

        # Get victim snapshots and convert to VictimState objects
        raw_victims = env.get_victim_snapshots()
        victim_objs = []
        for v in raw_victims:
            vs = VictimState(
                victim_id=v["victim_id"],
                position=v["position"],
                injury_severity=v["injury_severity"],
                detected_by=v["detected_by"],
                assigned_drone=v["assigned_drone"],
                mission_id=v["mission_id"],
                cooldown_until_tick=v.get("cooldown_until_tick", 0)
            )
            victim_objs.append(vs)
            fleet.add_or_update_victim(vs)
        print(f"Updated {len(victim_objs)} victim states.")

        # Compute fleet readiness
        readiness = state_agent.compute_fleet_readiness_summary()
        print(f"Fleet readiness: {readiness['available_drones']}/{readiness['total_drones']} drones available.")

        # Triage victims
        triage_input = []
        for v in victim_objs:
            # Convert VictimState to TriageVictim (requires extra fields from raw)
            raw = next(rv for rv in raw_victims if rv["victim_id"] == v.victim_id)
            tv = TriageVictim(
                victim_id=v.victim_id,
                severity=v.injury_severity,
                conscious=raw["conscious"],
                bleeding=raw["bleeding"],
                body_temperature_c=raw["body_temperature_c"],
                accessibility=raw["accessibility"],
                position=v.position
            )
            triage_input.append(tv)

        triage_results = triage_agent.prioritize_victims(triage_input)
        print("Triage results (top 3):")
        for victim, score, reason in triage_results[:3]:
            print(f"  {victim.victim_id}: {score:.1f} - {reason}")

        # Assign missions via coordinator
        assignments = coordinator.assign_missions(victim_objs, env.tick)
        all_assignments.extend(assignments)
        print(f"Coordinator created {len(assignments)} new mission(s) this tick.")
        
        # Update environment with new mission assignments
        for assignment in assignments:
            if assignment.victim_id:
                env.update_victim_assignment(assignment.victim_id, assignment.drone_id, assignment.mission_id)
            env.update_drone_mission(assignment.drone_id, assignment.mission_id)

        # Print current assignments
        if fleet.assignments:
            print("Active missions:")
            for mid, ass in fleet.assignments.items():
                if ass.status in ("pending", "active"):
                    print(f"  {mid}: drone {ass.drone_id} -> victim {ass.victim_id} ({ass.task_type})")
        else:
            print("No active missions.")

    # 5. Final summary
    print("\n" + "="*50)
    print("SIMULATION COMPLETE")
    print("="*50)
    print(f"Total ticks simulated: {total_ticks}")
    print(f"Total missions created: {len(fleet.assignments)}")
    print()

    # Fleet readiness final
    final_readiness = state_agent.compute_fleet_readiness_summary()
    print("Final fleet readiness:")
    print(f"  Drones total: {final_readiness['total_drones']}")
    print(f"  Drones available: {final_readiness['available_drones']}")
    print(f"  Average battery: {final_readiness['avg_battery']}%")
    print(f"  Operational: {final_readiness['operational_percent']}%")
    print()

    # Mission breakdown
    status_counts = {}
    for ass in fleet.assignments.values():
        status_counts[ass.status] = status_counts.get(ass.status, 0) + 1
    print("Mission status breakdown:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    print()

    # Victim assignment summary
    assigned_victims = [v for v in fleet.victims.values() if v.assigned_drone is not None]
    victims_in_cooldown = [v for v in fleet.victims.values() if v.cooldown_until_tick > env.tick]
    
    print(f"Victims assigned to a drone: {len(assigned_victims)}/{len(fleet.victims)}")
    for v in assigned_victims:
        print(f"  {v.victim_id} -> drone {v.assigned_drone} (mission {v.mission_id})")
    
    if victims_in_cooldown:
        print(f"\nVictims in cooldown ({len(victims_in_cooldown)}):")
        for v in victims_in_cooldown:
            print(f"  {v.victim_id}: cooldown until tick {v.cooldown_until_tick} (current: {env.tick})")
    
    # Drone status summary
    print(f"\nDrone status:")
    for drone_id, drone in fleet.drones.items():
        status = "available"
        if drone.current_mission is not None:
            status = f"on mission {drone.current_mission}"
        elif drone.battery_percent < 10.0:
            status = "low battery"
        elif drone.mechanical_health == "critical":
            status = "critical health"
        elif drone.sensor_status.get("rgb") != "ok" or drone.sensor_status.get("lidar") != "ok":
            status = "sensor issues"
        print(f"  {drone_id}: {status}, battery={drone.battery_percent:.1f}%, health={drone.mechanical_health}")

    print("\n=== RescueNet AI Simulation End ===")

if __name__ == "__main__":
    main()
