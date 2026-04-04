#!/usr/bin/env python3
"""Pass 15 API load/SLO gate.

Runs a short live load probe against API endpoints while demo runtime is active.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.slo import evaluate_slo


def ping(url: str, timeout: float = 2.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def wait_for_health(base_url: str, timeout_s: float = 20.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        if ping(f"{base_url}/health"):
            return True
        time.sleep(0.2)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run API load/SLO gate")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ticks", type=int, default=35)
    parser.add_argument("--requests", type=int, default=80)
    parser.add_argument("--p95-budget-ms", type=float, default=800.0)
    parser.add_argument("--max-error-rate", type=float, default=0.05)
    args = parser.parse_args()

    base = f"http://127.0.0.1:{args.api_port}"
    proc = subprocess.Popen([
        sys.executable, "main.py", "--mode", "demo", "--ticks", str(args.ticks), "--api-port", str(args.api_port)
    ])

    try:
        if not wait_for_health(base):
            print("[FAIL] API health not ready")
            return 1

        latencies = []
        errors = 0
        endpoints = ["/health", "/status", "/ops/metrics"]

        for i in range(args.requests):
            ep = endpoints[i % len(endpoints)]
            start = time.time()
            try:
                with urlopen(f"{base}{ep}", timeout=2.0) as r:
                    if r.status != 200:
                        errors += 1
                    _ = r.read()
            except URLError:
                errors += 1
            finally:
                latencies.append((time.time() - start) * 1000.0)

        passed, summary = evaluate_slo(
            latencies_ms=latencies,
            errors=errors,
            total=args.requests,
            p95_budget_ms=args.p95_budget_ms,
            max_error_rate=args.max_error_rate,
        )

        print(json.dumps(summary))
        if not passed:
            print("[FAIL] SLO gate failed")
            return 1
        print("[PASS] SLO gate passed")
        return 0
    finally:
        try:
            proc.wait(timeout=60)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
