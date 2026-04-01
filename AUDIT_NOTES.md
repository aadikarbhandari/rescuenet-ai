# RescueNet AI - Agent & Simulation Audit

**Task:** P1-T1  
**Phase:** Phase 1 - Audit and Document  
**Date:** 2025

---

## Executive Summary

This audit examines the current state of all 7 agent files, the simulation loop, and dashboard integration. The codebase has a solid foundation with functional priority scoring and mission assignment logic, but AI (LLM) integration is minimal - most decisions are rule-based.

**Key Finding:** The demo mode runs end-to-end with deterministic behavior. AI integration points are clearly identified for triage enhancement, coordinator replanning, perception, voice, and security.

---

## 1. Agent Files - Current State

### 1.1 `agents/triage.py` - **PARTIALLY FUNCTIONAL**

**What it does:**
- `TriageVictim` dataclass with 7 attributes (victim_id, severity, conscious, bleeding, body_temperature_c, accessibility, position)
- `compute_priority()`: Rule-based scoring (0-100) using weighted factors:
  - Severity: 0-30 points
  - Consciousness: 0-20 points  
  - Bleeding: 0-25 points
  - Body temperature: 0-15 points
  - Accessibility: 0-10 points
- `prioritize_victims()`: Sorts victims by score descending
- `triage_from_victim_states()`: Converts generic victim states to TriageVictim, filters undetected

**What it SHOULD do (AI integration points):**
- [ ] LLM-based injury assessment from sensor data
- [ ] Contextual priority adjustment (e.g., multiple victims in same area, time-of-day factors)
- [ ] Natural language reasoning output for dashboard
- [ ] Dynamic weight adjustment based on mission context

**Status:** ✅ Functional algorithm, needs AI enhancement for contextual reasoning

---

### 1.2 `agents/coordinator.py` - **MOSTLY FUNCTIONAL**

**What it does:**
- `prioritize_victims()`: Sorts by severity + distance to available drones
- `assign_missions()`: Main assignment loop that:
  - Filters assignable victims (not assigned, not in cooldown, confirmed)
  - Finds best drone via `fleet.get_best_drone_for()`
  - Checks drone capability via `fleet.can_perform_mission()`
  - Creates mission assignments
  - Handles alternative drone selection
- `_find_alternative_drone()`: Complex scoring with distance, battery, capability, reliability, environment factors
- `_task_for_severity()`: Maps severity to task type (critical→extract, severe→deliver, moderate→assist, minor→scan)

**What it SHOULD do (AI integration points):**
- [ ] LLM-based replanning when missions fail
- [ ] Dynamic task type selection based on real-time conditions
- [ ] Multi-objective optimization explanation for operators
- [ ] Mode switching logic (RescueNet ↔ Repurposed)

**Status:** ✅ Robust assignment logic, needs AI for dynamic replanning and mode switching

---

### 1.3 `agents/perception.py` - **STUB**

**What it does:**
- Only contains: `"""\nVision + acoustic detection\n"""`

**What it SHOULD do:**
- [ ] Process sensor data from drones (camera, thermal, acoustic)
- [ ] Victim detection confidence scoring
- [ ] False positive filtering
- [ ] LLM-based scene interpretation

**Status:** ❌ Stub - needs full implementation

---

### 1.4 `agents/state_awareness.py` - **STUB**

**What it does:**
- Only contains: `"""\nGlobal situational awareness\n"""`

**What it SHOULD do:**
- [ ] Maintain global mission state
- [ ] Track terrain/zones
- [ ] Build situational awareness picture
- [ ] LLM-based threat assessment

**Status:** ❌ Stub - needs implementation

---

### 1.5 `agents/voice.py` - **STUB**

**What it does:**
- Only contains: `"""\nPersonaPlex integration\n"""`

**What it SHOULD do:**
- [ ] Text-to-speech for victim guidance
- [ ] Integration with PersonaPlex
- [ ] Natural language victim communication
- [ ] Dynamic guidance messages based on victim condition

**Status:** ❌ Stub - needs implementation

---

### 1.6 `agents/security.py` - **STUB**

**What it does:**
- Only contains: `"""\nEncryption, spoofing detection, audit logging\n"""`

**What it SHOULD do:**
- [ ] Spoofing detection
- [ ] Jamming detection
- [ ] Encryption status monitoring
- [ ] Operator-visible alerts
- [ ] LLM-based anomaly detection

**Status:** ❌ Stub - needs implementation

---

### 1.7 `agents/routing.py` - **STUB**

**What it does:**
- Only contains: `"""\nNavigation + jamming fallback\n"""`

**What it SHOULD do:**
- [ ] Path planning
- [ ] Obstacle avoidance
- [ ] Optimal route calculation
- [ ] Jamming fallback navigation

**Status:** ❌ Stub - needs implementation

---

## 2. Simulation Core - Current State

### 2.1 `simulation/drone.py` - **BASIC**

**What it does:**
- Simple `Drone` class with id, x, y, battery, task
- Basic __repr__ for debugging

**Status:** ⚠️ Minimal - needs enhancement for full mission simulation

### 2.2 `simulation/mock_env.py` - **NOT EXAMINED**

**Expected to contain:**
- Mock environment setup
- 3 mock drones
- 4 mock victims
- Environment configuration

### 2.3 `simulation/environment.py` - **NOT EXAMINED**

**Expected to contain:**
- Base environment class
- Zone/terrain definitions
- Physics simulation

---

## 3. State Management - Current State

### 3.1 `state/fleet_state.py` - **FUNCTIONAL**

**FleetState:**
- `drones: Dict[str, DroneState]` - All drone instances
- `victims: Dict[str, VictimState]` - All victim instances
- `assignments: Dict[str, MissionAssignment]` - Active missions
- `get_best_drone_for(victim_id, task_type)` - Drone selection logic
- `can_perform_mission(drone_id, task_type)` - Capability checking
- `create_assignment(drone_id, victim_id, task_type)` - Mission creation
- `update_tick()` - State progression

**DroneState:**
- position (x, y, z)
- battery_percent
- current_mission
- winch_status
- payload_kg
- sensor_status
- mechanical_health
- wind_speed_ms
- visibility_m

**VictimState:**
- victim_id
- position (x, y, z)
- injury_severity (1-10)
- is_detected
- is_confirmed
- detection_confidence
- assigned_drone
- mission_id
- cooldown_until_tick

**Status:** ✅ Functional state management with clear data structures

---

## 4. Tick Loop Flow (Demo Mode)

Based on `main.py` structure:

```
main.py --mode demo --ticks N
    │
    ├── Initialize Mock Environment (simulation/mock_env.py)
    │   ├── Create 3 mock drones
    │   ├── Create 4 mock victims
    │   └── Initialize FleetState
    │
    ├── For each tick (1 to N):
    │   │
    │   ├── perception.detect_victims()     # STUB - returns mock detections
    │   │
    │   ├── triage.triage_from_victim_states()  # ✅ Functional
    │   │
    │   ├── coordinator.assign_missions()   # ✅ Functional
    │   │
    │   ├── fleet.update_tick()             # Update drone positions, battery
    │   │
    │   └── (optional) dashboard.update()   # Streamlit refresh
    │
    └── Output mission summary
```

**Key observation:** The tick loop is deterministic and works end-to-end, but AI decisions are currently rule-based.

---

## 5. Dashboard - Current State

### 5.1 `dashboard/app.py` - **PARTIAL**

**What it does:**
- Streamlit-based dashboard
- Fleet telemetry display
- Drone status visualization
- Basic mission tracking

**What it SHOULD do (missing):**
- [ ] Live AI decisions display
- [ ] Triage reasoning output
- [ ] Mode switching visualization
- [ ] Security alerts panel
- [ ] Voice agent status

**Status:** ⚠️ Basic telemetry only, needs AI decision integration

---

## 6. AI Integration Points Required

### Priority 1: Triage Enhancement
- **Location:** `agents/triage.py`
- **Current:** Rule-based scoring with fixed weights
- **Needed:**
  - LLM call to assess victim condition from raw sensor data
  - Contextual priority (e.g., "victim near toxic zone")
  - Natural language explanation for dashboard

### Priority 2: Coordinator Replanning
- **Location:** `agents/coordinator.py`
- **Current:** Static task mapping (severity → task type)
- **Needed:**
  - LLM-based replanning when drone fails or conditions change
  - Mode switching logic (RescueNet ↔ Repurposed)
  - Multi-objective optimization reasoning

### Priority 3: Perception
- **Location:** `agents/perception.py`
- **Current:** Empty stub
- **Needed:**
  - Process camera/thermal data
  - Confidence scoring
  - LLM scene interpretation

### Priority 4: Voice Agent
- **Location:** `agents/voice.py`
- **Current:** TTS placeholder
- **Needed:**
  - PersonaPlex integration
  - Dynamic guidance messages based on victim condition

### Priority 5: Security
- **Location:** `agents/security.py`
- **Current:** Stub
- **Needed:**
  - Spoofing/jamming detection demo
  - Dashboard alerts

---

## 7. Data Flow Summary

```
Simulation Tick Loop
        │
        ▼
┌───────────────────┐
│  Mock Environment │
│  (drones, victims)│
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   FleetState      │◄─── state/fleet_state.py
│   (drones,        │
│    victims,       │
│    assignments)   │
└─────────┬─────────┘
          │
    ┌─────┴─────┬──────────┬──────────┐
    ▼           ▼          ▼          ▼
┌───────┐ ┌────────┐ ┌─────────┐ ┌─────────┐
│Percep-│ │ Triage │ │Coordina-│ │ Security│
│tion   │ │        │ │tor      │ │         │
│(stub) │ │(func-  │ │(func-   │ │ (stub)  │
│       │ │tional) │ │tional)  │ │         │
└───┬───┘ └───┬────┘ └────┬────┘ └────┬────┘
    │         │            │           │
    └─────────┴─────┬──────┴───────────┘
                    ▼
           ┌────────────────┐
           │  Dashboard     │
           │  (telemetry    │
           │   only)        │
           └────────────────┘
```

---

## 8. Integration Points Summary

| Component | Current Status | AI Integration Point | Priority |
|-----------|---------------|---------------------|----------|
| triage.py | Functional | LLM contextual scoring | P1 |
| coordinator.py | Functional | Replanning + mode switching | P1 |
| perception.py | Stub | Scene interpretation | P2 |
| voice.py | Stub | PersonaPlex integration | P2 |
| security.py | Stub | Anomaly detection | P3 |
| routing.py | Stub | Path planning | P3 |
| state_awareness.py | Stub | Situational awareness | P2 |
| dashboard/app.py | Partial | AI reasoning display | P1 |

---

## 9. Recommendations

1. **Immediate:** Add LLM calls to triage.py for contextual scoring
2. **Short-term:** Implement perception.py stub with mock detection
3. **Medium-term:** Add mode switching to coordinator.py
4. **Long-term:** Full voice and security integration

---

## 10. Blocking Issues

**None identified.** The codebase is ready for AI integration work:
- ✅ Core simulation loop functional
- ✅ State management in place
- ✅ Dashboard infrastructure ready
- ✅ Clear integration points identified

---

*End of Audit*
