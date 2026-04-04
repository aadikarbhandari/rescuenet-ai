# RescueNet AI
Autonomous disaster response drone coordination system powered by AI agents.

## Overview
RescueNet AI is a modular multi-agent AI platform that acts as the central command brain for fleets of drones and sensors. In disaster scenarios, the system analyses conditions in real time and coordinates multiple drone fleets simultaneously, executing decisions at scale while remaining under human supervision.

The system enables real-time victim detection, injury triage, coordinated multi-drone operations, and security monitoring — all without requiring physical hardware via a built-in mock simulation environment.

## Features
- **AI-Powered Triage** — Prioritizes victims using DeepSeek LLM with rule-based fallback scoring
- **Intelligent Dispatch** — Coordinates drone assignments based on victim severity, distance, and battery status
- **Real-Time Dashboard** — Streamlit UI showing live fleet status, victim locations, missions, AI decisions, and security alerts
- **REST API** — FastAPI server on port 8000 for external integrations and monitoring
- **Security Monitoring** — Detects GPS spoofing, signal jamming, and anomalous drone behavior
- **Dual Mode Operation** — Demo mode (mock environment, no hardware) and AirSim mode (Unreal Engine)
- **Mission Lifecycle** — Full cycle: victim discovery → triage → dispatch → en route → on scene → return to base → charging → idle
- **AI Decisions Log** — Live log of every LLM dispatch decision with timestamps and assignments
- **Policy Guardrails** — Battery floor, reserve drone, and distance sanity checks before mission execution
- **Reliability Layer** — Retry/backoff + circuit-breaker protection for external LLM API calls

## System Architecture

```
Multi-Agent AI Layer
  ├── Coordinator Agent    — LLM-driven dispatch + rule-based fallback
  ├── Policy Engine        — Hard safety guardrails over autonomous decisions
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
│   └── app.py               # Streamlit real-time dashboard (self-contained)
├── simulation/
│   ├── factory.py           # Environment factory
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
Key dependencies: `fastapi`, `uvicorn`, `streamlit`, `pandas`, `requests`

3. Configure environment variables (optional — defaults are provided):

| Variable | Description | Default |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek/Vultr inference API key | Built-in fallback |
| `DEEPSEEK_BASE_URL` | API endpoint | Vultr inference |
| `DEEPSEEK_MODEL` | Model name | DeepSeek-V3.2 |
| `RUNTIME_MODE` | `DEMO`, `AIRSIM`, or `SIM` | `DEMO` |
| `RESCUENET_API_KEY` | Optional API key for protecting REST endpoints | Unset (auth off) |

## Running Demo Mode

Demo mode uses a mock disaster environment — no AirSim or Unreal Engine required.

```bash
python main.py --mode demo --ticks 200
```

What happens:
- Initializes mock disaster scenario with 3 drones and 4 victims
- Drones discover victims and are dispatched via LLM or rule-based dispatch
- Full mission lifecycle runs automatically across all ticks
- Security agent monitors for GPS spoofing and signal jamming
- FastAPI server starts on port 8000

API docs available at: `http://localhost:8000/docs`

If `RESCUENET_API_KEY` is set, REST endpoints (except health/docs) require:
- `X-API-Key: <your_key>` header, or
- `Authorization: Bearer <your_key>` header

## Running the Dashboard

The dashboard is fully self-contained — it runs its own simulation loop internally and does not require `main.py` to be running.

```bash
streamlit run dashboard/app.py
```

Dashboard: `http://localhost:8501`

**Dashboard features:**
- **Fleet Overview** — Total drones, available count, active missions, victims detected/rescued
- **Drone Fleet Status** — Live battery levels, positions, mission assignments, health status
- **Active Missions** — Per-drone mission tracking with target victim
- **Victim Triage Panel** — Severity scoring, detected-by drone, assigned drone, status (Discovered/Assigned)
- **AI Decisions Log** — Real-time log of every LLM dispatch decision with timestamps and full assignment details
- **Security Alerts** — GPS spoofing and signal jamming detections
- **Manual Controls** — Step simulation tick-by-tick or reset

To run the dashboard with SSH tunneling from a remote server:
```bash
ssh -L 8501:localhost:8501 -L 8000:localhost:8000 user@your-server-ip
```
Then open `http://localhost:8501` locally.

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

## Demo Walkthrough

For a quick live demo:

1. Start the dashboard: `streamlit run dashboard/app.py`
2. Open `http://localhost:8501` in your browser
3. Click **Step Simulation** — on the first step the LLM dispatches 3 drones to the highest-priority victims
4. Keep stepping — watch drones move (positions update), battery drain, missions progress
5. Expand entries in the **AI Decisions Log** to see the full LLM assignment reasoning
6. Notice victim_4 stays "Discovered/Unassigned" until a drone completes a mission and becomes available — correct triage behavior

## Troubleshooting

**Triage/dispatch falls back to rule-based mode**
Ensure `DEEPSEEK_API_KEY` is set and the API endpoint is reachable.

**Import errors**
Run from the project root directory, not from a subdirectory.

**Port already in use**
```bash
pkill -f "python main.py"
pkill -f streamlit
```

**Dashboard shows stale data**
Click the reset button in the sidebar, or restart streamlit.

## Known Limitations

- **Perception / Routing / Voice** — stub modules, pending implementation
- **victim_4 stays unassigned** — correct behavior; only 3 drones available for 4 victims, the lowest-priority victim waits until a drone is free
- **AirSim Integration** — full drone command execution requires Unreal Engine + GPU
- **Thread Safety** — global state in the API server is not thread-safe under concurrent load
- **No Authentication** — API endpoints are publicly accessible
  - Mitigation added: optional API key auth via `RESCUENET_API_KEY` (recommended in non-demo setups)

## Production Readiness Status

RescueNet is currently a high-capability prototype with strong autonomous workflow coverage, but it is not yet fully production-hardened for real-world emergency infrastructure.

### Already implemented for safer autonomy
- LLM + rule-based fallback behavior for triage/dispatch
- Enum-based state consistency in fleet/mission lifecycle
- Policy guardrails before executing assignments (battery floor, reserve drones, distance sanity)

### Still required for full production operations
- Hardware-in-the-loop validation at scale
- AuthN/AuthZ, encryption, and complete command audit trails
- Reliability SLOs, distributed queueing/retries, and chaos testing
- Regulatory/certification and formal incident response runbooks
