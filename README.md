# RescueNet AI
Autonomous disaster response drone coordination system powered by AI agents.

## Overview
RescueNet AI is an intelligent disaster response platform that coordinates a fleet of rescue drones to locate, prioritize, and assist victims during emergency situations. The system uses AI agents for victim triage, mission planning, drone dispatch, and security monitoring — with DeepSeek LLM as the primary decision engine and rule-based fallback for resilience.

## Features
- **AI-Powered Triage** — Prioritizes victims using DeepSeek LLM with rule-based fallback scoring
- **Intelligent Dispatch** — Coordinates drone assignments based on victim severity, distance, and battery status
- **Real-Time Dashboard** — Streamlit-based UI showing fleet status, victim locations, and mission progress
- **REST API** — FastAPI server on port 8000 for external integrations and monitoring
- **Security Monitoring** — Detects GPS spoofing, signal jamming, and anomalous drone behavior
- **Dual Mode Operation** — Demo mode (mock environment) and AirSim mode (Unreal Engine simulation)

## Repo Structure
```
rescuenet-ai/
├── agents/                    # AI agent modules
│   ├── coordinator.py         # Drone dispatch & mission planning (LLM + rule-based)
│   ├── triage.py              # Victim prioritization scoring
│   ├── security.py            # GPS spoofing & jamming detection
│   ├── state_awareness.py     # Fleet state management
│   ├── perception.py          # Vision/acoustic detection (stub)
│   ├── routing.py             # Navigation (stub)
│   └── voice.py               # PersonaPlex integration (stub)
├── api/
│   └── server.py              # FastAPI REST server
├── config/
│   ├── settings.py            # Configuration management
│   └── __init__.py
├── dashboard/
│   └── app.py                 # Streamlit dashboard
├── simulation/
│   ├── factory.py             # Environment factory
│   ├── environment.py         # Abstract environment interface
│   ├── mock_env.py            # Demo/mock environment
│   ├── drone.py               # Drone data model
│   └── airsim_adapter/        # AirSim integration layer
│       ├── adapter.py
│       └── contracts.py
├── state/
│   └── fleet_state.py         # Fleet & mission state management
└── main.py                    # Main entry point
```

## Setup

1. Clone the repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Key dependencies:
- `fastapi` & `uvicorn` — API server
- `streamlit` — Dashboard UI
- `pandas` — Data handling
- `requests` — HTTP client
- `openai` — LLM client
- `airsim` — AirSim simulator (optional, for AirSim mode only)

3. Configure environment variables (see below)

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek/Vultr inference API key | Yes (falls back to rule-based if missing) |
| `DEEPSEEK_BASE_URL` | API endpoint | No (default: Vultr inference) |
| `DEEPSEEK_MODEL` | Model name | No (default: DeepSeek-V3.2) |
| `RUNTIME_MODE` | `DEMO`, `AIRSIM`, or `SIM` | No (default: DEMO) |
| `AIRSIM_IP` | AirSim simulator IP | AirSim mode only |
| `AIRSIM_PORT` | AirSim simulator port | AirSim mode only |

## Running Demo Mode

Demo mode uses a mock disaster environment — no AirSim or Unreal Engine required.

```bash
python main.py --mode demo --ticks 20
```

What happens:
- Initializes a mock disaster scenario with 3 drones and 4 victims
- Drones discover and are dispatched to victims via LLM or rule-based dispatch
- FastAPI server starts on port 8000
- Simulation runs for the specified number of ticks

**API docs:** http://localhost:8000/docs

## Running the Dashboard

Start the main system first, then in a separate terminal:

```bash
streamlit run dashboard/app.py
```

**Dashboard:** http://localhost:8501

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

**Dashboard shows empty data**
Ensure `main.py` is running and the API server is up on port 8000 before launching Streamlit.

**AirSim connection failed**
Verify AirSim is running and `AIRSIM_IP`/`AIRSIM_PORT` are correct.

**Import errors**
Run from the project root directory, not from a subdirectory.

## Known Limitations
- **Perception/Routing** — `perception.py`, `routing.py`, and `voice.py` are stubs pending implementation
- **Thread Safety** — Global state in the API server is not thread-safe under concurrent load
- **No Authentication** — API endpoints are publicly accessible
- **AirSim Integration** — Full AirSim drone command execution requires Unreal Engine setup
