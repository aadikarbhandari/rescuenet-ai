#!/usr/bin/env python3
"""Pass 11 soak test helper.

Runs demo mode for N ticks and checks that /ops/metrics exposes expected
fields after warm-up. Intended for local/CI non-blocking burn-in checks.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from urllib.request import urlopen
import json


def wait_for_metrics(url: str, timeout_s: float = 10.0):
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            with urlopen(url, timeout=2) as r:
                if r.status == 200:
                    payload = json.loads(r.read().decode("utf-8"))
                    required = {"avg_tick_ms", "p50_tick_ms", "p95_tick_ms", "max_tick_ms"}
                    if required.issubset(payload.keys()):
                        return payload
        except Exception:
            time.sleep(0.2)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run demo soak test")
    parser.add_argument("--ticks", type=int, default=25)
    parser.add_argument("--api-port", type=int, default=8000)
    args = parser.parse_args()

    proc = subprocess.Popen([sys.executable, "main.py", "--mode", "demo", "--ticks", str(args.ticks), "--api-port", str(args.api_port)])
    try:
        metrics = wait_for_metrics(f"http://127.0.0.1:{args.api_port}/ops/metrics", timeout_s=20)
        if metrics is None:
            print("[FAIL] Could not read /ops/metrics during soak run")
            return 1

        print(f"[PASS] Soak metrics available: avg={metrics.get('avg_tick_ms')} p95={metrics.get('p95_tick_ms')}")
        return 0
    finally:
        try:
            proc.wait(timeout=60)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
