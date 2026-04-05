"""Runtime persistence helpers (Pass 10).

Provides a tiny JSONL event log + JSON snapshot store so demo/sim runs
can be audited and state can be reloaded after restart.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


@dataclass
class RuntimeStore:
    root_dir: Path

    @classmethod
    def from_path(cls, path: str) -> "RuntimeStore":
        root = Path(path)
        root.mkdir(parents=True, exist_ok=True)
        return cls(root_dir=root)

    @property
    def events_path(self) -> Path:
        return self.root_dir / "events.jsonl"

    @property
    def snapshot_path(self) -> Path:
        return self.root_dir / "latest_snapshot.json"

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": event_type,
            "payload": payload,
        }
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def save_snapshot(self, state: Dict[str, Any]) -> None:
        tmp = self.snapshot_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(state, f, default=str)
        tmp.replace(self.snapshot_path)

    def load_snapshot(self) -> Optional[Dict[str, Any]]:
        if not self.snapshot_path.exists():
            return None
        with self.snapshot_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def tail_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.events_path.exists():
            return []
        with self.events_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        events = []
        for line in lines[-max(1, limit):]:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
        return events
