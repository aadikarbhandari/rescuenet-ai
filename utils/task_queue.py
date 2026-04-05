"""Durable task queue (Pass 14).

SQLite-backed queue for async work separation between API and workers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import sqlite3
import threading
import time
import uuid


@dataclass
class QueueTask:
    task_id: str
    kind: str
    payload: Dict[str, Any]
    status: str
    created_at: float
    updated_at: float
    attempts: int = 0
    last_error: Optional[str] = None


class SQLiteTaskQueue:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_queue (
                    task_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
                """
            )
            conn.commit()

    def _connect(self):
        return sqlite3.connect(str(self.db_path), timeout=5)

    def enqueue(self, kind: str, payload: Dict[str, Any], task_id: Optional[str] = None) -> str:
        now = time.time()
        tid = task_id or f"task_{uuid.uuid4().hex}"
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO task_queue
                    (task_id, kind, payload, status, created_at, updated_at, attempts, last_error)
                    VALUES (?, ?, ?, 'queued', ?, ?, 0, NULL)
                    """,
                    (tid, kind, json.dumps(payload, default=str), now, now),
                )
                conn.commit()
        return tid

    def claim_next(self, kind: Optional[str] = None) -> Optional[QueueTask]:
        with self._lock:
            with self._connect() as conn:
                if kind:
                    row = conn.execute(
                        "SELECT task_id, kind, payload, status, created_at, updated_at, attempts, last_error "
                        "FROM task_queue WHERE status='queued' AND kind=? ORDER BY created_at ASC LIMIT 1",
                        (kind,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT task_id, kind, payload, status, created_at, updated_at, attempts, last_error "
                        "FROM task_queue WHERE status='queued' ORDER BY created_at ASC LIMIT 1"
                    ).fetchone()
                if not row:
                    return None
                now = time.time()
                conn.execute(
                    "UPDATE task_queue SET status='in_progress', updated_at=?, attempts=attempts+1 WHERE task_id=?",
                    (now, row[0]),
                )
                conn.commit()
        return QueueTask(
            task_id=row[0], kind=row[1], payload=json.loads(row[2]), status="in_progress",
            created_at=row[4], updated_at=now, attempts=int(row[6]) + 1, last_error=row[7]
        )

    def complete(self, task_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("UPDATE task_queue SET status='done', updated_at=? WHERE task_id=?", (time.time(), task_id))
                conn.commit()

    def fail(self, task_id: str, error: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE task_queue SET status='failed', updated_at=?, last_error=? WHERE task_id=?",
                    (time.time(), error[:500], task_id),
                )
                conn.commit()

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT task_id, kind, payload, status, created_at, updated_at, attempts, last_error "
                    "FROM task_queue ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(limit, 500)),),
                ).fetchall()
        out = []
        for r in rows:
            out.append({
                "task_id": r[0],
                "kind": r[1],
                "payload": json.loads(r[2]),
                "status": r[3],
                "created_at": r[4],
                "updated_at": r[5],
                "attempts": r[6],
                "last_error": r[7],
            })
        return out
