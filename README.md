# RescueNet AI

Autonomous disaster response drone coordination system powered by AI agents.

## Overview

RescueNet AI is an intelligent disaster response platform that coordinates a fleet of rescue drones to locate, prioritize, and assist victims during emergency situations. The system leverages AI agents for victim triage, mission planning, drone dispatch, and security monitoring.

## Features

- **AI-Powered Triage**: Prioritizes victims using DeepSeek LLM with rule-based fallback scoring
- **Intelligent Dispatch**: Coordinates drone assignments based on severity, distance, and battery status
- **Real-Time Dashboard**: Streamlit-based UI showing fleet status, victim locations, and mission progress
- **REST API**: FastAPI server for external integrations and monitoring
- **Security Monitoring**: Detects GPS spoofing, signal jamming, and anomalous drone behavior
- **Dual Mode Operation**: Supports both demo (mock) and AirSim simulation environments

## Repo Structure

```
rescuenet-ai/
├── agents/                    # AI agent modules
│   ├── coordinator.py         # Drone dispatch & mission planning
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
│   ├── app.py                 # Streamlit dashboard
│   └── dash.py                # Dashboard auto-fixer utility
├── simulation/
│   ├── factory.py             # Environment factory
│   ├── environment.py         # Abstract environment interface
│   ├── mock_env.py            # Demo/mock environment
│   ├── drone.py               # Drone data model
│   └── airsim_adapter/        # AirSim integration layer
│       ├── adapter.py
│       └── contracts.py
├── state/
│   └── fleet_state.py         # Fleet state management
└── main.py                    # Main entry point
```

## Setup

1. **Clone the repository**

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   Key dependencies include:
   - `fastapi` & `uvicorn` - API server
   - `streamlit` - Dashboard UI
   - `pandas` - Data handling
   - `requests` - HTTP client
   - `openai` - LLM client
   - `airsim` - AirSim simulator (optional, for AirSim mode)

3. **Configure environment variables** (see below)

## Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek API key for LLM triage/dispatch | Yes |
| `DEEPSEEK_BASE_URL` | DeepSeek API endpoint | No (default provided) |
| `DEEPSEEK_MODEL` | Model name (e.g., `deepseek-chat`) | No |
| `RUNTIME_MODE` | Execution mode: `DEMO`, `AIRSIM`, or `SIM` | No (default: DEMO) |
| `AIRSIM_IP` | AirSim simulator IP address | For AirSim mode |
| `AIRSIM_PORT` | AirSim simulator port | For AirSim mode |

## How to Run Demo Mode

Demo mode uses a mock disaster environment for testing without requiring AirSim.

```bash
# Set runtime mode
export RUNTIME_MODE=DEMO

# Run the main system
python main.py
```

The demo will:
- Initialize a mock disaster scenario with 8 victims
- Start the FastAPI server on port 8000
- Launch the Streamlit dashboard (if enabled)

**Dashboard Access**: Open `http://localhost:8501` in your browser

**API Documentation**: Available at `http://localhost:8000/docs`

## How to Run AirSim Mode

AirSim mode connects to Microsoft AirSim for realistic drone simulation.

1. **Start AirSim** in the Unreal Engine environment

2. **Configure connection**:
   ```bash
   export RUNTIME_MODE=AIRSIM
   export AIRSIM_IP=127.0.0.1
   export AIRSIM_PORT=41451
   export DEEPSEEK_API_KEY=your_api_key
   ```

3. **Run the system**:
   ```bash
   python main.py
   ```

## Troubleshooting

### API Key Issues
- **Symptom**: Triage/dispatch falls back to rule-based mode
- **Fix**: Ensure `DEEPSEEK_API_KEY` is set correctly in environment

### Dashboard Not Loading
- **Symptom**: Streamlit fails to start or shows connection errors
- **Fix**: Check that the API server is running on port 8000

### AirSim Connection Failed
- **Symptom**: Adapter returns mock data despite AirSim mode
- **Fix**: Verify AirSim is running and `AIRSIM_IP`/`AIRSIM_PORT` are correct

### Missing Victims in Dashboard
- **Symptom**: Dashboard shows empty victim list
- **Fix**: Check `FleetState` victim management - known limitation in current version

### Battery Drain Issues
- **Symptom**: Drones lose battery too quickly or not at all
- **Fix**: Battery logic is actively tuned in `mock_env.py` - values may need adjustment

### Import Errors
- **Symptom**: `ModuleNotFoundError` for internal modules
- **Fix**: Ensure you're running from the project root directory

## Known Limitations

- **LLM Dispatch Path**: Currently disabled (`if False and ...` in coordinator.py) - system uses rule-based dispatch
- **Perception/Routing**: Stub modules require implementation
- **Thread Safety**: Global state in API server is not thread-safe
- **No Authentication**: API endpoints are publicly accessible
