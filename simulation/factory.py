"""
Environment factory for creating environment instances based on runtime mode.

This module provides activation plumbing for AirSim integration with
lazy imports and clear failure modes.
"""
import logging
from typing import Optional

from config import RuntimeMode, Settings
from .environment import Environment
from .mock_env import MockDisasterEnv


class SimulationFactory:
    """
    Factory class for creating environment instances based on runtime mode.
    
    Provides clean activation paths for both demo and sim/airsim modes:
    - Demo mode: Always works with mock environment
    - Sim mode: Attempts to activate AirSim path with lazy imports and clear error handling
    """
    
    _logger = logging.getLogger(__name__)
    
    @staticmethod
    def create(settings: Settings) -> Environment:
        """
        Create an environment instance based on runtime mode.
        
        Args:
            settings: Configuration settings containing runtime mode
            
        Returns:
            Environment instance appropriate for the runtime mode
            
        Raises:
            ValueError: If runtime mode is not supported
            ImportError: If AirSim dependencies are missing (sim mode only)
            RuntimeError: If AirSim activation fails (sim mode only)
        """
        mode = settings.mode.value if isinstance(settings.mode, RuntimeMode) else str(settings.mode).lower()
        if mode == RuntimeMode.DEMO.value:
            return SimulationFactory._create_demo(settings)
        elif mode in (RuntimeMode.SIM.value, RuntimeMode.AIRSIM.value):
            return SimulationFactory._create_airsim(settings)
        else:
            raise ValueError(f"Unsupported runtime mode: {settings.mode}")
    
    @staticmethod
    def create_environment(settings: Settings) -> Environment:
        """
        Create an environment instance based on runtime mode.
        
        This method provides a compatible interface for code that calls
        SimulationFactory.create_environment() directly.
        
        Args:
            settings: Configuration settings containing runtime mode
            
        Returns:
            Environment instance appropriate for the runtime mode
        """
        return SimulationFactory.create(settings)
    
    @staticmethod
    def _create_demo(settings: Settings) -> Environment:
        """Create a demo/mock environment."""
        SimulationFactory._logger.info(
            f"Creating demo environment with seed={settings.mock_seed}"
        )
        print("[Factory] Creating demo environment (no AirSim required)...")
        return MockDisasterEnv(
            seed=settings.mock_seed,
            num_drones=getattr(settings, "mock_num_drones", 3),
            num_victims=getattr(settings, "mock_num_victims", 4),
        )
    
    @staticmethod
    def _create_airsim(settings: Settings) -> Environment:
        """
        Create an AirSim environment with lazy imports and proper error handling.
        
        Raises:
            ImportError: If AirSim environment module is not available
            RuntimeError: If AirSim connection fails
        """
        SimulationFactory._logger.info(
            f"Activating AirSim environment path for {settings.airsim_host}:{settings.airsim_port}"
        )
        print(f"[Factory] Connecting to AirSim at {settings.airsim_host}:{settings.airsim_port}...")
        
        # Lazy import for AirSimEnvironment to avoid loading AirSim dependencies
        # in demo mode
        try:
            from .airsim_env import AirSimEnvironment
        except ImportError as e:
            SimulationFactory._logger.error(
                f"Failed to import AirSimEnvironment module: {e}"
            )
            raise ImportError(
                "AirSim environment module not available. "
                "This may indicate missing files or a corrupted installation. "
                "Demo mode should still work."
            ) from e
        
        # Attempt to create AirSim environment
        try:
            env = AirSimEnvironment(settings)
            
            # Verify the environment is functional
            if not hasattr(env, 'step') or not callable(env.step):
                raise RuntimeError("AirSimEnvironment created but missing required methods")
            
            # Connect and initialize if needed
            if hasattr(env, "is_connected") and not env.is_connected:
                env.connect()
            
            num_drones = getattr(settings, 'num_drones', len(settings.drone_names)) if hasattr(settings, 'drone_names') else getattr(settings, 'num_drones', 1)
            print(f"[Factory] Connected. {num_drones} drones ready.")
            print("[Factory] Spawning victims and supplies...")
            
            # Spawn victims if the method exists
            if hasattr(env, 'spawn_victims'):
                victim_count = getattr(settings, 'num_victims', 8)
                env.spawn_victims(count=victim_count)
            
            print("[Factory] Environment ready.")
            SimulationFactory._logger.info("AirSim environment activated successfully")
            return env
            
        except Exception as e:
            SimulationFactory._logger.error(f"AirSim environment activation failed: {e}")
            raise RuntimeError(
                f"Failed to activate AirSim environment: {e}\n"
                f"To use demo mode instead, run with: --mode demo\n"
                f"Or set RESCUENET_MODE=demo environment variable."
            ) from e


# Keep backward-compatible function interface
def create_environment(settings: Settings) -> Environment:
    """
    Create an environment instance based on runtime mode.
    
    This function provides clean activation paths for both demo and sim modes.
    
    Args:
        settings: Configuration settings containing runtime mode
        
    Returns:
        Environment instance appropriate for the runtime mode
    """
    return SimulationFactory.create(settings)


def get_environment(mode_arg: Optional[str] = None) -> Environment:
    """
    Convenience function to get environment with default configuration.
    
    Args:
        mode_arg: Optional command-line mode argument
        
    Returns:
        Environment instance
    """
    from config import get_settings
    settings = get_settings(mode_arg=mode_arg)
    return create_environment(settings)
