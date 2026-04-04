"""
Runtime adapter manager.

Loads vendor-specific adapters dynamically from config and exposes health/capability reports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from integration.adapters import AdapterRegistry, DroneAdapter, SensorAdapter


@dataclass
class AdapterSpec:
    vendor: str
    adapter_type: str  # "drone" | "sensor"
    class_path: str
    config: Dict[str, Any] = field(default_factory=dict)


class AdapterManager:
    def __init__(self):
        self.registry = AdapterRegistry()
        self.load_errors: List[str] = []
        self.loaded_specs: List[AdapterSpec] = []

    def _load_class(self, class_path: str):
        module_name, class_name = class_path.rsplit(".", 1)
        module = import_module(module_name)
        return getattr(module, class_name)

    def register_adapter(self, spec: AdapterSpec) -> bool:
        try:
            cls = self._load_class(spec.class_path)
            instance = cls(**spec.config) if spec.config else cls()
            if spec.adapter_type == "drone":
                if not isinstance(instance, DroneAdapter):
                    raise TypeError(f"{spec.class_path} is not a DroneAdapter")
                self.registry.register_drone_adapter(spec.vendor, instance)
            elif spec.adapter_type == "sensor":
                if not isinstance(instance, SensorAdapter):
                    raise TypeError(f"{spec.class_path} is not a SensorAdapter")
                self.registry.register_sensor_adapter(spec.vendor, instance)
            else:
                raise ValueError(f"Unknown adapter type: {spec.adapter_type}")
            self.loaded_specs.append(spec)
            return True
        except Exception as e:
            self.load_errors.append(f"{spec.vendor}:{spec.class_path} -> {e}")
            return False

    def load_from_config(self, config_path: str = "config.json") -> None:
        p = Path(config_path)
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text())
            specs = data.get("adapters", [])
            for raw in specs:
                spec = AdapterSpec(
                    vendor=raw.get("vendor", "unknown"),
                    adapter_type=raw.get("type", ""),
                    class_path=raw.get("class_path", ""),
                    config=raw.get("config", {}) or {},
                )
                if spec.class_path:
                    self.register_adapter(spec)
        except Exception as e:
            self.load_errors.append(f"Failed reading {config_path}: {e}")

    def health_report(self) -> Dict[str, Any]:
        return {
            "registered": self.registry.list_registered(),
            "loaded_count": len(self.loaded_specs),
            "load_errors": self.load_errors[-20:],
        }

