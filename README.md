# RescueNet AI
**Autonomous multi-agent drone platform for disaster response.**

---

## What it does
RescueNet AI coordinates autonomous drone fleets to locate, triage, and rescue victims in dynamic disaster environments. It uses a multi-agent LangGraph pipeline to handle real-time decision-making:
- **Perception**: YOLOv8/CLIP for victim detection.
- **Triage**: `TriageAgent` scores victims (0-100) based on injury severity, vitals (bleeding, consciousness, temperature), and accessibility.
- **Coordination**: `CoordinatorAgent` assigns missions by matching high-priority victims with available drones (battery, location).
- **Simulation**: Supports AirSim for production and a deterministic `MockDisasterEnv` for development.

## Architecture
- **Core**: `main.py` drives the tick-based simulation loop.
- **Multi-Agent System**:
    - `StateAwarenessAgent`: Ingests drone telemetry, computes fleet readiness.
    - `TriageAgent`: Prioritizes victims using medical heuristics.
    - `CoordinatorAgent`: Manages mission assignment and lifecycle.
- **State**: `FleetState` tracks drones/missions; `VictimState` tracks victim status.
- **Stack**: Python, LangGraph, YOLOv8/CLIP, AirSim (mock fallback), Streamlit.

## Quick Start
```bash
# Run demo mode (Mock environment)
python main.py --mode demo --ticks 10

# Run simulation mode (requires AirSim)
python main.py --mode sim --ticks 5
```

## Team
**AR26 HackXelerator Berlin** — Mission Two: Autonomous Systems and Embodied AI.