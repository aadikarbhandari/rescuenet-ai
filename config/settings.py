"""
Centralized configuration settings for RescueNet AI.
Supports runtime mode selection via environment variables, config file, and command line.
"""

import os
import json
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass, field
from enum import Enum


class RuntimeMode(str, Enum):
    """Available runtime modes for RescueNet AI."""
    DEMO = "demo"  # Use mock environment (default)
    SIM = "sim"    # Use AirSim/real simulation (future)


@dataclass
class Settings:
    """
    Application settings with runtime mode configuration.
    
    Priority order for mode selection:
    1. Command-line argument (highest priority)
    2. Environment variable RESCUENET_MODE
    3. Config file (config.json)
    4. Default: DEMO mode
    """
    
    # Runtime mode configuration
    mode: RuntimeMode = field(default=RuntimeMode.DEMO)
    
    # Mock environment settings (for DEMO mode)
    mock_seed: int = field(default=42)
    mock_num_drones: int = field(default=3)
    mock_num_victims: int = field(default=4)
    
    # Simulation settings (for future SIM mode)
    airsim_host: str = field(default="localhost")
    airsim_port: int = field(default=41451)
    
    # General settings
    log_level: str = field(default="INFO")
    
    def __post_init__(self):
        """Validate settings after initialization."""
        if not isinstance(self.mode, RuntimeMode):
            self.mode = RuntimeMode(self.mode)
    
    @classmethod
    def from_env(cls) -> "Settings":
        """
        Create settings from environment variables.
        
        Environment variables:
        - RESCUENET_MODE: "demo" or "sim"
        - RESCUENET_MOCK_SEED: Seed for mock environment
        - RESCUENET_LOG_LEVEL: Logging level
        """
        mode_str = os.getenv("RESCUENET_MODE", "").lower()
        mode = RuntimeMode.DEMO  # Default
        
        if mode_str in ["demo", "sim"]:
            mode = RuntimeMode(mode_str)
        
        return cls(
            mode=mode,
            mock_seed=int(os.getenv("RESCUENET_MOCK_SEED", "42")),
            mock_num_drones=int(os.getenv("RESCUENET_MOCK_NUM_DRONES", "3")),
            mock_num_victims=int(os.getenv("RESCUENET_MOCK_NUM_VICTIMS", "4")),
            airsim_host=os.getenv("RESCUENET_AIRSIM_HOST", "localhost"),
            airsim_port=int(os.getenv("RESCUENET_AIRSIM_PORT", "41451")),
            log_level=os.getenv("RESCUENET_LOG_LEVEL", "INFO")
        )
    
    @classmethod
    def from_config_file(cls, config_path: Optional[Path] = None) -> "Settings":
        """
        Create settings from configuration file.
        
        Config file should be JSON format with keys matching Settings fields.
        Example:
        {
            "mode": "demo",
            "mock_seed": 42,
            "log_level": "INFO"
        }
        """
        if config_path is None:
            config_path = Path("config.json")
        
        if not config_path.exists():
            return cls()  # Return default settings
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Convert mode string to RuntimeMode enum
            if "mode" in config_data:
                config_data["mode"] = RuntimeMode(config_data["mode"])
            
            return cls(**config_data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Warning: Failed to load config file {config_path}: {e}")
            return cls()  # Return default settings on error
    
    @classmethod
    def from_command_line(cls, mode_arg: Optional[str] = None, **kwargs) -> "Settings":
        """
        Create settings from command-line arguments.
        
        Args:
            mode_arg: Runtime mode from command line ("demo" or "sim")
            **kwargs: Additional settings to override
        """
        settings = cls.from_env()  # Start with environment settings
        
        # Override with command-line mode if provided
        if mode_arg and mode_arg.lower() in ["demo", "sim"]:
            settings.mode = RuntimeMode(mode_arg.lower())
        
        # Override with any additional kwargs
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        return settings
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary for serialization."""
        return {
            "mode": self.mode.value,
            "mock_seed": self.mock_seed,
            "mock_num_drones": self.mock_num_drones,
            "mock_num_victims": self.mock_num_victims,
            "airsim_host": self.airsim_host,
            "airsim_port": self.airsim_port,
            "log_level": self.log_level
        }
    
    def __str__(self) -> str:
        """String representation of settings."""
        return f"Settings(mode={self.mode.value}, mock_seed={self.mock_seed}, log_level={self.log_level})"


# Global settings instance
_settings_instance: Optional[Settings] = None


def get_settings(mode_arg: Optional[str] = None, **kwargs) -> Settings:
    """
    Get or create the global settings instance.
    
    This function follows the priority order:
    1. Command-line arguments (if provided)
    2. Environment variables
    3. Config file
    4. Default values
    
    Args:
        mode_arg: Runtime mode from command line
        **kwargs: Additional settings to override
        
    Returns:
        Settings instance
    """
    global _settings_instance
    
    if _settings_instance is None:
        # Try config file first
        config_settings = Settings.from_config_file()
        
        # Override with environment variables
        env_settings = Settings.from_env()
        
        # Merge: environment overrides config file
        merged_settings = config_settings
        for key, value in env_settings.to_dict().items():
            if value != Settings().to_dict()[key]:  # Only override if different from default
                setattr(merged_settings, key, value)
        
        # Finally override with command-line arguments
        _settings_instance = Settings.from_command_line(mode_arg, **kwargs)
        
        # Apply any additional kwargs
        for key, value in kwargs.items():
            if hasattr(_settings_instance, key):
                setattr(_settings_instance, key, value)
    elif mode_arg is not None:
        # If settings already exist but new mode_arg provided, update it
        if mode_arg.lower() in ["demo", "sim"]:
            _settings_instance.mode = RuntimeMode(mode_arg.lower())
    
    return _settings_instance