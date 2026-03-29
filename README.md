# RNA

# RescueNet AI - Full Project Documentation

**Version:** 1.0 (Hackathon MVP)  
**Date:** March 2026  
**Owner:** @revailace  
**Status:** Forming → Active Development  

---

## 1. Project Overview (Simple Version)

RescueNet AI is **one intelligent multi-agent AI brain** that controls entire fleets of drones and sensors.

**Main Purpose**  
In real disasters (earthquakes, floods, landslides, conflict zones), humans panic and centralized command collapses. RescueNet steps in as the calm, autonomous commander. It detects survivors, analyses injuries, decides priorities, coordinates multiple drone fleets in real time, delivers supplies, extracts victims when possible, and gives voice guidance — all without waiting for constant human input.

**Key Intelligence Feature**  
The AI maintains **full real-time awareness** of every drone in the fleet:
- Battery percentage
- Mechanical condition / damage
- Sensor health
- Payload and winch status
- Environmental data (wind, rain, temperature, visibility)

It uses this information to make smart, safe decisions automatically (e.g. never sending a low-battery drone on a long critical mission).

**When no emergency**  
The same platform is easily repurposed for daily tasks (infrastructure inspection, agriculture monitoring, security patrols, vlogging rentals, etc.). This keeps the system active and useful year-round.

---

## 2. Vision & Core Philosophy

- The AI is **resource-aware and proactive**, not reactive.
- Human oversight exists but is **not required** for every decision when lives are at stake.
- The system must be **practical** — it works in simulation now and can scale to real hardware later.
- We are building an **intelligent commander**, not just another delivery drone controller.

---

## 3. High-Level Architecture
Ground Dashboard (Streamlit/Gradio)
↑↓ WebSocket / REST API
RescueNet Core (Python + LangGraph)
├── Coordinator / Supervisor Agent
├── Perception Agent (Vision + Acoustic)
├── State & Resource Awareness Agent   ← CRITICAL
├── Triage & Decision Agent
├── Voice Agent (NVIDIA PersonaPlex)
├── Routing & Resilience Agent
├── Security Agent
└── Action Executor
Simulation Environment (AirSim or Isaac Sim)
├── Multiple heterogeneous drones (scout + heavy-lift)
├── Sensors (RGB, Thermal, LiDAR, Microphone, IMU)
└── Dynamic environment (weather, terrain, jamming simulation)
text---

## 4. Detailed Agent Descriptions

### 4.1 State & Resource Awareness Agent (Most Important)
- Maintains a live `FleetState` object (updated every 1–2 seconds via uplink).
- Tracks for **every drone**:
  - Battery % + estimated flight time remaining
  - Mechanical health flags (damage level)
  - Sensor status (working / degraded / offline)
  - Current payload weight and winch status
  - Environmental readings (wind speed, precipitation, visibility, temperature)
- Provides helper functions such as `can_perform_mission(drone_id, task_type, estimated_duration)` → returns True/False + reasoning.
- Feeds live data to every other agent so decisions are always realistic.

### 4.2 Perception Agent
- Processes RGB + thermal camera feeds.
- Detects people, estimates injury severity (basic classification for MVP).
- Acoustic detection (screams, claps, voice) with propeller noise cancellation.

### 4.3 Triage & Decision Agent
- Uses Perception + State data to assign priority scores to victims.
- Decides optimal drone assignments.

### 4.4 Coordinator / Supervisor Agent
- Oversees the whole graph.
- Decides when to switch modes (disaster vs normal).
- Handles re-tasking and conflict resolution.

### 4.5 Voice Agent
- Uses NVIDIA PersonaPlex for calm, natural two-way voice in local languages.
- Generates first-aid instructions based on triage.

### 4.6 Routing & Resilience Agent
- Handles navigation (Visual SLAM + LiDAR when GPS lost).
- Manages frequency hopping / mesh fallback on jamming.

### 4.7 Security Agent
- Monitors for spoofing, jamming, encryption.
- Logs all actions for audit.

---

## 5. MVP Scope (What We Must Deliver)

**Core Demo (Must Work)**
- 3–5 simulated drones (mix of scout and heavy-lift)
- Live fleet state dashboard showing battery, condition, sensors
- One complete rescue scenario:
  - Scan area → detect victim → triage → assign drones → deliver supplies → voice guidance
- Automatic re-tasking based on battery / condition
- Simple mode switch (Disaster ↔ Normal)
- Basic jamming / GPS-denied simulation

**Stretch Goals (Nice to Have)**
- Two-way PersonaPlex voice
- AI suggesting hardware adaptation (e.g. “Recommend rotating frame for ground mode”)
- Security Agent demo (jamming → mesh fallback)

---

## 6. Tech Stack (Simulation-First)

- **Simulation**: AirSim (recommended for speed) or NVIDIA Isaac Sim
- **Multi-Agent**: LangGraph (latest version)
- **Vision**: YOLOv8 / CLIP + simple thermal processing
- **Voice**: NVIDIA PersonaPlex API (or simulated TTS for MVP)
- **Dashboard**: Streamlit (fast) or Gradio
- **Cloud**: Vultr A100 / H100 instances (we have $250 credit per team member)
- **Language**: Python 3.11+

---

## 7. Recommended Folder Structure
rescuenet-ai/
├── agents/                  # All LangGraph agents
│   ├── coordinator.py
│   ├── perception.py
│   ├── state_awareness.py     ← Very important
│   ├── triage.py
│   ├── voice.py
│   ├── routing.py
│   └── security.py
├── simulation/              # AirSim / Isaac Sim wrappers
├── state/                   # FleetState class + live updates
├── dashboard/               # Streamlit app
├── utils/                   # Helpers, logging, config
├── config.py
├── main.py                  # Entry point to launch graph + simulation
├── requirements.txt
└── README.md
text---

## 8. Step-by-Step Development Plan (3 Weeks)

**Week 1**
- Set up AirSim + basic drone control
- Build `FleetState` and State & Resource Awareness Agent
- Create simple dashboard showing drone telemetry

**Week 2**
- Implement Perception + Triage agents
- Add Coordinator that can re-task drones based on state
- Basic voice output

**Week 3**
- Full scenario demo + mode switching
- Polish dashboard + add security/jamming simulation
- Prepare presentation & recording

---

## 9. How to Use Vultr Credits

- Spin up **one shared A100** instance for heavy simulation.
- Each team member can have their own smaller instance for local testing.
- Always shut down instances when not in use.
- We have more than enough credit.

---

## 10. Future Expansion Ideas (Post-Hackathon)

- Real hardware integration (NemoClaw / Unitree / custom drones)
- Hardware adaptation suggestions (frame rotation, etc.)
- Multi-language voice with PersonaPlex
- Full swarm behaviour with 20+ drones
- Post-mission analysis & learning loop

---

**Next Steps for the Team**

1. Confirm this documentation matches our vision.
2. Jump on a quick call to assign agents / modules.
3. Start by forking a repo and setting up the basic AirSim + LangGraph skeleton.

We are building something genuinely intelligent and useful. Let's ship it.

---

**End of Document**
