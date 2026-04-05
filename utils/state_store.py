"""Durable state backend (Pass 13).

Simple SQLite key/value store for API runtime state.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import json
import sqlite3
import threading
import time


@dataclass
class SQLiteStateStore:
    db_path: Path

    def __post_init__(self):
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS state_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    @classmethod
    def from_path(cls, path: str) -> "SQLiteStateStore":
        return cls(db_path=Path(path))

    def _connect(self):
        return sqlite3.connect(str(self.db_path), timeout=5)

    def set_many(self, values: Dict[str, Any]) -> None:
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO state_kv (key, value, updated_at) VALUES (?, ?, ?)",
                    [(k, json.dumps(v, default=str), now) for k, v in values.items()],
                )
                conn.commit()

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT value FROM state_kv WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        return json.loads(row[0])

    def get_many(self, keys: list[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k in keys:
            out[k] = self.get(k)
        return out
