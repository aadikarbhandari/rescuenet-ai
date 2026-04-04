"""
Operational observability helpers (metrics + structured events).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List
import json


def structured_event(event_type: str, **fields: Any) -> str:
    payload = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event_type,
        **fields,
    }
    return json.dumps(payload, default=str)


@dataclass
class OpsMetrics:
    ticks: int = 0
    llm_triage_success: int = 0
    llm_triage_fallback: int = 0
    llm_dispatch_success: int = 0
    llm_dispatch_fallback: int = 0
    assignments_executed: int = 0
    total_tick_ms: float = 0.0
    recent_tick_ms: List[float] = field(default_factory=list)

    def record_tick(self, tick_ms: float) -> None:
        self.ticks += 1
        self.total_tick_ms += tick_ms
        self.recent_tick_ms.append(tick_ms)
        self.recent_tick_ms = self.recent_tick_ms[-50:]

    def avg_tick_ms(self) -> float:
        return 0.0 if self.ticks == 0 else self.total_tick_ms / self.ticks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticks": self.ticks,
            "llm_triage_success": self.llm_triage_success,
            "llm_triage_fallback": self.llm_triage_fallback,
            "llm_dispatch_success": self.llm_dispatch_success,
            "llm_dispatch_fallback": self.llm_dispatch_fallback,
            "assignments_executed": self.assignments_executed,
            "avg_tick_ms": round(self.avg_tick_ms(), 2),
            "recent_tick_ms": [round(x, 2) for x in self.recent_tick_ms],
        }

