# RescueNet AI - Full Project Documentation

**Version:** 1.0 (Hackathon MVP)  
**Date:** March 2026  
**Owner:** @revailace  
**Status:** Active Development  

---

## 1. Project Overview

RescueNet AI is an intelligent multi-agent AI platform that serves as the central brain for entire fleets of drones and sensors.

**Main Purpose**  
In real disasters (earthquakes, floods, conflict zones, etc.), humans often panic and centralized command breaks down. RescueNet solves this by autonomously detecting survivors, analysing injuries in real time, performing dynamic triage, and coordinating multiple drone fleets simultaneously — without waiting for constant human instructions.

The system maintains continuous real-time awareness of its entire fleet. It constantly monitors every drone's battery levels, mechanical condition, sensor health, payload status, and environmental data through uplink checks. Using this live information, the AI makes smart and safe decisions.

It can instantly redirect resources: some drones survey affected areas, others deliver first-aid kits and supplies, while groups of heavy-lift drones collaborate to extract victims from rubble or floodwaters. It also provides calm, real-time two-way voice guidance to victims using NVIDIA PersonaPlex in local languages.

When lives are at stake, the AI takes the lead. Human oversight is available but not required for every decision.

When there is no active emergency, the same platform can be repurposed for infrastructure inspections, agriculture surveys, security monitoring, or other practical tasks. This keeps the fleets active and useful year-round.

---

## 2. Vision and Core Philosophy

- The AI is resource-aware and proactive.
- It has full self-awareness of every drone's capabilities and current state.
- Human oversight exists, but the system is designed to act independently when every second counts.
- We are building an intelligent commander, not just a delivery controller.
- Practical first: simulation MVP now, real hardware later.

---

## 3. High-Level Architecture

```mermaid
flowchart TD
    Dashboard["Ground Dashboard (Streamlit / Gradio)"] <-->|WebSocket / REST API| Core["RescueNet Core (Python + LangGraph)"]

    subgraph Core ["RescueNet Core Agents"]
        Coord[Coordinator / Supervisor Agent]
        Perc["Perception Agent (Vision + Acoustic)"]
        State["State & Resource Awareness Agent - CRITICAL"]
        Triage[Triage & Decision Agent]
        Voice["Voice Agent (NVIDIA PersonaPlex)"]
        Route[Routing & Resilience Agent]
        Sec[Security Agent]
        Action[Action Executor]
    end

    Core --> Sim["Simulation Environment (AirSim or Isaac Sim)"]

    subgraph Sim ["Simulation Layer"]
        Drones["Multiple heterogeneous drones (scout + heavy-lift)"]
        Sensors["Sensors: RGB, Thermal, LiDAR, Microphone, IMU"]
        Env["Dynamic environment (weather, terrain, jamming simulation)"]
    end
```

---

## 4. Detailed Agent Descriptions

### State and Resource Awareness Agent (CRITICAL)

- Maintains a live `FleetState` object updated every 1-2 seconds via uplink.
- Tracks for every drone: battery %, mechanical condition, sensor health, payload status, and environmental data (wind speed, precipitation, visibility, temperature).
- Provides intelligent helper functions like `can_perform_mission(drone_id, task_type, estimated_duration)` that return True/False with reasoning.
- Feeds live data to every other agent so all decisions are grounded in real fleet state.
- Prevents unsafe task assignments automatically, without needing explicit rules for every edge case.

### Perception Agent

- Processes RGB and thermal camera feeds.
- Detects people and estimates injury severity using pre-trained vision models.
- Acoustic detection (screams, voice, claps) with propeller noise cancellation.

### Triage and Decision Agent

- Uses perception data and fleet state to assign priority scores to victims.
- Decides optimal drone assignments based on proximity, payload, and battery.

### Coordinator / Supervisor Agent

- Oversees the entire agent graph.
- Handles re-tasking and conflict resolution between agents.
- Manages mode switching (Disaster vs Normal operations).

### Voice Agent

- Uses NVIDIA PersonaPlex for calm, natural, full-duplex two-way voice guidance.
- Generates contextual first-aid instructions based on triage output.
- Supports multiple languages (Nepali, English for MVP).

### Routing and Resilience Agent

- Primary navigation using standard flight paths.
- Falls back to Visual SLAM and LiDAR when GPS is lost.
- Handles jamming fallback: frequency hopping, then mesh networking between drones.
- Uses store-and-forward for data when all links are temporarily down.

### Security Agent

- Monitors continuously for signal jamming, spoofing, and anomalous commands.
- Manages encrypted communications on all links including fallback channels.
- Logs every critical action and state change for post-mission audit.

---

## 5. MVP Scope (What We Will Deliver)

### Must Have

- Simulation with 3-5 drones (mix of scout and heavy-lift types)
- Live fleet state monitoring (battery, condition, sensors, environmental data)
- Autonomous victim detection, triage scoring, and drone re-tasking
- One complete rescue scenario from scan to supply delivery
- Basic voice output (TTS first-aid instructions)
- Dashboard showing real-time drone statuses and AI decisions
- Mode switching (Disaster vs Normal)

### Nice to Have

- Two-way PersonaPlex voice (listen + respond)
- AI suggesting hardware adaptations based on environment analysis
- Simulated jamming scenario with mesh fallback demo
- Multi-drone collaborative extraction (4-5 drones working together on one victim)

---

## 6. Tech Stack

| Component | Choice |
|-----------|--------|
| Simulation | AirSim (recommended to start) or NVIDIA Isaac Sim |
| Multi-Agent Framework | LangGraph |
| Vision Models | YOLOv8 / CLIP + thermal processing |
| Voice | NVIDIA PersonaPlex API (or simulated TTS for MVP) |
| Dashboard | Streamlit or Gradio |
| Cloud | Vultr A100 / H100 instances ($250 credit per team member) |
| Language | Python 3.11+ |

---

## 7. Project Folder Structure

```text
rescuenet-ai/
├── agents/
│   ├── coordinator.py         # Supervisor agent - oversees full graph
│   ├── perception.py          # Vision + acoustic detection
│   ├── state_awareness.py     # CRITICAL - live fleet state + decision helpers
│   ├── triage.py              # Priority scoring + drone assignment
│   ├── voice.py               # PersonaPlex integration
│   ├── routing.py             # Navigation + jamming fallback
│   └── security.py            # Encryption, spoofing detection, audit logging
├── simulation/                # AirSim / Isaac Sim wrappers and helpers
├── state/                     # FleetState class + live update logic
├── dashboard/                 # Streamlit / Gradio frontend
├── utils/                     # Shared helpers, logging, config
├── config.py                  # Central configuration
├── main.py                    # Entry point - launches graph + simulation
├── requirements.txt
└── README.md
```

---

## 8. FleetState - Key Data Structure

```python
# state/fleet_state.py

@dataclass
class DroneState:
    drone_id: str
    battery_percent: float          # 0-100
    mechanical_health: str          # "ok" | "degraded" | "critical"
    sensor_status: dict             # {"rgb": "ok", "thermal": "ok", "lidar": "degraded"}
    payload_kg: float               # Current payload weight
    winch_status: str               # "ready" | "deployed" | "fault"
    position: tuple                 # (lat, lon, alt) or SLAM coords
    wind_speed_ms: float            # From onboard environmental sensor
    temperature_c: float
    visibility_m: float
    current_mission: str | None     # Current task ID or None

class FleetState:
    drones: dict[str, DroneState]

    def can_perform_mission(self, drone_id: str, task_type: str, estimated_duration_min: float) -> tuple[bool, str]:
        """
        Returns (True, "") if drone can take the mission.
        Returns (False, reason) if it cannot.
        Used by all agents before assigning any task.
        """
        ...

    def get_best_drone_for(self, task_type: str, location: tuple) -> str | None:
        """
        Returns drone_id of the best available drone for a given task and location.
        Considers battery, proximity, payload, and current load.
        """
        ...
```

---

## 9. Development Plan (3 Weeks)

### Week 1 - Foundation

- Set up AirSim environment with 3-5 drones
- Build `FleetState` class and State Awareness Agent
- Create basic Streamlit dashboard showing drone telemetry
- Set up LangGraph skeleton with placeholder agents

### Week 2 - Intelligence Layer

- Implement Perception Agent (victim detection via YOLOv8 + thermal)
- Build Triage and Decision Agent with priority scoring
- Add Coordinator with re-tasking logic based on fleet state
- Basic voice output (TTS first-aid instructions)

### Week 3 - Full Demo + Polish

- Wire up full rescue scenario end-to-end
- Add mode switching (Disaster vs Normal)
- Add Security Agent and simulated jamming fallback
- Dashboard polish and demo recording
- Prepare final presentation

---

## 10. Vultr Cloud Setup

- $250 credit per team member is more than enough for the hackathon.
- Spin up one shared A100 PCIe (40GB) instance for simulation (~$1.29-$2.40/hr).
- Each team member can use a smaller instance for code testing.
- Always stop instances when not actively running to conserve credits.
- Estimated total spend for 3 weeks of development: well under $200 per person.

---

## 11. Future Expansion (Post-Hackathon)

- Real hardware integration (NemoClaw, Unitree, custom drones)
- AI hardware suggestion feature: system analyses terrain and recommends physical adaptations to human operators (e.g. frame configuration changes for tight spaces)
- Full swarm behaviour with 20+ drones
- Post-mission analysis and learning loop
- API integration layer for third-party use cases (company incident monitoring, agriculture, security patrols)

---

## 12. Next Steps for the Team

1. Confirm this documentation matches our shared vision.
2. Set up the GitHub repo and add this file.
3. Quick call to assign agents and modules to team members.
4. Start with AirSim setup + FleetState class in parallel.
5. Ship.

---

*End of Document*
