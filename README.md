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
- **Autonomy Policy v2** — Critical override, low-battery auto-return posture, and optional supply-drone reserve policy
- **Observability Metrics** — Runtime ops metrics (tick latency, LLM success/fallback rates, assignments) via API
- **Latency Percentiles** — Ops metrics now include p50/p95/max tick latency for quick performance tracking

## System Architecture

```
Multi-Agent AI Layer
  ├── Coordinator Agent    — LLM-driven dispatch + rule-based fallback
  ├── Policy Engine        — Hard safety guardrails over autonomous decisions
  ├── Triage Agent         — Victim prioritization scoring
  ├── Security Agent       — GPS spoofing & jamming detection
  ├── State Awareness      — Fleet state management
  ├── Perception           — MVP victim detection scoring from telemetry/snapshots
  ├── Routing              — MVP safe-altitude routes + jamming fallback route mode
  └── Voice                — NVIDIA PersonaPlex integration (stub)

Control & Integration Layer
  ├── Fleet State          — Drone & mission state management
  ├── Adapter Manager      — Runtime loading + health for vendor adapters
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
│   ├── perception.py        # MVP perception (distance + sensor confidence model)
│   ├── routing.py           # MVP routing (safe altitude + jam fallback)
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
| `RESCUENET_API_KEY` | Optional API key for REST auth (`key` or `sha256:<digest>`, comma-separated keys supported) | Unset (auth off) |
| `RESCUENET_RATE_LIMIT_PER_MIN` | Optional per-IP limit for protected endpoints | `120` |
| `RESCUENET_STATE_DB` | SQLite path for durable API state backend | `runtime_data/state.db` |
| `RESCUENET_QUEUE_DB` | SQLite path for durable async task queue backend | `runtime_data/queue.db` |

4. Optional: register vendor adapters in `config.json`:
```json
{
  "adapters": [
    {
      "vendor": "vendor_name",
      "type": "drone",
      "class_path": "your_package.your_module.YourDroneAdapter",
      "config": {}
    }
  ]
}
```

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

Ops reliability metrics endpoint:
- `GET /ops/metrics`
- `GET /ops/events?limit=50` (persisted runtime events tail)
- `GET /ops/state-backend` (active API state backend info)
- `POST /ops/tasks/enqueue`, `POST /ops/tasks/claim`, `GET /ops/tasks` (durable queue control plane)

Production validation harness (Pass 6):
- `python scripts/release_gate.py`
- Runs compile checks, validation tests, and a 1-tick demo smoke test.
- Optional soak gate: `RESCUENET_RUN_SOAK=1 python scripts/release_gate.py`
- Optional load/SLO gate: `RESCUENET_RUN_LOAD=1 python scripts/release_gate.py`
- CI workflow (`.github/workflows/release-gate.yml`) runs the same gate on pull requests and main/work pushes.
- Pass 8 adds API/reliability integration tests under `tests/test_pass8_integration.py`.
- Pass 9 adds MVP perception/routing tests under `tests/test_pass9_agent_mvp.py`.
- Pass 10 adds persistence tests under `tests/test_pass10_persistence.py`.
- Pass 11 adds observability percentile tests under `tests/test_pass11_observability.py`.
- Pass 12 adds API hardening tests under `tests/test_pass12_api_hardening.py`.
- Pass 13 adds durable state backend tests under `tests/test_pass13_state_backend.py`.
- Pass 14 adds durable task queue tests under `tests/test_pass14_task_queue.py`.
- Pass 15 adds SLO helper tests under `tests/test_pass15_slo_gate.py`.

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

- **Voice** — stub module, pending implementation
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
