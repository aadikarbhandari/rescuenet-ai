# RescueNet AI Production Pass Plan

## Phase 1: Repository Inspection and Planning

### Current Architecture Summary

**RescueNet AI** is a multi-agent drone coordination system with the following structure:

```
rescuenet-ai/
├── agents/                    # AI agent implementations
│   ├── coordinator.py        # Mission assignment and supervision
│   ├── state_awareness.py    # Fleet state monitoring and readiness
│   ├── triage.py            # Victim priority scoring
│   ├── perception.py        # (Placeholder) Vision/acoustic detection
│   ├── routing.py           # (Placeholder) Navigation
│   ├── security.py          # (Placeholder) Security monitoring
│   └── voice.py             # (Placeholder) Voice guidance
├── simulation/               # Simulation environment
│   ├── mock_env.py          # Deterministic mock environment
│   └── drone.py             # Simple Drone class
├── state/                    # State management
│   └── fleet_state.py       # Drone/Victim state data structures
├── dashboard/                # User interface
│   └── app.py               # Streamlit dashboard
├── main.py                  # Main simulation entry point
├── config.py                # (Empty) Configuration file
├── requirements.txt         # Dependencies
└── README.md               # Project documentation
```

### Key System Components

1. **Mock Environment** (`simulation/mock_env.py`):
   - Deterministic simulation with 3 drones and 4 victims
   - Provides drone/victim snapshots via `get_drone_snapshots()` and `get_victim_snapshots()`
   - Manages mission lifecycle with `step()`, `update_victim_assignment()`, `update_drone_mission()`
   - Tracks simulation tick counter

2. **State Management** (`state/fleet_state.py`):
   - `DroneState`, `VictimState`, `MissionAssignment` dataclasses
   - `FleetState` class with mission assignment logic
   - Capability checking via `can_perform_mission()`

3. **Agent System**:
   - `StateAwarenessAgent`: Ingests raw data, computes fleet readiness
   - `TriageAgent`: Prioritizes victims based on injury severity
   - `CoordinatorAgent`: Assigns missions to available drones

4. **Entry Points**:
   - `main.py`: Command-line simulation with tick-based loop
   - `dashboard/app.py`: Streamlit UI with real-time monitoring

### Current Dependencies on Mock Environment

The system is tightly coupled to `MockDisasterEnv` in two locations:
- `main.py`: Direct import and instantiation
- `dashboard/app.py`: Direct import and instantiation

**Environment Interface Methods Used:**
1. `__init__(seed: int)` - Constructor with seed parameter
2. `step()` - Advance simulation by one tick
3. `get_drone_snapshots() -> List[Dict]` - Get current drone states
4. `get_victim_snapshots() -> List[Dict]` - Get current victim states  
5. `get_completed_missions() -> List[str]` - Get recently completed missions
6. `update_victim_assignment(victim_id, drone_id, mission_id)` - Assign victim to mission
7. `update_drone_mission(drone_id, mission_id)` - Assign drone to mission
8. `tick` property - Current simulation tick
9. `drones` property - List of drone objects
10. `victims` property - List of victim objects

## Minimum Code Boundaries for Dual-Mode System

### 1. Environment Abstraction Interface

**Required Interface:** `BaseEnvironment`
```python
class BaseEnvironment(ABC):
    @abstractmethod
    def __init__(self, **kwargs):
        """Initialize environment with configuration."""
        pass
    
    @abstractmethod
    def step(self):
        """Advance simulation by one time step."""
        pass
    
    @abstractmethod
    def get_drone_snapshots(self) -> List[Dict[str, Any]]:
        """Return current drone states."""
        pass
    
    @abstractmethod
    def get_victim_snapshots(self) -> List[Dict[str, Any]]:
        """Return current victim states."""
        pass
    
    @abstractmethod
    def get_completed_missions(self) -> List[str]:
        """Return list of recently completed mission IDs."""
        pass
    
    @abstractmethod
    def update_victim_assignment(self, victim_id: str, drone_id: str, mission_id: str):
        """Assign victim to a drone mission."""
        pass
    
    @abstractmethod
    def update_drone_mission(self, drone_id: str, mission_id: str):
        """Assign drone to a mission."""
        pass
    
    @property
    @abstractmethod
    def tick(self) -> int:
        """Current simulation tick."""
        pass
```

### 2. Configuration System

**Required:** Runtime mode selection via configuration or command-line argument
- `--mode demo`: Use mock environment (current behavior)
- `--mode sim`: Use AirSim/real simulation environment (future)
- Environment-specific configuration (seed, AirSim settings, etc.)

### 3. Factory Pattern for Environment Creation

**Required:** Centralized environment factory that selects implementation based on mode.

## Proposed File/Module Structure for Production-Ready System

```
rescuenet-ai/
├── simulation/               # Simulation layer (REFACTORED)
│   ├── interfaces.py        # BaseEnvironment abstract class
│   ├── mock_env.py          # MockDisasterEnv (implements BaseEnvironment)
│   ├── airsim_env.py        # AirSimEnvironment (future, implements BaseEnvironment)
│   ├── factory.py           # EnvironmentFactory for mode selection
│   └── drone.py             # Drone model (unchanged)
├── config/                  # Configuration management (NEW)
│   ├── __init__.py
│   ├── settings.py          # App settings and mode selection
│   └── airsim_config.py     # AirSim-specific settings
├── agents/                  # AI agents (unchanged)
├── state/                   # State management (unchanged)
├── dashboard/               # Dashboard (MODIFIED)
│   └── app.py              # Updated to use EnvironmentFactory
├── main.py                 # Main entry point (MODIFIED)
├── config.py               # Legacy config (deprecate)
├── requirements.txt        # Dependencies
└── PRODUCTION_PASS_PLAN.md # This document
```

### Key Changes Required

#### 1. Create Abstract Interface (`simulation/interfaces.py`)
- Define `BaseEnvironment` abstract base class
- Ensure all required methods are abstract
- Include type hints and docstrings

#### 2. Refactor Mock Environment (`simulation/mock_env.py`)
- Make `MockDisasterEnv` inherit from `BaseEnvironment`
- Ensure all abstract methods are implemented
- No change to internal logic

#### 3. Create Environment Factory (`simulation/factory.py`)
```python
class EnvironmentFactory:
    @staticmethod
    def create_environment(mode: str, **kwargs) -> BaseEnvironment:
        if mode == "demo":
            from .mock_env import MockDisasterEnv
            return MockDisasterEnv(**kwargs)
        elif mode == "sim":
            # Future: from .airsim_env import AirSimEnvironment
            # return AirSimEnvironment(**kwargs)
            raise NotImplementedError("AirSim mode not yet implemented")
        else:
            raise ValueError(f"Unknown environment mode: {mode}")
```

#### 4. Update Main Entry Point (`main.py`)
- Add `--mode` command-line argument
- Replace direct `MockDisasterEnv` instantiation with factory
- Pass configuration parameters to factory

#### 5. Update Dashboard (`dashboard/app.py`)
- Replace direct `MockDisasterEnv` instantiation with factory
- Use configuration to determine mode
- Maintain backward compatibility (default to "demo" mode)

#### 6. Create Configuration Module (`config/`)
- Centralized settings management
- Mode selection logic
- Environment-specific configuration

## Implementation Phases

### Phase 1: Interface Definition and Mock Refactor
1. Create `simulation/interfaces.py` with `BaseEnvironment`
2. Update `MockDisasterEnv` to inherit from `BaseEnvironment`
3. Verify all abstract methods are implemented

### Phase 2: Factory Pattern Implementation
1. Create `simulation/factory.py` with `EnvironmentFactory`
2. Add mode selection logic
3. Test factory with "demo" mode

### Phase 3: Configuration System
1. Create `config/` directory with settings module
2. Add command-line argument parsing for mode selection
3. Add configuration loading from file/environment variables

### Phase 4: Update Entry Points
1. Modify `main.py` to use factory and configuration
2. Modify `dashboard/app.py` to use factory and configuration
3. Test both entry points with "demo" mode

### Phase 5: AirSim Integration (Future)
1. Create `simulation/airsim_env.py` implementing `BaseEnvironment`
2. Add AirSim-specific configuration in `config/airsim_config.py`
3. Extend factory to support "sim" mode
4. Test AirSim integration

## Constraints and Considerations

### Backward Compatibility
- Default mode must be "demo" to maintain current behavior
- All existing tests must pass without modification
- Dashboard must work without configuration changes

### Minimal Changes
- Only modify files that directly interact with environment
- Keep agent logic unchanged
- Maintain existing data structures and APIs

### Future Extensibility
- Interface designed for multiple simulation backends
- Configuration system supports additional parameters
- Factory pattern allows easy addition of new environment types

## Success Criteria

1. **Dual-mode operation**: System can run in "demo" or "sim" mode
2. **Backward compatibility**: Existing functionality unchanged in "demo" mode
3. **Clean abstraction**: No direct dependencies on `MockDisasterEnv` in main/dashboard
4. **Extensible design**: Easy to add new environment implementations
5. **Configuration-driven**: Mode selection via config/command-line

## Next Steps

1. **Phase 2**: Implement the interface and factory pattern
2. **Phase 3**: Update entry points to use new architecture
3. **Phase 4**: Test thoroughly with existing functionality
4. **Phase 5**: Begin AirSim integration (separate effort)

This plan establishes the foundation for a production-ready dual-mode system while maintaining the existing mock environment as the default "demo" mode.