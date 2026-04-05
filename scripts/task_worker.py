#!/usr/bin/env python3
"""Pass 14 worker process for SQLite task queue."""
from __future__ import annotations

import argparse
import os
import time
from utils.task_queue import SQLiteTaskQueue


def handle_task(kind: str, payload: dict) -> None:
    # Placeholder work handlers for queue plumbing validation.
    if kind == "noop":
        return
    if kind == "sleep":
        time.sleep(float(payload.get("seconds", 0.1)))
        return
    # Unknown kinds are still accepted for now.


def main() -> int:
    parser = argparse.ArgumentParser(description="Run queue worker")
    parser.add_argument("--kind", type=str, default=None, help="Optional task kind filter")
    parser.add_argument("--max-tasks", type=int, default=10)
    parser.add_argument("--poll-interval", type=float, default=0.2)
    args = parser.parse_args()

    queue = SQLiteTaskQueue(os.getenv("RESCUENET_QUEUE_DB", "runtime_data/queue.db"))
    processed = 0

    while processed < args.max_tasks:
        task = queue.claim_next(kind=args.kind)
        if not task:
            time.sleep(args.poll_interval)
            continue
        try:
            handle_task(task.kind, task.payload)
            queue.complete(task.task_id)
        except Exception as e:
            queue.fail(task.task_id, str(e))
        processed += 1

    print(f"Processed {processed} task(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
