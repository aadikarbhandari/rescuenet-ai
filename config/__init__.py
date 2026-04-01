"""
Configuration module for RescueNet AI.
Centralized settings management for runtime mode selection.
"""

from .settings import RuntimeMode, Settings, get_settings

__all__ = ["RuntimeMode", "Settings", "get_settings"]