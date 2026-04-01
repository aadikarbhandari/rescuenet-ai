"""
Environment factory for creating environment instances based on runtime mode.

This module provides activation plumbing for AirSim integration with
lazy imports and clear failure modes.
"""
import logging
import sys
from typing import Optional
from config import RuntimeMode, Settings
from .environment import Environment
from .mock_env import MockDisasterEnv


def create_environment(settings: Settings) -> Environment:
    """
    Create an environment instance based on runtime mode.
    
    This function provides clean activation paths for both demo and sim modes:
    - Demo mode: Always works with mock environment
    - Sim mode: Attempts to activate AirSim path with lazy imports and clear error handling
    
    Args:
        settings: Configuration settings containing runtime mode
        
    Returns:
        Environment instance appropriate for the runtime mode
        
    Raises:
        ValueError: If runtime mode is not supported
        ImportError: If AirSim dependencies are missing (sim mode only)
        RuntimeError: If AirSim activation fails (sim mode only)
    """
    logger = logging.getLogger(__name__)
    
    if settings.mode == RuntimeMode.DEMO:
        logger.info(f"Creating demo environment with seed={settings.mock_seed}")
        return MockDisasterEnv(
            seed=settings.mock_seed,
            # Note: mock_num_drones and mock_num_victims could be passed here
            # when the mock environment supports them
        )
    elif settings.mode == RuntimeMode.SIM:
        logger.info(f"Activating AirSim environment path for {settings.airsim_host}:{settings.airsim_port}")
        
        # Lazy import for AirSimEnvironment to avoid loading AirSim dependencies
        # in demo mode
        try:
            from .airsim_env import AirSimEnvironment
        except ImportError as e:
            # This should only happen if the airsim_env module itself is missing
            logger.error(f"Failed to import AirSimEnvironment module: {e}")
            raise ImportError(
                "AirSim environment module not available. "
                "This may indicate missing files or a corrupted installation. "
                "Demo mode should still work."
            ) from e
        
        # Attempt to create AirSim environment
        try:
            env = AirSimEnvironment(
                host=settings.airsim_host,
                port=settings.airsim_port
            )
            
            # Verify the environment is functional
            # This is a basic health check that doesn't require actual AirSim connectivity
            if not hasattr(env, 'step') or not callable(env.step):
                raise RuntimeError("AirSimEnvironment created but missing required methods")
            
            logger.info(f"AirSim environment activated successfully")
            return env
            
        except Exception as e:
            # Catch any errors during AirSim environment initialization
            logger.error(f"AirSim environment activation failed: {e}")
            raise RuntimeError(
                f"Failed to activate AirSim environment: {e}\n"
                f"To use demo mode instead, run with: --mode demo\n"
                f"Or set RESCUENET_MODE=demo environment variable."
            ) from e
    else:
        raise ValueError(f"Unsupported runtime mode: {settings.mode}")


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