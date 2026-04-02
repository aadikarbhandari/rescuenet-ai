# RescueNet AI
Autonomous disaster response drone coordination system powered by AI agents.

## Overview
RescueNet AI is a modular multi-agent AI platform that acts as the central command brain for fleets of drones and sensors. In disaster scenarios, the system analyses conditions in real time and coordinates multiple drone fleets simultaneously, executing decisions at scale while remaining under human supervision.

The system enables real-time victim detection, injury triage, coordinated multi-drone operations, and security monitoring. It integrates multi-sensor inputs and can coordinate physical actions such as supply delivery.

## Features
- **AI-Powered Triage** — Prioritizes victims using DeepSeek LLM with rule-based fallback scoring
- **Intelligent Dispatch** — Coordinates drone assignments based on victim severity, distance, and battery status
- **Real-Time Dashboard** — Streamlit-based UI showing live fleet status, victim locations, missions, and security alerts
- **REST API** — FastAPI server on port 8000 for external integrations and monitoring
- **Security Monitoring** — Detects GPS spoofing, signal jamming, and anomalous drone behavior
- **Dual Mode Operation** — Demo mode (mock environment) and AirSim mode (Unreal Engine simulation)
- **Mission Lifecycle** — Full cycle from victim discovery → triage → dispatch → en route → on scene → return to base → charging → idle

## System Architecture

```
Multi-Agent AI Layer
  ├── Coordinator Agent    — LLM-driven dispatch + rule-based fallback
  ├── Triage Agent         — Victim prioritization scoring
  ├── Security Agent       — GPS spoofing & jamming detection
  ├── State Awareness      — Fleet state management
  ├── Perception           — Vision/acoustic detection (stub)
  ├── Routing              — Navigation (stub)
  └── Voice                — NVIDIA PersonaPlex integration (stub)

Control & Integration Layer
  ├── Fleet State          — Drone & mission state management
  ├── FastAPI Server       — REST API on port 8000
  └── Streamlit Dashboard  — Real-time web UI on port 8501

Simulation Layer
  ├── Mock Environment     — Demo mode (no hardware required)
  └── AirSim Adapter       — Unreal Engine integration
```

## Repo Structure
```
rescuenet-ai/
├── agents/
│   ├── coordinator.py       # Drone dispatch & mission planning (LLM + rule-based)
│   ├── triage.py            # Victim prioritization scoring
│   ├── security.py          # GPS spoofing & jamming detection
│   ├── state_awareness.py   # Fleet state management
│   ├── perception.py        # Vision/acoustic detection (stub)
│   ├── routing.py           # Navigation (stub)
│   └── voice.py             # PersonaPlex integration (stub)
├── api/
│   └── server.py            # FastAPI REST server
├── config/
│   └── settings.py          # Configuration management
├── dashboard/
│   └── app.py               # Streamlit real-time dashboard
├── simulation/
│   ├── factory.py           # Environment factory
│   ├── environment.py       # Abstract environment interface
│   ├── mock_env.py          # Demo/mock environment
│   └── airsim_adapter/      # AirSim integration layer
├── state/
│   └── fleet_state.py       # Fleet & mission state management
└── main.py                  # Main entry point
```

## Setup

1. Clone the repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Key dependencies: `fastapi`, `uvicorn`, `streamlit`, `pandas`, `requests`, `openai`

3. Configure environment variables (optional — defaults are provided):

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek/Vultr inference API key | Built-in fallback |
| `DEEPSEEK_BASE_URL` | API endpoint | Vultr inference |
| `DEEPSEEK_MODEL` | Model name | DeepSeek-V3.2 |
| `RUNTIME_MODE` | `DEMO`, `AIRSIM`, or `SIM` | DEMO |
| `AIRSIM_IP` | AirSim simulator IP | AirSim mode only |
| `AIRSIM_PORT` | AirSim simulator port | AirSim mode only |

## Running Demo Mode

Demo mode uses a mock disaster environment — no AirSim or Unreal Engine required.

```bash
python main.py --mode demo --ticks 200
```

What happens:
- Initializes mock disaster scenario with 3 drones and 4 victims
- Drones discover victims and are dispatched via LLM or rule-based dispatch
- Full mission lifecycle: assigned → en route → on scene → returning → charging → idle
- Security agent monitors for GPS spoofing and signal jamming
- FastAPI server starts on port 8000

**API docs:** http://localhost:8000/docs

## Running the Dashboard

The dashboard is self-contained and runs its own simulation internally:

```bash
streamlit run dashboard/app.py
```

**Dashboard:** http://localhost:8501

Features:
- Live fleet status with battery levels and positions
- Active mission tracking
- Victim triage panel with severity scoring
- Security alert monitoring
- Manual step and reset controls

To run both simultaneously:
```bash
# Terminal 1 - Backend simulation
python main.py --mode demo --ticks 9999 &

# Terminal 2 - Dashboard
streamlit run dashboard/app.py
```

## Running AirSim Mode

1. Start AirSim in Unreal Engine

2. Configure and run:
```bash
export RUNTIME_MODE=AIRSIM
export AIRSIM_IP=127.0.0.1
export AIRSIM_PORT=41451
export DEEPSEEK_API_KEY=your_api_key
python main.py --mode airsim
```

## Troubleshooting

**Triage/dispatch falls back to rule-based mode**
Ensure `DEEPSEEK_API_KEY` is set and the API endpoint is reachable.

**Import errors**
Run from the project root directory, not from a subdirectory.

**Port already in use**
Run `pkill -f "python main.py"` to kill any existing instances.

## Known Limitations
- **Perception/Routing/Voice** — stub modules pending implementation
- **Thread Safety** — Global state in the API server is not thread-safe under concurrent load
- **No Authentication** — API endpoints are publicly accessible
- **AirSim Integration** — Full drone command execution requires Unreal Engine + GPU setup
