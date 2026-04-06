"""_summary_

Connect the State Awareness Agent to the system entry point and start live fleet monitoring

This file serves as the main entry point for the RescueNet AI backend. 
It initializes the State Awareness Agent, which connects to AirSim, detects all drones, and continuously updates the FleetState with real-time telemetry data. 
The agent runs in a background thread, allowing it to maintain an up-to-date view of the fleet's status while other agents (Coordinator, Triage, Routing) can query it for decision-making.

"""

from agents.state_awareness import StateAwarenessAgent
import time


def main():
    print("Starting RescueNet AI...")

    # Start the simulation connection and continuously monitor the drones’ state:
    state_agent = StateAwarenessAgent(update_interval=2.0)
    state_agent.start()

    print("State Awareness Agent running...")

    try:
        while True:
            fleet_state = state_agent.get_fleet_state()

            print("\n--- Fleet Status ---")

            for drone in fleet_state.get_all_drones():
                print(
                    f"{drone.drone_id} | "
                    f"Battery: {drone.battery_percent:.1f}% | "
                    f"Position: {drone.position} | "
                    f"Mission: {drone.current_mission}"
                )

            time.sleep(5)
    except KeyboardInterrupt:
        print("\nShutting down...")
        state_agent.stop()



if __name__ == "__main__":
    main()


