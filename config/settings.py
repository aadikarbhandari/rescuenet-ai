import os
import json
from pathlib import Path
from typing import Optional, Literal, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class RuntimeMode(str, Enum):
    """Available runtime modes for RescueNet AI."""
    DEMO = "demo"
    AIRSIM = "airsim"
    SIM = "sim"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class RescueStation:
    """Represents a rescue station with supplies and charging capability."""
    name: str
    x: float
    y: float
    z: float
    first_aid_kits: int = 10
    charging_slots: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "first_aid_kits": self.first_aid_kits,
            "charging_slots": self.charging_slots
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RescueStation":
        return cls(
            name=data.get("name", "Station"),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            z=data.get("z", 0.0),
            first_aid_kits=data.get("first_aid_kits", 10),
            charging_slots=data.get("charging_slots", 3)
        )


@dataclass
class AirSimSettings:
    """AirSim connection and drone configuration settings."""
    airsim_ip: str = "127.0.0.1"
    airsim_port: int = 41451
    num_drones: int = 5
    drone_names: List[str] = field(default_factory=lambda: ["Drone1", "Drone2", "Drone3", "Drone4", "Drone5"])
    battery_drain_rate: float = 0.5
    battery_drain_idle: float = 0.05
    battery_critical: float = 15.0
    battery_low: float = 25.0
    charging_rate: float = 1.0
    
    def __post_init__(self):
        if isinstance(self.drone_names, str):
            self.drone_names = json.loads(self.drone_names)


@dataclass
class DeepSeekSettings:
    """DeepSeek LLM API configuration."""
    deepseek_api_key: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY", "EYSU74G6QDLAB5345GNEBV34WGTMEHTLKZHA"))
    deepseek_base_url: str = "https://api.vultrinference.com/v1"
    deepseek_model: str = "DeepSeek-V3.2"
    llm_timeout: int = 30
    llm_max_tokens: int = 1000
    
    def __post_init__(self):
        if not self.deepseek_api_key:
            self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")


@dataclass
class VictimDetectionSettings:
    """Victim detection configuration."""
    confirmation_confidence: float = 0.65
    detection_radius: float = 50.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "confirmation_confidence": self.confirmation_confidence,
            "detection_radius": self.detection_radius
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VictimDetectionSettings":
        return cls(
            confirmation_confidence=data.get("confirmation_confidence", 0.65),
            detection_radius=data.get("detection_radius", 50.0)
        )


@dataclass
class SimulationSettings:
    """General simulation timing and logging settings."""
    tick_interval: float = 1.0
    max_ticks: int = 300
    log_level: str = "INFO"
    mode: str = "demo"
    
    def __post_init__(self):
        if self.mode not in ["demo", "airsim", "sim"]:
            self.mode = "demo"


@dataclass
class Settings:
    """
    Central application settings for RescueNet AI.
    Supports runtime mode selection via environment variables, config file, and command line.
    
    Priority order for mode selection:
    1. Command-line argument (highest priority)
    2. Environment variable RESCUENET_MODE
    3. Config file (config.json)
    4. Default: DEMO mode
    """
    
    # Subsystem configurations
    airsim: AirSimSettings = field(default_factory=AirSimSettings)
    deepseek: DeepSeekSettings = field(default_factory=DeepSeekSettings)
    simulation: SimulationSettings = field(default_factory=SimulationSettings)
    victim_detection: VictimDetectionSettings = field(default_factory=VictimDetectionSettings)
    
    # Rescue stations (spread across 1km terrain = 1000m x 1000m)
    rescue_stations: List[RescueStation] = field(default_factory=lambda: [
        RescueStation(name="Station_Alpha", x=-400.0, y=0.0, z=-400.0, first_aid_kits=15, charging_slots=5),
        RescueStation(name="Station_Beta", x=0.0, y=0.0, z=0.0, first_aid_kits=20, charging_slots=5),
        RescueStation(name="Station_Gamma", x=400.0, y=0.0, z=400.0, first_aid_kits=15, charging_slots=5),
    ])
    
    # Legacy compatibility fields
    mode: RuntimeMode = field(default=RuntimeMode.DEMO)
    mock_seed: int = 42
    mock_num_drones: int = 3
    mock_num_victims: int = 4
    log_level: str = "INFO"
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "EYSU74G6QDLAB5345GNEBV34WGTMEHTLKZHA")
    deepseek_base_url: str = "https://api.vultrinference.com/v1"
    deepseek_model: str = "DeepSeek-V3.2"
    llm_timeout: int = 30
    llm_max_tokens: int = 1000
    
    # Derived properties for backward compatibility
    @property
    def airsim_host(self) -> str:
        return self.airsim.airsim_ip
    
    @property
    def airsim_port(self) -> int:
        return self.airsim.airsim_port
    
    @property
    def llm_base_url(self) -> str:
        return self.deepseek.deepseek_base_url
    
    @property
    def llm_api_key(self) -> str:
        return self.deepseek.deepseek_api_key
    
    @property
    def llm_model(self) -> str:
        return self.deepseek.deepseek_model
    
    def __post_init__(self):
        """Validate settings after initialization."""
        if isinstance(self.mode, str):
            self.mode = RuntimeMode(self.mode.lower() if self.mode else "demo")
        if isinstance(self.log_level, str):
            pass
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        mode_str = os.getenv("RESCUENET_MODE", "").lower()
        mode = RuntimeMode.DEMO
        if mode_str in ["demo", "airsim", "sim"]:
            mode = RuntimeMode(mode_str)
        
        airsim = AirSimSettings(
            airsim_ip=os.getenv("AIRSIM_IP", "127.0.0.1"),
            airsim_port=int(os.getenv("AIRSIM_PORT", "41451")),
            num_drones=int(os.getenv("NUM_DRONES", "5")),
            drone_names=json.loads(os.getenv("DRONE_NAMES", '["Drone1", "Drone2", "Drone3", "Drone4", "Drone5"]')),
            battery_drain_rate=float(os.getenv("BATTERY_DRAIN_RATE", "0.5")),
            battery_drain_idle=float(os.getenv("BATTERY_DRAIN_IDLE", "0.05")),
            battery_critical=float(os.getenv("BATTERY_CRITICAL", "15.0")),
            battery_low=float(os.getenv("BATTERY_LOW", "25.0")),
            charging_rate=float(os.getenv("CHARGING_RATE", "1.0")),
        )
        
        deepseek = DeepSeekSettings(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.vultrinference.com/v1"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "DeepSeek-V3.2"),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", "30")),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1000")),
        )
        
        simulation = SimulationSettings(
            tick_interval=float(os.getenv("TICK_INTERVAL", "1.0")),
            max_ticks=int(os.getenv("MAX_TICKS", "300")),
            log_level=os.getenv("RESCUENET_LOG_LEVEL", "INFO"),
            mode=os.getenv("RESCUENET_MODE", "demo"),
        )
        
        victim_detection = VictimDetectionSettings(
            confirmation_confidence=float(os.getenv("CONFIRMATION_CONFIDENCE", "0.65")),
            detection_radius=float(os.getenv("DETECTION_RADIUS", "50.0")),
        )
        
        return cls(
            mode=mode,
            airsim=airsim,
            deepseek=deepseek,
            simulation=simulation,
            victim_detection=victim_detection,
            mock_seed=int(os.getenv("RESCUENET_MOCK_SEED", "42")),
            mock_num_drones=int(os.getenv("RESCUENET_MOCK_NUM_DRONES", "3")),
            mock_num_victims=int(os.getenv("RESCUENET_MOCK_NUM_VICTIMS", "4")),
            log_level=os.getenv("RESCUENET_LOG_LEVEL", "INFO"),
        )
    
    @classmethod
    def from_config_file(cls, config_path: Optional[Path] = None) -> "Settings":
        """Create settings from configuration file."""
        if config_path is None:
            config_path = Path("config.json")
        
        if not config_path.exists():
            return cls()
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            airsim_data = config_data.get("airsim", {})
            airsim = AirSimSettings(**airsim_data) if airsim_data else AirSimSettings()
            
            deepseek_data = config_data.get("deepseek", {})
            deepseek = DeepSeekSettings(**deepseek_data) if deepseek_data else DeepSeekSettings()
            
            simulation_data = config_data.get("simulation", {})
            simulation = SimulationSettings(**simulation_data) if simulation_data else SimulationSettings()
            
            victim_detection_data = config_data.get("victim_detection", {})
            victim_detection = VictimDetectionSettings.from_dict(victim_detection_data)
            
            stations_data = config_data.get("rescue_stations", [])
            rescue_stations = [RescueStation.from_dict(s) for s in stations_data] if stations_data else None
            
            mode_str = config_data.get("mode", "demo")
            if isinstance(mode_str, str):
                mode = RuntimeMode(mode_str.lower())
            else:
                mode = RuntimeMode.DEMO
            
            return cls(
                mode=mode,
                airsim=airsim,
                deepseek=deepseek,
                simulation=simulation,
                victim_detection=victim_detection,
                rescue_stations=rescue_stations,
                mock_seed=config_data.get("mock_seed", 42),
                mock_num_drones=config_data.get("mock_num_drones", 3),
                mock_num_victims=config_data.get("mock_num_victims", 4),
                log_level=config_data.get("log_level", "INFO"),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            print(f"Warning: Failed to load config file {config_path}: {e}")
            return cls()
    
    @classmethod
    def from_command_line(cls, mode_arg: Optional[str] = None, **kwargs) -> "Settings":
        """Create settings from command-line arguments."""
        settings = cls.from_env()
        
        if mode_arg and mode_arg.lower() in ["demo", "airsim", "sim"]:
            settings.mode = RuntimeMode(mode_arg.lower())
            settings.simulation.mode = settings.mode.value
        
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
            "log_level": self.log_level,
            "airsim": {
                "airsim_ip": self.airsim.airsim_ip,
                "airsim_port": self.airsim.airsim_port,
                "num_drones": self.airsim.num_drones,
                "drone_names": self.airsim.drone_names,
                "battery_drain_rate": self.airsim.battery_drain_rate,
                "battery_drain_idle": self.airsim.battery_drain_idle,
                "battery_critical": self.airsim.battery_critical,
                "battery_low": self.airsim.battery_low,
                "charging_rate": self.airsim.charging_rate,
            },
            "deepseek": {
                "deepseek_api_key": self.deepseek.deepseek_api_key,
                "deepseek_base_url": self.deepseek.deepseek_base_url,
                "deepseek_model": self.deepseek.deepseek_model,
                "llm_timeout": self.deepseek.llm_timeout,
                "llm_max_tokens": self.deepseek.llm_max_tokens,
            },
            "simulation": {
                "tick_interval": self.simulation.tick_interval,
                "max_ticks": self.simulation.max_ticks,
                "log_level": self.simulation.log_level,
                "mode": self.simulation.mode,
            },
            "victim_detection": self.victim_detection.to_dict(),
            "rescue_stations": [s.to_dict() for s in self.rescue_stations],
        }
    
    def __str__(self) -> str:
        return f"Settings(mode={self.mode.value}, log_level={self.log_level}, drones={self.airsim.num_drones}, stations={len(self.rescue_stations)})"


_settings_instance: Optional[Settings] = None


def get_settings(mode_arg: Optional[str] = None, **kwargs) -> Settings:
    """Get or create the global settings instance."""
    global _settings_instance
    
    if _settings_instance is None:
        _settings_instance = Settings.from_command_line(mode_arg, **kwargs)
        
        for key, value in kwargs.items():
            if hasattr(_settings_instance, key):
                setattr(_settings_instance, key, value)
    elif mode_arg is not None:
        if mode_arg.lower() in ["demo", "airsim", "sim"]:
            _settings_instance.mode = RuntimeMode(mode_arg.lower())
    
    return _settings_instance


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """Load settings from config file or environment, with defaults."""
    settings = Settings.from_config_file(config_path)
    
    env_settings = Settings.from_env()
    
    if settings.mode == RuntimeMode.DEMO and env_settings.mode != RuntimeMode.DEMO:
        settings.mode = env_settings.mode
    
    if settings.log_level == "INFO" and env_settings.log_level != "INFO":
        settings.log_level = env_settings.log_level
    
    return settings


def get_deepseek_headers(settings: Optional[Settings] = None) -> Dict[str, str]:
    """Get HTTP headers for DeepSeek API requests."""
    if settings is None:
        settings = get_settings()
    
    return {
        "Authorization": f"Bearer {settings.deepseek.deepseek_api_key}",
        "Content-Type": "application/json",
    }


def get_llm_client(settings: Optional[Settings] = None):
    """Get an OpenAI-compatible LLM client using the configured settings."""
    try:
        from openai import OpenAI
    except ImportError:
        print("Warning: openai library not installed. Install with: pip install openai")
        return None
    
    if settings is None:
        settings = get_settings()
    
    if not settings.deepseek.deepseek_api_key:
        raise ValueError("DeepSeek API key not configured. Set DEEPSEEK_API_KEY environment variable.")
    
    client = OpenAI(
        api_key=settings.deepseek.deepseek_api_key,
        base_url=settings.deepseek.deepseek_base_url,
        timeout=settings.deepseek.llm_timeout,
        max_retries=2,
    )
    
    return client


def reset_settings() -> None:
    """Reset the global settings instance."""
    global _settings_instance
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "EYSU74G6QDLAB5345GNEBV34WGTMEHTLKZHA")
    deepseek_base_url: str = "https://api.vultrinference.com/v1"
    deepseek_model: str = "DeepSeek-V3.2"
    _settings_instance = None


__all__ = [
    "RuntimeMode",
    "LogLevel", 
    "RescueStation",
    "AirSimSettings",
    "DeepSeekSettings",
    "VictimDetectionSettings",
    "SimulationSettings",
    "Settings",
    "get_settings",
    "load_settings",
    "get_deepseek_headers",
    "get_llm_client",
    "reset_settings",
]