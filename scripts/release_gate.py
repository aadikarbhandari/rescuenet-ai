#!/usr/bin/env python3
"""Pass 6 release gate checks.

Runs a small set of production-safety checks:
1) bytecode compile smoke
2) unit/integration validation suite
3) demo runtime smoke
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import List


@dataclass
class CheckResult:
    name: str
    command: List[str]
    returncode: int


CHECKS = [
    ("compileall", [sys.executable, "-m", "compileall", "-q", "."]),
    ("pass6_validation_tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]),
    ("demo_smoke", [sys.executable, "main.py", "--mode", "demo", "--ticks", "1"]),
]


def run_check(name: str, command: List[str]) -> CheckResult:
    print(f"\n==> Running {name}: {' '.join(command)}")
    proc = subprocess.run(command)
    return CheckResult(name=name, command=command, returncode=proc.returncode)


def main() -> int:
    results: List[CheckResult] = []
    for name, command in CHECKS:
        result = run_check(name, command)
        results.append(result)
        if result.returncode != 0:
            print(f"\n[FAIL] {name} failed with return code {result.returncode}")
            break

    failed = [r for r in results if r.returncode != 0]
    print("\n=== Release Gate Summary ===")
    for result in results:
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"- {result.name}: {status}")

    if failed:
        return 1
    print("All release gate checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
